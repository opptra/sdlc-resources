# Start a new app

The template is a FastAPI service that serves a Vite build. Copy it into a new repository in the `opptra` organization.

## 1. Copy

```bash
mkdir my-app && cd my-app
cp -R /path/to/sdlc/template/. .
rm -rf frontend/node_modules frontend/dist .venv
git init
```

Edit `service.yaml`, `README.md`, `AGENTS.md`, and `CODEOWNERS`. Replace `@opptra/platform` with the team or people who must approve workflow and `service.yaml` changes.

`service.yaml`:

```yaml
name: my-app
archetype: cloud-run-service
prod_project: opptra-applications
region: asia-south1
auth: app-login
```

`prod_project` is the existing production project for this app. Staging always goes to `opptra-staging`.

Check the file:

```bash
/path/to/sdlc/scripts/check_manifest.py service.yaml
```

## 2. Run it locally

```bash
uv sync
uv run uvicorn app.main:app --app-dir backend --reload --port 8000
```

In another shell:

```bash
cd frontend
npm ci
npm run dev
```

Vite proxies `/api` to port 8000. Open the dev server URL and confirm the page shows API health `ok`.

## 3. Create the GitHub repository

Push `main`. Create `staging` from `main` and push it.

```bash
git checkout -b staging
git push -u origin main
git push -u origin staging
```

The caller workflows pin `opptra/sdlc` at `@v1`. Until that tag exists, a pilot may change the pin to `@main`.

The first deploy creates GitHub environments named `staging` and `production`. Leave them without a required reviewer. The pull request approval is the gate.

## 4. Protect the branches

From a checkout of `opptra/sdlc`, after the first CI run has posted its check:

```bash
scripts/protect-branches.sh opptra/my-app
```

The required check name defaults to `ci / ci`. If the pull request shows a different name, pass it:

```bash
CHECK_NAME="the name from the pull request" scripts/protect-branches.sh opptra/my-app
```

## 5. Let GitHub deploy

After [gcp-bootstrap.md](gcp-bootstrap.md) has been run:

```bash
scripts/bind-repo.sh opptra/my-app opptra-applications
```

The script prints the Actions variables. Set them on the app repository. The next merge to `staging` deploys `opptra-staging`. The next merge from `staging` to `main` deploys `prod_project`.

## 6. Secrets

Put runtime secrets in Secret Manager in the target project. Names are per app. The staging service reads staging secrets. It does not reference secret ids that end in `_PROD`. Wiring a secret into Cloud Run is a field we add when the first app needs one. Until then, do not commit a `.env` and do not bake a secret into the image.
