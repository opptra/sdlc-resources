#!/usr/bin/env bash
# Require a pull request, one approval, and the CI check on staging and main.
# Usage: scripts/protect-branches.sh <org/repo>
# The check name GitHub shows for the reusable workflow is "ci / ci"
# unless CHECK_NAME is set to the name from a real pull request.

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: scripts/protect-branches.sh <org/repo>" >&2
  exit 2
fi

REPO="$1"
CHECK_NAME="${CHECK_NAME:-ci / ci}"

for branch in staging main; do
  if ! gh api "repos/${REPO}/branches/${branch}" >/dev/null 2>&1; then
    echo "${REPO} has no ${branch} branch. Push it, then run this script again." >&2
    exit 1
  fi

  gh api --method PUT "repos/${REPO}/branches/${branch}/protection" --input - <<JSON
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["${CHECK_NAME}", "plan / plan"]
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
  echo "protected ${REPO}@${branch} (required checks: ${CHECK_NAME}, plan / plan)"
done
