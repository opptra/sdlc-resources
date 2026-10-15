# Lifecycle

This is the path for a new internal app, and the target for an existing one. Each step says what a person does and what this repository provides.

## 1. Requirements

Open a Linear issue before writing code. The issue says who uses the tool, what it does, which production GCP project it will live in, and how people sign in (`app-login`, `iap`, or `public`).

An app that wants an Openspec file keeps it in the repo. v1 does not install Openspec or call it from CI.

## 2. Planning

Linear is the planner. v1 does not automate Linear. The pull request template asks for the issue link. A production bug is a Linear issue on that app's project.

## 3. Create the repository

Copy [template/](../template/) and follow [new-app.md](new-app.md). Fill in `service.yaml`. The archetype for this template is `cloud-run-service`.

Other archetypes have a written rule and no workflow file yet:

| Archetype | Rule |
|---|---|
| `cloud-run-service` | This template. One image, one Cloud Run service. |
| `cloud-run-job` | A new image does not start a backfill. The job workflow is later. |
| `vm-worker` | The VM runs a scraper or browser worker. The UI and API stay on Cloud Run. Postgres goes on Cloud SQL. |
| `apps-script` | Clasp to a staging script, then clasp prod from `main` after review. |
| `config-only` | Pull request and lint. No deploy. |

## 4. Development

Branch off `staging`. Run the API and the UI locally as [the template README](../template/README.md) describes.

Cursor reads `AGENTS.md` and `.cursor/rules`, copied from [rules/](../rules/). The rules tell the agent:

- Deploy only through the reusable workflow.
- Do not add a script that deploys to production from a laptop.
- Do not commit a secret or bake one into an image.
- Tag images with the git SHA.
- Keep a pull request to one change. Split product code away from workflow or `service.yaml` changes.
- New UI code is Vite and React. New API code is FastAPI.

## 5. Pull request and CI

Open a pull request into `staging`. The app's CI workflow calls [ci.yml](../.github/workflows/ci.yml). The check runs Ruff, the frontend typecheck, and ESLint. It runs pytest when `backend/tests` contains `test_*.py` files. An old repo with no tests gets lint only, until the first test file arrives.

Direct pushes to `staging` and `main` are rejected after [scripts/protect-branches.sh](../scripts/protect-branches.sh).

## 6. Review

Dobby posts the brief in [dobby/review-brief.md](../dobby/review-brief.md) before a person is pinged. One human approval merges. CODEOWNERS adds the named owner on risky paths. Details are in [review.md](review.md).

## 7. Staging

Merge to `staging`. [deploy-cloud-run.yml](../.github/workflows/deploy-cloud-run.yml) builds the image tagged with the commit SHA, pushes it to Artifact Registry in `opptra-staging`, and deploys Cloud Run there. The job requests `/api/health` and fails if that is not 200. It comments the staging URL on the pull request.

The person who opens the promotion pull request opens that URL.

## 8. Production

Open a pull request from `staging` into `main`. Merge deploys the same workflow to `prod_project` from `service.yaml`. Traffic moves to the new revision. There is no second click in a GitHub Environment. The human approval already happened on the pull request.

Laptop `gcloud` and `deploy.sh` are not the deploy path.

## 9. Rollback

Revert the commit on a branch off `staging`, merge to `staging`, then promote to `main`. The pipeline deploys the reverted SHA.

## 10. Logging

The template logs JSON to stdout with `severity`, `message`, `service`, and `environment`. Cloud Run ingests that stream. There is no sidecar.

## 11. Alerts

After a service is deployed, add the three alerts in [alerting.md](alerting.md). One Slack channel per GCP project.

## 12. Usage

`frontend/src/analytics.ts` is a no-op. Product analytics stays out until someone runs a PostHog trial and lands the client in that file.

## Platform work that is not an app change

Creating `opptra-staging`, Workload Identity, budgets, and IAM is [gcp-bootstrap.md](gcp-bootstrap.md). Humans do not get deploy rights. GitHub deploys through Workload Identity Federation.
