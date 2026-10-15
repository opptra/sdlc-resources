# Migrate an existing repository

The language can stay. The contract is the branches, the required lint check, the agent rules, and deploy through the workflow. Do the steps in order. A later step depends on the earlier one having been used at least once.

## 1. Add the manifest and the callers

Add `service.yaml` at the repo root. Copy the caller workflows from [template/.github/workflows/](../template/.github/workflows/) and the pull request template. Copy `AGENTS.md` and `.cursor/rules/` from [rules/](../rules/) and edit the app name, archetype, and prod project.

Point `prod_project` at the project that already runs production. Do not move production projects as part of this step.

Protect `staging` and `main` with [scripts/protect-branches.sh](../scripts/protect-branches.sh) after CI has run once. Create `staging` from the current default branch if it does not exist.

## 2. Make lint a required check

The reusable CI workflow expects `pyproject.toml` and `frontend/` at the repo root, matching the template. An existing repo that is laid out differently should pass `working_directory` only if the whole app lives in one subdirectory. If Python and the UI are split in a way the workflow cannot see, change the caller to the layout and keep the check name stable. Ask in the `opptra/sdlc` review rather than inventing a second pipeline.

Repos with no tests pass `run_tests: false` until the first test file exists. After that, remove the input and let CI discover the tests.

Deploy is still the old path at the end of this step.

## 3. Staging

Run [scripts/bind-repo.sh](../scripts/bind-repo.sh) once `opptra-staging` exists. Merge to `staging` and confirm `/api/health` on the URL the workflow comments.

## 4. Production

Open the pull request from `staging` to `main`. Merge it. Confirm the Cloud Run revision in `prod_project` is the same commit SHA.

## 5. Remove the laptop path

Delete `deploy.sh` and any documented `gcloud run deploy` from a laptop. Move secrets to Secret Manager. A script that remains for emergencies must default to staging, must refuse to run against the prod project without an explicit flag, and is not the documented path.

## What this step does not include

Moving a MIG, leaving Vercel, or moving Postgres off a VM is a runtime change. It happens after the workflow is the only deploy path. Do not combine it with the first production deploy through GitHub.

## Pilot

Use a small app that is already Cloud Run. `finance-ops` and `github-mcp-server` fit. Catalog, SCM, and the warehouse VM paths are the wrong first proof, because they also need a runtime move.
