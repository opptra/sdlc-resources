# New app

The developer creates the GitHub repository. The agent scaffolds it in five phases (`check` → `init-runtime` → `add-data` → `add-tests` → `sync-infra`).

1. A person opens a Linear issue with the users, the outcome, the production GCP project, and who can sign in (and an optional migration or design plan in the folder).
2. The developer creates an empty `opptra/<name>` repository.
3. The developer runs the `create-app` skill. The skill reads the Linear issue and any local plan, infers the preset/workloads, data store (`postgres`, `firestore`, or `none`), storage bucket, queue, secrets, and auth, and asks only what is still missing.
4. If part of the request is outside the platform catalog, the skill records it under `unmet` in `service.yaml` with a recommendation and scaffolds everything else.
5. After the developer agrees, `create-app` runs the 5 phases using `scripts/sdlc.py`:
   - Phase 1 (`check`): Writes and validates `service.yaml`.
   - Phase 2 (`init-runtime`): Scaffolds the runtime skeleton and customizes the initial routes, job entrypoints, or UI layout.
   - Phase 3 (`add-data`): Installs the database/storage/queue/secret packages and customizes the state or schema helpers.
   - Phase 4 (`add-tests`): Sets up the test runner, writes unit tests for the scaffolded entrypoints and invariants, and verifies `ruff` and `pytest` / `npm test` pass.
   - Phase 5 (`sync-infra`): Deterministically generates `infra/`, `.github/workflows/`, `AGENTS.md`, `CLAUDE.md`, `.cursor/rules/*.mdc`, and `README.md`.
6. The developer pushes `main` and creates `staging` and `production` from `main`.
7. A platform owner runs `scripts/protect-branches.sh` and `scripts/bind-repo.sh`. Protection covers `main` and `production` only. For an app with Terraform, set `PLAN_CHECK=plan`.
