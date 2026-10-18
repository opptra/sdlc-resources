#!/usr/bin/env bash
# Protect main and production. staging stays unprotected so a push deploys it.
# Usage: scripts/protect-branches.sh <org/repo>
# Set PLAN_CHECK=plan when the repo has a Terraform plan workflow.

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: scripts/protect-branches.sh <org/repo>" >&2
  exit 2
fi

REPO="$1"
CHECK_NAME="${CHECK_NAME:-ci}"
CONTEXTS="[\"${CHECK_NAME}\"]"
if [[ -n "${PLAN_CHECK:-}" ]]; then
  CONTEXTS="[\"${CHECK_NAME}\", \"${PLAN_CHECK}\"]"
fi

for branch in main production; do
  if ! gh api "repos/${REPO}/branches/${branch}" >/dev/null 2>&1; then
    echo "${REPO} has no ${branch} branch. Push it, then run this script again." >&2
    exit 1
  fi

  gh api --method PUT "repos/${REPO}/branches/${branch}/protection" --input - <<JSON
{
  "required_status_checks": {
    "strict": true,
    "contexts": ${CONTEXTS}
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON
  echo "protected ${REPO}@${branch}"
done
