Read the root service.yaml before you change infra, workflows, or deploy settings. Archetype, workloads, auth, capabilities, and parts come from that file.

main is the default branch. Cut feature branches from main. Open the pull request into main. Merging to main does not deploy.

A direct push to staging deploys the staging project. Any developer may push there. Do not merge main into staging to release. Merging to main does not deploy. A pull request from main into production is the only promotion from main, and that merge deploys prod_project.

Do not add deploy.sh. Do not run gcloud run deploy. Do not commit a .env or a credential. Do not tag an image latest.

Prefix every external resource created in GCP or outside the repository—Cloud Run services and jobs, Cloud Scheduler entries, Cloud Tasks queues, Secret Manager secrets, Cloud Storage buckets, Cloud SQL instances, service accounts, and alert policies—with the app's `prefix` (or `name`) from `service.yaml` (`<prefix>-<resource>`). Never create unprefixed generic names such as `smtp`, `webhook`, `alerts`, or `default` in a shared GCP project.

Product code and changes to infra, .github/workflows, config/jobs.yaml schedules, or service.yaml go in separate pull requests. Use the change-app skill when adding or modifying a capability, workload, or schedule.

When the user asks for a change and does not name a skill, decide and follow one. A broken or incorrect behavior follows the bug skill. New product behavior follows the feature skill. Adding a database, bucket, queue, job, or schedule follows the change-app skill. Do not wait for /feature, /bug, or /change-app.

Plan with the user before creating a Linear issue. Do not create a new Linear ticket on every prompt while still discussing or refining the plan. Check the current Git branch (`feat/<ticket-id>-...`, `fix/<ticket-id>-...`, `infra/<ticket-id>-...`) and `.sdlc/state.yaml` first:
- If a ticket branch is already checked out and the new ask is related to that same ticket, reuse that Linear issue, append the new requirements and OpenSpec updates to the existing Linear issue, and implement on the current branch.
- If a ticket branch is checked out and it is unclear whether the new ask belongs to that ticket or is a separate task, ask the user whether to add it to the existing Linear issue or switch to `main` and create/use a new Linear issue.
- If on `main` with no ticket ID given, agree on the overall plan with the user first, then create one Linear issue and push the agreed requirements, acceptance criteria, and OpenSpec summary to that Linear issue. Do not invent a ticket id.

Branch names are feat/<ticket-id>-<short-slug> for a feature, fix/<ticket-id>-<short-slug> for a bug, and infra/<ticket-id>-<short-slug> for a capability or schedule change.

Commit messages are feat: <ticket-id> <short summary> or fix: <ticket-id> <short summary>.

Every pull request links the Linear issue.

A feature writes an OpenSpec under openspec/ before any product code and syncs the spec summary to the Linear issue. The pull request includes that path. A bug writes an OpenSpec only when the fix needs a product or design choice.

Before you edit files, tell the developer what you will change and wait for a yes. Before a commit, run `.githooks/pre-commit` and `make ci`, show the message and the file list, and wait. Before a push or a pull request, show the branch, title, and body and wait. Never pass `--no-verify` to `git commit` or `git push`.

During `create-app` or `align-app`, run `.githooks/pre-commit` and `make ci` after generating files. Fix any auto-resolvable lint, formatting, or wiring errors automatically. If a check fails due to something that cannot be resolved without user input, explain the exact failure and ask the user whether to provide the input or disable that specific check (`run_tests: false` or `run_lint: false`) in `service.yaml`.

Done means `.githooks/pre-commit`, `make ci`, and the test command for each part you touched have been run and passed.
