#!/usr/bin/env bash
# Let one GitHub repository plan and apply Terraform for one app.
# Usage: scripts/bind-repo.sh <org/repo> <prod-project-id>
# Creates the CI service account only. Terraform creates the Cloud Run service
# and the runtime service account. Requires docs/gcp-bootstrap.md first.

set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: scripts/bind-repo.sh <org/repo> <prod-project-id>" >&2
  exit 2
fi

REPO="$1"
PROD_PROJECT="$2"
STAGING_PROJECT="${STAGING_PROJECT:-opptra-staging}"
POOL="${WIF_POOL:-opptra-github}"
PROVIDER="${WIF_PROVIDER:-github}"
REGION="${REGION:-asia-south1}"
NAME="${REPO##*/}"

if [[ "$REPO" != */* ]]; then
  echo "repo must look like opptra/finance-ops" >&2
  exit 2
fi

if ! gcloud projects describe "$STAGING_PROJECT" >/dev/null 2>&1; then
  echo "staging project ${STAGING_PROJECT} does not exist yet. Follow docs/gcp-bootstrap.md." >&2
  exit 1
fi

gcloud projects describe "$PROD_PROJECT" >/dev/null

if ! gcloud iam workload-identity-pools describe "$POOL" \
  --project="$STAGING_PROJECT" --location=global >/dev/null 2>&1; then
  echo "workload identity pool ${POOL} is missing in ${STAGING_PROJECT}." >&2
  exit 1
fi

STAGING_NUMBER="$(gcloud projects describe "$STAGING_PROJECT" --format='value(projectNumber)')"
MEMBER="principalSet://iam.googleapis.com/projects/${STAGING_NUMBER}/locations/global/workloadIdentityPools/${POOL}/attribute.repository/${REPO}"

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

bind_deployer() {
  local project="$1"
  local deployer="${NAME}-deployer@${project}.iam.gserviceaccount.com"
  local bucket="${project}-tfstate"

  if ! gcloud storage buckets describe "gs://${bucket}" >/dev/null 2>&1; then
    echo "missing Terraform state bucket gs://${bucket}. Follow docs/gcp-bootstrap.md." >&2
    exit 1
  fi

  ensure_sa "$project" "${NAME}-deployer"
  grant_project_role "$project" "$deployer" roles/run.admin
  grant_project_role "$project" "$deployer" roles/artifactregistry.writer
  grant_project_role "$project" "$deployer" roles/iam.serviceAccountAdmin
  grant_project_role "$project" "$deployer" roles/iam.serviceAccountUser

  gcloud storage buckets add-iam-policy-binding "gs://${bucket}" \
    --member="serviceAccount:${deployer}" \
    --role="roles/storage.objectAdmin" \
    --quiet >/dev/null
  gcloud storage buckets add-iam-policy-binding "gs://${bucket}" \
    --member="serviceAccount:${deployer}" \
    --role="roles/storage.legacyBucketReader" \
    --quiet >/dev/null

  gcloud iam service-accounts add-iam-policy-binding "$deployer" \
    --project="$project" \
    --member="$MEMBER" \
    --role=roles/iam.workloadIdentityUser \
    --quiet >/dev/null
}

enable_apis "$STAGING_PROJECT"
enable_apis "$PROD_PROJECT"
ensure_registry "$STAGING_PROJECT"
ensure_registry "$PROD_PROJECT"
bind_deployer "$STAGING_PROJECT"
bind_deployer "$PROD_PROJECT"

PROVIDER_RESOURCE="projects/${STAGING_NUMBER}/locations/global/workloadIdentityPools/${POOL}/providers/${PROVIDER}"

cat <<EOF

Set these Actions variables on ${REPO}:

WIF_PROVIDER_STAGING=${PROVIDER_RESOURCE}
WIF_SERVICE_ACCOUNT_STAGING=${NAME}-deployer@${STAGING_PROJECT}.iam.gserviceaccount.com
WIF_PROVIDER_PROD=${PROVIDER_RESOURCE}
WIF_SERVICE_ACCOUNT_PROD=${NAME}-deployer@${PROD_PROJECT}.iam.gserviceaccount.com

gh variable set WIF_PROVIDER_STAGING --repo ${REPO} --body "${PROVIDER_RESOURCE}"
gh variable set WIF_SERVICE_ACCOUNT_STAGING --repo ${REPO} --body "${NAME}-deployer@${STAGING_PROJECT}.iam.gserviceaccount.com"
gh variable set WIF_PROVIDER_PROD --repo ${REPO} --body "${PROVIDER_RESOURCE}"
gh variable set WIF_SERVICE_ACCOUNT_PROD --repo ${REPO} --body "${NAME}-deployer@${PROD_PROJECT}.iam.gserviceaccount.com"
EOF
