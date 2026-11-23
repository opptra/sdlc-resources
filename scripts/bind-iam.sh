#!/usr/bin/env bash
# Bootstrap the IAM planner and applier for a protected environment.
set -euo pipefail

usage() {
  cat <<'HELP'
Usage: bind-staging.sh --with-iam <org/repo>
       bind-production.sh --with-iam <org/repo> <project>

Set IAM_STATE_BUCKET to a dedicated, versioned state bucket controlled by
the IAM administrators, IAM_GRANT_ROLES to a comma-separated list of
delegated roles, and IAM_GRANT_MEMBERS to a comma-separated list of
service account emails the workflow may manage. See docs/bind.md.
HELP
}

if [[ "${1:-}" == --help ]]; then usage; exit 0; fi
if [[ $# -ne 6 ]]; then usage >&2; exit 2; fi

repo=$1 project=$2 environment=$3 identity_project=$4 pool=$5 provider=$6
: "${IAM_STATE_BUCKET:?Set IAM_STATE_BUCKET to the dedicated IAM state bucket}"
: "${IAM_GRANT_ROLES:?Set IAM_GRANT_ROLES to the roles to delegate}"
: "${IAM_GRANT_MEMBERS:?Set IAM_GRANT_MEMBERS to the service account emails to manage}"
[[ "$environment" == staging || "$environment" == production ]]
[[ "$project" =~ ^[a-z][a-z0-9-]+$ ]]
[[ "$IAM_STATE_BUCKET" =~ ^[a-z0-9][-a-z0-9_.]+$ ]]
[[ "$repo" =~ ^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$ ]]
command -v jq >/dev/null
gcloud storage buckets describe "gs://$IAM_STATE_BUCKET" --raw --format=json |
  jq -e '(.versioning.enabled // false) and
    (.iamConfiguration.uniformBucketLevelAccess.enabled // .uniform_bucket_level_access // false)' >/dev/null ||
  { echo 'Use a versioned state bucket with uniform bucket-level access.' >&2; exit 1; }

roles=$(jq -cen --arg value "$IAM_GRANT_ROLES" '
  $value | split(",") | unique |
  if all(.[]; test("^(roles/[a-zA-Z0-9_.]+|projects/[a-z0-9-]+/roles/[a-zA-Z0-9_]+)$"))
  then . else error("Invalid IAM_GRANT_ROLES") end')
members=$(jq -cen --arg value "$IAM_GRANT_MEMBERS" '
  $value | split(",") | unique |
  if all(.[]; test("^[a-z][a-z0-9-]*@[a-z0-9-]+[.]iam[.]gserviceaccount[.]com$"))
  then map("serviceAccount:" + .) else error("Invalid IAM_GRANT_MEMBERS") end')
while IFS= read -r role; do
  case "$role" in
    roles/owner|roles/editor|roles/viewer) echo "Basic role $role is outside the delegated scope." >&2; exit 1 ;;
    roles/*) definition=$(gcloud iam roles describe "$role" --format=json) ;;
    projects/"$project"/roles/*)
      definition=$(gcloud iam roles describe "${role##*/}" --project="$project" --format=json) ;;
    *) echo "Custom roles must belong to $project." >&2; exit 1 ;;
  esac
  jq -e '(.includedPermissions | length > 0) and
    all(.includedPermissions[]; test("setIamPolicy$|^iam[.]roles[.]|^iam[.]serviceAccountKeys[.]|^iam[.]serviceAccounts[.](getAccessToken|getOpenIdToken|signBlob|signJwt|implicitDelegation)$") | not)' \
    <<<"$definition" >/dev/null ||
    { echo "Role $role can change IAM or issue credentials. Choose a narrower role." >&2; exit 1; }
done < <(jq -r '.[]' <<<"$roles")

number=$(gcloud projects describe "$identity_project" --format='value(projectNumber)')
[[ "$number" =~ ^[0-9]+$ ]]
provider_path="projects/$number/locations/global/workloadIdentityPools/$pool/providers/$provider"
prefix=$(gh api "repos/$repo/actions/oidc/customization/sub" --jq '.sub_claim_prefix')
[[ "$prefix" == repo:* ]]
# Use a short deterministic ID that works with longer repository names.
key=$(printf '%s' "$repo/$environment" | shasum -a 256 | cut -c1-16)
planner="iam-plan-$key@$project.iam.gserviceaccount.com"
applier="iam-apply-$key@$project.iam.gserviceaccount.com"
jq -e --arg planner "serviceAccount:$planner" --arg applier "serviceAccount:$applier" '
    all(.[]; . != $planner and . != $applier)' <<<"$members" >/dev/null
condition="api.getAttribute('iam.googleapis.com/modifiedGrantsByRole', []).hasOnly($roles)"
title="sdlc-iam-$key"
existing=$(gcloud projects get-iam-policy "$project" --format=json)
# Rebinding the same scope is safe. An administrator must explicitly remove a
# previous condition before changing the delegated roles.
jq -e --arg member "serviceAccount:$applier" --arg title "$title" --arg expression "$condition" '
  all(.bindings[]? |
    select(.role == "roles/resourcemanager.projectIamAdmin" and (.members | index($member)));
    .condition.title == $title and .condition.expression == $expression)
' <<<"$existing" >/dev/null || {
  echo "Review and remove the previous project IAM delegation for $applier before rebinding." >&2
  exit 1
}

# Verify the apply environment before giving any workflow cloud authority.
gh api "repos/$repo/environments/$environment-iam-plan" >/dev/null
apply_environment=$(gh api "repos/$repo/environments/$environment-iam-apply")
if [[ "$environment" == staging ]]; then
  jq -e 'any(.protection_rules[]?; .type == "required_reviewers" and .prevent_self_review == true and (.reviewers | length > 0))' <<<"$apply_environment" >/dev/null ||
    { echo "Require a teammate reviewer for staging-iam-apply." >&2; exit 1; }
fi
printf '%s\n' "$apply_environment" |
  jq -e '.deployment_branch_policy.custom_branch_policies' >/dev/null ||
  { echo "Configure required reviewers, prevent self-review, and select a branch for $environment-iam-apply." >&2; exit 1; }
gh api --paginate --slurp "repos/$repo/environments/$environment-iam-apply/deployment-branch-policies" |
  jq -e --arg branch "$environment" '
    [.[].branch_policies[]] | length == 1 and .[0].name == $branch and .[0].type == "branch"
  ' >/dev/null ||
  { echo "Allow only the $environment branch in $environment-iam-apply." >&2; exit 1; }

for phase in plan apply; do
  id="iam-$phase-$key"
  email="$id@$project.iam.gserviceaccount.com"
  if ! gcloud iam service-accounts describe "$email" --project="$project" >/dev/null 2>&1; then
    gcloud iam service-accounts create "$id" --project="$project" --display-name="SDLC IAM $phase for $repo"
  fi
  gcloud iam service-accounts add-iam-policy-binding "$email" --project="$project" \
    --role=roles/iam.workloadIdentityUser \
    --member="principal://iam.googleapis.com/projects/$number/locations/global/workloadIdentityPools/$pool/subject/$prefix:environment:$environment-iam-$phase" --quiet
  gh variable set WIF_PROVIDER --repo "$repo" --env "$environment-iam-$phase" --body "$provider_path"
  gh variable set WIF_SERVICE_ACCOUNT --repo "$repo" --env "$environment-iam-$phase" --body "$email"
  gh variable set IAM_PROJECT --repo "$repo" --env "$environment-iam-$phase" --body "$project"
  gh variable set IAM_STATE_BUCKET --repo "$repo" --env "$environment-iam-$phase" --body "$IAM_STATE_BUCKET"
  gh variable set IAM_GRANT_ROLES --repo "$repo" --env "$environment-iam-$phase" --body "$roles"
  gh variable set IAM_GRANT_MEMBERS --repo "$repo" --env "$environment-iam-$phase" --body "$members"
done

gcloud projects add-iam-policy-binding "$project" --member="serviceAccount:$planner" \
  --role=roles/iam.securityReviewer --condition=None --quiet
gcloud projects add-iam-policy-binding "$project" --member="serviceAccount:$applier" \
  --role=roles/resourcemanager.projectIamAdmin \
  --condition="^|^title=$title|expression=$condition" --quiet
gcloud storage buckets add-iam-policy-binding "gs://$IAM_STATE_BUCKET" \
  --member="serviceAccount:$planner" --role=roles/storage.objectViewer --quiet
gcloud storage buckets add-iam-policy-binding "gs://$IAM_STATE_BUCKET" \
  --member="serviceAccount:$applier" --role=roles/storage.objectAdmin --quiet
printf 'IAM planner and applier configured for %s in %s.\n' "$repo" "$environment"
