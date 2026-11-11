Read the root `service.yaml` and the Product contract in `AGENTS.md`. Check `infra_management` and use `odlc status --json` to locate Terraform roots and the promotion workflow. Inspect the checked-in workflow and component manifests to confirm what CI reads. The ownership field takes precedence over bootstrap comments in generated files.

main is the default branch. Cut feature branches from main. Open the pull request into main. Merging to main does not deploy.

A direct push to staging deploys the staging project. Any developer may push there. Do not merge main into staging to release. Merging to main does not deploy. A pull request from main into production is the only promotion from main, and that merge deploys prod_project.

Do not add deploy.sh. Do not run gcloud run deploy. Do not commit a .env or a credential. Do not tag an image latest. Do not log secret values, bearer tokens, signed download URLs, or customer PII (email bodies, invoice text, phone numbers). Log ticket or record IDs, run IDs, and exit codes.

Prefix every external resource created in GCP or outside the repository—Cloud Run services and jobs, Cloud Scheduler entries, Cloud Tasks queues, Secret Manager secrets, Cloud Storage buckets, Cloud SQL instances, service accounts, and alert policies—with the app's `prefix` (or `name`) from `service.yaml` (`<prefix>-<resource>`). Never create unprefixed generic names such as `smtp`, `webhook`, `alerts`, or `default` in a shared GCP project.

With `infra_management: adoption` or `app-owned`, edit the relevant root under `infra/` or `<component>/infra/` and its environment inputs for resources, IAM, schedules, runtime variables, and secret references. Follow `.github/workflows/promotion.yml` or the repo's active deploy callers for Docker paths, state keys, and deployment triggers. Keep metadata and actual pipeline inputs in `service.yaml`. Trace readers before moving settings and give each setting one owner. When product code and infrastructure deliver one change, include both in the same PR. Use `change-app` for infrastructure-only work. A repo with generator ownership still uses its manifest and the separate infrastructure PR flow.

For a legacy deployment migration, follow `adopt-terraform`. During rehearsal, use `infra_management: adoption`, keep the current production deploy path active, and record the live inventory, legacy steps, and replacement in `docs/terraform-adoption.json`. The handoff PR changes the marker to `app-owned` after review resolves gaps and the replacement completes the full staging release. Run `odlc adoption-check --repo <owner/repository>` for the proposed handoff. Routine releases follow the active pipeline.

When the user asks for a change and does not name a skill, decide and follow one. A broken or incorrect behavior follows the bug skill. New product behavior follows the feature skill. Adding a database, bucket, queue, job, schedule, secret, or plain environment variable follows the change-app skill. Do not wait for /feature, /bug, or /change-app.

Set runtime variables and secret references before the code that consumes them. Do not ask the user to name a skill or to run a script. During adoption and after handoff, declare the plain value or Secret Manager ID in Terraform and document the variable name in `.env.example` with a placeholder for secrets. In generator-owned repos, declare these in the component's `env` and `secrets` fields in `service.yaml`, validate the manifest, and run the pinned sync. Keep secret values in Secret Manager and local development values in the ignored `.env`. Product code reads plain values with `get_env` and secrets with `get_secret`.

Plan with the user before creating a Linear issue. Do not create a new Linear ticket on every prompt while still discussing or refining the plan. Check the current Git branch (`feat/<ticket-id>-...`, `fix/<ticket-id>-...`, `infra/<ticket-id>-...`) first:
- If a ticket branch is already checked out and the new ask is related to that same ticket, reuse that Linear issue, append the new requirements and OpenSpec updates when they are not already on the issue, and implement on the current branch.
- If a ticket branch is checked out and it is unclear whether the new ask belongs to that ticket or is a separate task, ask the user whether to add it to the existing Linear issue or switch to `main` and create or use a new Linear issue.
- If on `main` and the user gave a ticket id, read that Linear issue.
- If on `main` with no ticket id given, agree on the overall plan with the user first, then create one Linear issue and push the agreed requirements, acceptance criteria, and OpenSpec summary to that Linear issue. Do not invent a ticket id.

Branch names are feat/<ticket-id>-<short-slug> for a feature, fix/<ticket-id>-<short-slug> for a bug, and infra/<ticket-id>-<short-slug> for a capability or schedule change.

Commit messages are feat: <ticket-id> <short summary>, fix: <ticket-id> <short summary>, or infra: <ticket-id> <short summary>.

Every pull request links the Linear issue.

A feature writes an OpenSpec under openspec/ before any product code and syncs the spec summary to the Linear issue. The pull request includes that path. A bug writes an OpenSpec only when the fix needs a product or design choice.

Use the recorded generator for bootstrap. After handoff, `odlc sync` only refreshes managed agent rules. When the recorded generator predates handoff, use the updated CLI with `odlc sync --upgrade` once, after committing the ownership marker to the app branch. Check the resulting rules diff.

After the pull request into main is open, print the ship card: the command `git push --force-with-lease origin <branch>:staging`, that main is not merged into staging, and that production is a pull request from main into production. Push staging only when the developer asks. A rollback is a revert on main, then the same card. Do not redeploy an older image.

Use a two-gate confirmation flow:
1. **Plan / Spec Gate:** Before editing product files, present the plan (plus the OpenSpec summary for a feature, or root cause and failing reproduction test for a bug) and wait for a yes.
2. **Ship Gate:** After implementation, run `.githooks/pre-commit` and `make ci` automatically until green, then show the commit message, file list, branch name, and pull request title/body together in one prompt and wait for a yes before committing, pushing, and opening the pull request. Never pass `--no-verify` to `git commit` or `git push`.

Run `.githooks/pre-commit` and `make ci` for bootstrap and app changes. If image wiring fails in a generator-owned repo, fix `path`, `docker_context`, or `dockerfile` in the manifest and regenerate. During adoption and after handoff, follow the active workflow's build inputs and update its matching local build command if necessary. Use `BUILD_CONTEXT` for shell scripts. `DOCKER_CONTEXT` is reserved by Docker.

Done means `.githooks/pre-commit`, `make ci`, and the test command for each part you touched have been run and passed.
