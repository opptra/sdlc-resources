# Example app

Replace this paragraph with what the app does. The rest is the Opptra standard. The source copy lives in `opptra/sdlc` under `rules/`.

This app deploys only through the GitHub workflows that call `opptra/sdlc`. Read `service.yaml` for the service name, archetype, production project, region, and auth.

## Branches

Branch off `staging`. Open a pull request into `staging`. Production is a later pull request from `staging` into `main`. Both branches are protected.

## Do not

- Add a `deploy.sh`, or any script, that runs `gcloud` against the production project.
- Commit a secret, a `.env` file, or a credential inside an image.
- Deploy an image tag other than the git SHA.
- Put Postgres, Redis, or the UI on a VM. A VM is only a worker that cannot run on Cloud Run.
- Introduce Next.js, a second frontend server, or a new language in a new app.

## Local

API: `uv run uvicorn app.main:app --app-dir backend --reload --port 8000`

UI: `cd frontend && npm run dev`

Vite proxies `/api` to port 8000.

## Rollback

Revert through `staging`, then `main`. The workflow deploys that commit.
