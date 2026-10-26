# opptra/sdlc-resources

The standard for how an Opptra app is set up, aligned, changed, reviewed, and deployed.

`service.yaml` holds the facts: production project, region, workloads/components, capabilities, and any `unmet` platform gaps. [mapping.yaml](mapping.yaml) decides the files, the CI, the deploy, and the agent rules. [scripts/sdlc.py](scripts/sdlc.py) and [scripts/generate.py](scripts/generate.py) apply that decision in phases (`check`, `status`, `init-runtime`, `add-data`, `add-tests`, `sync-infra`). People do not hand-copy a hardcoded pipeline.

## Branches

`main` is the default branch. A feature pull request targets `main`. Merging to `main` does not deploy.

A direct push to `staging` deploys the shared staging project. `staging` has no pull request. `main` is not merged into `staging`.

A pull request from `main` into `production` deploys `prod_project` from `service.yaml`.

## Start here

| Path | Who it is for |
|---|---|
| [docs/workflows.md](docs/workflows.md) | Which skill to use. The same pages publish to GitHub Pages from `main`. |
| `opptra/agent-skills` (`opptra`, `create-app`, `change-app`, `align-app`, `feature`, `bug`) | The agent skills that drive the SDLC |
| [scripts/sdlc.py](scripts/sdlc.py) | Phase CLI (`check`, `status`, `init-runtime`, `add-data`, `add-tests`, `sync-infra`) |
| [docs/new-app.md](docs/new-app.md) | Creating a new app |
| [docs/align.md](docs/align.md) | Aligning an existing repository |
| [docs/feature.md](docs/feature.md) | Reviewing a feature |
| [docs/bug.md](docs/bug.md) | Reviewing a bug |
| [docs/gcp-bootstrap.md](docs/gcp-bootstrap.md) | The one-time GCP setup |

Apps Script is not generated. When a request includes needs outside the current catalog, the skill scaffolds all supported parts and records the gap under `unmet` with a recommendation.

## What the generator derives

| Facts | Result |
|---|---|
| `ui` and `api` (`staff-dashboard`) | FastAPI, Vite, passing `/api/health` and UI tests, Python CI, frontend CI, Terraform plan, Cloud Run deploy |
| `api` (`http-api`) | The same without the UI or frontend CI |
| `job` / `scheduled-jobs` | One image, one or many Cloud Run Jobs with per-job commands and Cloud Scheduler crons (enabled jobs only), optional `shared-secret` webhook receiver, passing runner tests |
| `worker` | A long-running VM worker, structured logging, a passing test, Python CI, an image push that does not restart the VM |
| `config` | A README and a CI check. No deploy |
| `database: postgres` | Cloud SQL Postgres 16, SQLAlchemy + Alembic (`db.py`), Secret Manager password, IAM |
| `database: firestore` | Default Firestore Native DB IAM, `firestore_state.py` (lease locks, heartbeats, idempotency, generation pointers) |
| `bucket: private` | Private GCS bucket (`<project>-<name>-assets`), uniform access, storage helper |
| `queue` | Cloud Tasks queue and enqueuer IAM |
| `secrets` | Secret Manager secret shells (no values in repo/state) and accessor IAM |
| `alerts` | Log-based alert policy for failed job runs / unhandled `severity>=ERROR` logs |
