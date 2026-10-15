# opptra/sdlc

The standard for how an Opptra app is set up, reviewed, and deployed. This repository is the v1 draft for review. It is not tagged `v1` yet, and the shared staging project does not exist yet. Workflows use the placeholder project id `opptra-staging`.

People should read [docs/lifecycle.md](docs/lifecycle.md) first, then the doc for the task they have.

## What is in here

| Path | What it is |
|---|---|
| [docs/lifecycle.md](docs/lifecycle.md) | The path from a Linear issue to production |
| [docs/decisions.md](docs/decisions.md) | Choices already made, for reviewers |
| [docs/new-app.md](docs/new-app.md) | Copy the template and ship a new app |
| [docs/migrating.md](docs/migrating.md) | Bring an existing repo onto the pipeline |
| [docs/review.md](docs/review.md) | Dobby, human approval, CODEOWNERS |
| [docs/alerting.md](docs/alerting.md) | The three production alerts |
| [docs/gcp-bootstrap.md](docs/gcp-bootstrap.md) | Staging project, Workload Identity, budgets |
| [.github/workflows/ci.yml](.github/workflows/ci.yml) | Reusable lint and test workflow |
| [.github/workflows/deploy-cloud-run.yml](.github/workflows/deploy-cloud-run.yml) | Reusable Cloud Run deploy |
| [template/](template/) | FastAPI + Vite app that calls those workflows |
| [rules/](rules/) | Source copy of the agent rules |
| [dobby/review-brief.md](dobby/review-brief.md) | Spec for the comment Dobby should post |
| [scripts/protect-branches.sh](scripts/protect-branches.sh) | Protect `staging` and `main` |
| [scripts/bind-repo.sh](scripts/bind-repo.sh) | Let one GitHub repo deploy one app |
| [service.schema.json](service.schema.json) | Fields every `service.yaml` must have |

## What v1 deliberately leaves out

Cloud Run Job and VM worker workflows, Apps Script automation, release notes, PostHog, per-app Terraform, and a shared UI kit. The docs name the rule for those shapes. The workflow file comes later.

## Local check of the template

```bash
cd template
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest
cd frontend
npm ci
npm run lint
npm run typecheck
npm run build
```

## After this is on GitHub

1. Push this repository to `opptra/sdlc`.
2. Review the docs and the template.
3. Tag `v1` once the review is in. App workflows pin `@v1`. Until that tag exists, a pilot may pin `@main`.
4. Create the GCP project and follow [docs/gcp-bootstrap.md](docs/gcp-bootstrap.md).
5. Pilot one existing Cloud Run app. [docs/migrating.md](docs/migrating.md) names the order.
