Read the root service.yaml before you change infra, workflows, or deploy settings. Archetype, workloads, auth, capabilities, and parts come from that file.

main is the default branch. Cut feature branches from main. Open the pull request into main. Merging to main does not deploy.

A direct push to staging deploys the staging project. Any developer may push there. Do not merge main into staging to release. Merging to main does not deploy. A pull request from main into production is the only promotion from main, and that merge deploys prod_project.

Do not add deploy.sh. Do not run gcloud run deploy. Do not commit a .env or a credential. Do not tag an image latest. Do not log secret values, bearer tokens, signed download URLs, or customer PII (email bodies, invoice text, phone numbers). Log ticket or record IDs, run IDs, and exit codes.

Prefix every external resource created in GCP or outside the repository—Cloud Run services and jobs, Cloud Scheduler entries, Cloud Tasks queues, Secret Manager secrets, Cloud Storage buckets, Cloud SQL instances, service accounts, and alert policies—with the app's `prefix` (or `name`) from `service.yaml` (`<prefix>-<resource>`). Never create unprefixed generic names such as `smtp`, `webhook`, `alerts`, or `default` in a shared GCP project.

Product code and changes to infra, .github/workflows, config/jobs.yaml schedules, or service.yaml go in separate pull requests. Use the change-app skill when adding or modifying a capability, workload, or schedule.

When the user asks for a change and does not name a skill, decide and follow one. A broken or incorrect behavior follows the bug skill. New product behavior follows the feature skill. Adding a database, bucket, queue, job, schedule, secret, or plain environment variable follows the change-app skill. Do not wait for /feature, /bug, or /change-app.

When the work needs a value the process reads from the environment, place it yourself before any product code. Do not ask the user to name a skill or to run a script. Classify each value. A key, password, or token goes in `secrets` on the component, job, or receiver that reads it. Commit the name only. A domain, port, email address, list of emails, or flag goes in the component `env` map. A list is one comma-separated string, and the value is committed. Edit the root `service.yaml`, then run `check` and `sync-infra` from `opptra/sdlc-resources`. Leave `infra/`, `.env.example`, and the workflows to that script. `sync-infra` writes `plain_env` and the secret mounts into `infra/main.tf`, and writes both kinds of names into `.env.example`. Secret lines there stay `replace-me`. This `service.yaml` edit is its own pull request on `infra/<ticket-id>-<short-slug>`, opened before the product pull request. Stay in the same chat. Do not send the developer away. After opening the `infra/<ticket-id>-<short-slug>` pull request, you may immediately cut `feat/<ticket-id>-<short-slug>` (or `fix/<ticket-id>-<short-slug>`) stacked on top of that infra branch so the developer can write and test product code locally right away, then rebase onto `main` once the infra pull request merges. Product code reads a plain value with `get_env` and a secret with `get_secret`. A local secret value goes in `.env` only. After deploy, add a missing secret version in Secret Manager for that project and re-run the workflow.

Plan with the user before creating a Linear issue. Do not create a new Linear ticket on every prompt while still discussing or refining the plan. Check the current Git branch (`feat/<ticket-id>-...`, `fix/<ticket-id>-...`, `infra/<ticket-id>-...`) first:
- If a ticket branch is already checked out and the new ask is related to that same ticket, reuse that Linear issue, append the new requirements and OpenSpec updates when they are not already on the issue, and implement on the current branch.
- If a ticket branch is checked out and it is unclear whether the new ask belongs to that ticket or is a separate task, ask the user whether to add it to the existing Linear issue or switch to `main` and create or use a new Linear issue.
- If on `main` and the user gave a ticket id, read that Linear issue.
- If on `main` with no ticket id given, agree on the overall plan with the user first, then create one Linear issue and push the agreed requirements, acceptance criteria, and OpenSpec summary to that Linear issue. Do not invent a ticket id.

Branch names are feat/<ticket-id>-<short-slug> for a feature, fix/<ticket-id>-<short-slug> for a bug, and infra/<ticket-id>-<short-slug> for a capability or schedule change.

Commit messages are feat: <ticket-id> <short summary>, fix: <ticket-id> <short summary>, or infra: <ticket-id> <short summary>.

Every pull request links the Linear issue.

A feature writes an OpenSpec under openspec/ before any product code and syncs the spec summary to the Linear issue. The pull request includes that path. A bug writes an OpenSpec only when the fix needs a product or design choice.

Run sync-infra from the recorded generator commit. Clone main of opptra/sdlc-resources only when no generator commit is recorded, or the developer asks to upgrade the generator.

After the pull request into main is open, print the ship card: the command `git push --force-with-lease origin <branch>:staging`, that main is not merged into staging, and that production is a pull request from main into production. Push staging only when the developer asks. A rollback is a revert on main, then the same card. Do not redeploy an older image.

Use a two-gate confirmation flow:
1. **Plan / Spec Gate:** Before editing product files, present the plan (plus the OpenSpec summary for a feature, or root cause and failing reproduction test for a bug) and wait for a yes.
2. **Ship Gate:** After implementation, run `.githooks/pre-commit` and `make ci` automatically until green, then show the commit message, file list, branch name, and pull request title/body together in one prompt and wait for a yes before committing, pushing, and opening the pull request. Never pass `--no-verify` to `git commit` or `git push`.

During `create-app` or `align-app`, run `.githooks/pre-commit` and `make ci` after generating files. Fix any auto-resolvable lint, formatting, or wiring errors automatically. If a check fails due to something that cannot be resolved without user input, explain the exact failure and ask the user whether to provide the input or disable that specific check (`run_tests: false` or `run_lint: false`) in `service.yaml`.

Done means `.githooks/pre-commit`, `make ci`, and the test command for each part you touched have been run and passed.
