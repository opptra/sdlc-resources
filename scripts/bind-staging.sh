#!/usr/bin/env bash
# Let one GitHub repository plan and apply Terraform in the staging project.
# Usage: scripts/bind-staging.sh <org/repo>
# Creates the staging deployer only. Does not deploy and does not touch production.
# Production is scripts/bind-production.sh. See docs/bind.md.

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: scripts/bind-staging.sh <org/repo>" >&2
  exit 2
fi

REPO="$1"
CI_PROJECT="${CI_PROJECT:-opptra-sdlc-ci}"
STAGING_PROJECT="${STAGING_PROJECT:-opptra-staging}"
POOL="${WIF_POOL:-opptra-github}"
PROVIDER="${WIF_PROVIDER:-github}"
REGION="${REGION:-asia-south1}"
ENVIRONMENT="staging"
NAME="${REPO##*/}"
ACCOUNT="${NAME}-deployer"

if [[ "$REPO" != */* ]]; then
  echo "repo must look like opptra/finance-ops" >&2
  exit 2
fi

if [[ "$STAGING_PROJECT" == "$CI_PROJECT" ]]; then
  echo "staging project must be a workload project, not ${CI_PROJECT}." >&2
  exit 2
fi

if [[ ! "$ACCOUNT" =~ ^[a-z][a-z0-9-]{4,28}[a-z0-9]$ ]]; then
  echo "service account id ${ACCOUNT} must be 6 to 30 characters. Shorten the GitHub repository name." >&2
  exit 2
fi

if ! gcloud projects describe "$STAGING_PROJECT" >/dev/null 2>&1; then
  echo "staging project ${STAGING_PROJECT} does not exist yet. Follow docs/gcp-bootstrap.md." >&2
  exit 1
fi

if ! gcloud iam workload-identity-pools describe "$POOL" \
  --project="$CI_PROJECT" --location=global >/dev/null 2>&1; then
  echo "workload identity pool ${POOL} is missing in ${CI_PROJECT}, or this account cannot read it." >&2
  exit 1
fi

CI_NUMBER="$(gcloud projects describe "$CI_PROJECT" --format='value(projectNumber)')"

github_subject() {
  local repo="$1"
  local environment="$2"
  local prefix
  if ! command -v gh >/dev/null 2>&1; then
    echo "gh is required to read the GitHub token name for ${repo}." >&2
    exit 1
  fi
  prefix="$(gh api "repos/${repo}/actions/oidc/customization/sub" --jq '.sub_claim_prefix')"
  if [[ -z "$prefix" || "$prefix" != repo:* ]]; then
    echo "could not read the GitHub token name for ${repo}" >&2
    exit 1
  fi
  printf '%s:environment:%s' "$prefix" "$environment"
}

SUBJECT="$(github_subject "$REPO" "$ENVIRONMENT")"
LEGACY_SUBJECT="repo:${REPO}:environment:${ENVIRONMENT}"
MEMBER="principal://iam.googleapis.com/projects/${CI_NUMBER}/locations/global/workloadIdentityPools/${POOL}/subject/${SUBJECT}"
LEGACY_MEMBER="principal://iam.googleapis.com/projects/${CI_NUMBER}/locations/global/workloadIdentityPools/${POOL}/subject/${LEGACY_SUBJECT}"

enable_apis() {
  local project="$1"
  gcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com \
    iamcredentials.googleapis.com \
    iam.googleapis.com \
    cloudresourcemanager.googleapis.com \
    iap.googleapis.com \
    storage.googleapis.com \
    sqladmin.googleapis.com \
    cloudscheduler.googleapis.com \
    cloudtasks.googleapis.com \
    firestore.googleapis.com \
    monitoring.googleapis.com \
    --project="$project"
}

ensure_registry() {
  local project="$1"
  if ! gcloud artifacts repositories describe apps \
    --project="$project" --location="$REGION" >/dev/null 2>&1; then
    gcloud artifacts repositories create apps \
      --project="$project" \
      --location="$REGION" \
      --repository-format=docker \
      --description="App images for opptra/sdlc"
  fi
}

ensure_sa() {
  local project="$1"
  local account="$2"
  local email="${account}@${project}.iam.gserviceaccount.com"
  if ! gcloud iam service-accounts describe "$email" --project="$project" >/dev/null 2>&1; then
    gcloud iam service-accounts create "$account" --project="$project" --display-name="$account"
  fi
}

grant_project_role() {
  local project="$1"
  local email="$2"
  local role="$3"
  gcloud projects add-iam-policy-binding "$project" \
    --member="serviceAccount:${email}" \
    --role="$role" \
    --quiet >/dev/null
}

drop_repo_wide_binding() {
  local project="$1"
  local deployer="$2"
  local staging_number old_member
  staging_number="$(gcloud projects describe "$STAGING_PROJECT" --format='value(projectNumber)' 2>/dev/null || true)"
  if [[ -z "$staging_number" ]]; then
    return 0
  fi
  old_member="principalSet://iam.googleapis.com/projects/${staging_number}/locations/global/workloadIdentityPools/${POOL}/attribute.repository/${REPO}"
  gcloud iam service-accounts remove-iam-policy-binding "$deployer" \
    --project="$project" \
    --member="$old_member" \
    --role=roles/iam.workloadIdentityUser \
    --quiet >/dev/null 2>&1 || true
}

bind_deployer() {
  local project="$1"
  local deployer="${ACCOUNT}@${project}.iam.gserviceaccount.com"
  local bucket="${project}-tfstate"

  if ! gcloud storage buckets describe "gs://${bucket}" >/dev/null 2>&1; then
    echo "missing Terraform state bucket gs://${bucket}. Follow docs/gcp-bootstrap.md." >&2
    exit 1
  fi

  ensure_sa "$project" "$ACCOUNT"
  grant_project_role "$project" "$deployer" roles/run.admin
  grant_project_role "$project" "$deployer" roles/artifactregistry.writer
  grant_project_role "$project" "$deployer" roles/iam.serviceAccountAdmin
  grant_project_role "$project" "$deployer" roles/iam.serviceAccountUser
  grant_project_role "$project" "$deployer" roles/resourcemanager.projectIamAdmin
  grant_project_role "$project" "$deployer" roles/secretmanager.admin
  grant_project_role "$project" "$deployer" roles/cloudsql.admin
  grant_project_role "$project" "$deployer" roles/cloudscheduler.admin
  grant_project_role "$project" "$deployer" roles/cloudtasks.admin
  grant_project_role "$project" "$deployer" roles/storage.admin
  grant_project_role "$project" "$deployer" roles/monitoring.alertPolicyEditor
  # Log-based alerts also create a Logging notification rule.
  grant_project_role "$project" "$deployer" roles/logging.configWriter

  gcloud storage buckets add-iam-policy-binding "gs://${bucket}" \
    --member="serviceAccount:${deployer}" \
    --role="roles/storage.objectAdmin" \
    --quiet >/dev/null
  gcloud storage buckets add-iam-policy-binding "gs://${bucket}" \
    --member="serviceAccount:${deployer}" \
    --role="roles/storage.legacyBucketReader" \
    --quiet >/dev/null

  drop_repo_wide_binding "$project" "$deployer"
  if [[ "$SUBJECT" != "$LEGACY_SUBJECT" ]]; then
    gcloud iam service-accounts remove-iam-policy-binding "$deployer" \
      --project="$project" \
      --member="$LEGACY_MEMBER" \
      --role=roles/iam.workloadIdentityUser \
      --quiet >/dev/null 2>&1 || true
  fi
  gcloud iam service-accounts add-iam-policy-binding "$deployer" \
    --project="$project" \
    --member="$MEMBER" \
    --role=roles/iam.workloadIdentityUser \
    --quiet >/dev/null
}

enable_apis "$STAGING_PROJECT"
ensure_registry "$STAGING_PROJECT"
bind_deployer "$STAGING_PROJECT"

PROVIDER_RESOURCE="projects/${CI_NUMBER}/locations/global/workloadIdentityPools/${POOL}/providers/${PROVIDER}"
STAGING_DEPLOYER="${ACCOUNT}@${STAGING_PROJECT}.iam.gserviceaccount.com"

cat <<EOF

Staging deployer is ready. This script did not deploy and did not change production.

Create the GitHub environment "staging" before the first staging plan or deploy, if it does not exist yet.
A repository admin does that under Settings → Environments. Also create "production" and add a required reviewer there when the plan allows it.

Set these Actions variables on ${REPO}:

WIF_PROVIDER_STAGING=${PROVIDER_RESOURCE}
WIF_SERVICE_ACCOUNT_STAGING=${STAGING_DEPLOYER}

gh variable set WIF_PROVIDER_STAGING --repo ${REPO} --body "${PROVIDER_RESOURCE}"
gh variable set WIF_SERVICE_ACCOUNT_STAGING --repo ${REPO} --body "${STAGING_DEPLOYER}"

Send scripts/bind-production.sh to someone who can change IAM in this app's production project.
They do not need access to ${STAGING_PROJECT}.
EOF
