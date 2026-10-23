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
6. The developer creates an empty GitHub repository and gives the agent the URL. The agent sets `origin` and pushes `main`, `staging`, and `production`.
7. `scripts/bind-repo.sh` in the app is already filled in with the repository and production project. The developer runs it if they can change IAM. Otherwise they give that file to someone who can. The script lets GitHub Actions apply Terraform. It does not deploy, and it does not protect branches. `main` and `production` are covered by the organization ruleset. `staging` stays open so a push can deploy.
