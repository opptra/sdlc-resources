---
title: New app
parent: Using it
nav_order: 3
---

# New app

The developer creates the GitHub repository. The agent scaffolds it in five phases (`check` → `init-runtime` → `add-data` → `add-tests` → `sync-infra`).

1. A person opens a Linear issue with the users, the outcome, the production GCP project, and who can sign in (and an optional migration or design plan in the folder).
2. The developer creates an empty `opptra/<name>` repository.
3. The developer runs the `create-app` skill. The skill reads the Linear issue and any local plan, shows the 17-point blueprint, and asks only what is still missing. If `.sdlc/state.yaml` already exists, it resumes the next phase.
4. If part of the request is outside the platform catalog, the skill records it under `unmet` in `service.yaml` with a recommendation and scaffolds everything else.
5. After the developer agrees, `create-app` runs the 5 phases using `scripts/sdlc.py`:
   - Phase 1 (`check`): Writes and validates `service.yaml`.
   - Phase 2 (`init-runtime`): Scaffolds the runtime skeleton and customizes the initial routes, job entrypoints, or UI layout.
   - Phase 3 (`add-data`): Installs the database/storage/queue/secret packages and customizes the state or schema helpers.
   - Phase 4 (`add-tests`): Sets up the test runner, writes unit tests for the scaffolded entrypoints and invariants, and verifies `ruff` and `pytest` / `npm test` pass.
   - Phase 5 (`sync-infra`): Deterministically generates `infra/`, `.github/workflows/`, `AGENTS.md`, `CLAUDE.md`, `.cursor/rules/*.mdc`, and `README.md`.
6. The developer gives the agent the repository URL from step 2. The agent sets `origin` and pushes `main`, `staging`, and `production`. The last phase records `generator_sha` in `.sdlc/state.yaml`.
7. Connect GitHub Actions to GCP. The checklist is [Bind a repository](bind.md). Neither script deploys the app, and neither protects branches. `main` and `production` are covered by the organization ruleset. `staging` stays open so a push can deploy.
   - A repository admin creates GitHub environments named `staging` and `production` under Settings → Environments. Add a required reviewer on `production` when the plan allows it. Then set the Actions variables the scripts print.
   - The developer runs `scripts/bind-staging.sh` when they can change IAM in `opptra-staging` and can read the pool in `opptra-sdlc-ci`. They run the two `gh variable set` commands that script prints. They do not need production access.
   - The developer sends `scripts/bind-production.sh` to someone who can change IAM in `prod_project`. That person runs it and runs the two production `gh variable set` commands it prints. They do not need access to `opptra-staging`. If they cannot set GitHub variables, they send those two commands back to a repository admin.
