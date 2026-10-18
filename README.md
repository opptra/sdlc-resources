# opptra/sdlc

The standard for how an Opptra app is set up, reviewed, and deployed.

`service.yaml` holds the facts: production project, region, and components. [mapping.yaml](mapping.yaml) decides the files, the CI, the deploy, and the agent rules. [scripts/generate.py](scripts/generate.py) applies that decision once. People do not hand-copy a hardcoded pipeline.

## Branches

`main` is the default branch. A feature pull request targets `main`. Merging to `main` does not deploy.

A push to `staging` deploys the shared staging project. `staging` has no pull request.

A merge into `production` deploys `prod_project` from `service.yaml`.

## Start here

| Path | Who it is for |
|---|---|
| [skills/create-app/SKILL.md](skills/create-app/SKILL.md) | The agent that scaffolds a new app |
| [skills/feature/SKILL.md](skills/feature/SKILL.md) | A Linear feature |
| [skills/bug/SKILL.md](skills/bug/SKILL.md) | A Linear bug |
| [docs/new-app.md](docs/new-app.md) | A person creating the GitHub repo |
| [docs/feature.md](docs/feature.md) | A person reviewing a feature |
| [docs/bug.md](docs/bug.md) | A person reviewing a bug |
| [docs/gcp-bootstrap.md](docs/gcp-bootstrap.md) | The one-time GCP setup |

Apps Script is not generated. If a description fits none of the archetypes, the create-app skill says so and stops.

## What the generator derives

| Facts in a component | Result |
|---|---|
| `ui` and `api` | FastAPI, Vite, a passing `/api/health` test, Python CI, frontend CI, Terraform plan, Cloud Run deploy |
| `api` | The same without the UI or frontend CI |
| `job` | A Python entrypoint, a passing test, Python CI, a deploy that updates the job and does not run it |
| `worker` | A worker, a passing test, Python CI, an image push that does not restart the VM |
| `config` | A README and a CI check. No deploy |
