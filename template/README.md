# Example app

Copy of the Opptra template. Replace this page with what the app does, who uses it, and the production project from `service.yaml`.

## Local

```bash
uv sync
uv run uvicorn app.main:app --app-dir backend --reload --port 8000
```

```bash
cd frontend
npm ci
npm run dev
```

The Vite server proxies `/api` to `http://127.0.0.1:8000`.

## Checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
cd frontend && npm run lint && npm run typecheck
```

## Deploy

Merging to `staging` deploys `opptra-staging`. Merging `staging` into `main` deploys `prod_project` from `service.yaml`. Both go through `opptra/sdlc`. See that repository's `docs/new-app.md`.
