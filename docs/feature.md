# Feature

1. A person opens a Linear issue with acceptance criteria, or describes the feature and lets the `feature` skill create one issue after the plan is agreed.
2. The developer points the agent at the issue. The agent prints the route banner, including the skills commit and the generator commit, and waits for a yes before editing files.
3. The agent runs `python3 scripts/sdlc.py status --check` (when present) and reads `service.yaml` to load the active capabilities and rules. If the feature requires a new cloud resource, bucket, database, queue, or cron schedule, that change is routed to `change-app` in a separate pull request first.
4. Depth is `express` (one file: test and code, no OpenSpec), `standard` (OpenSpec, the default), or `migration` (a local plan already decided the shape). The agent branches from `main` as `feat/<ticket>-<short-slug>`.
5. On `standard` and `migration`, the agent writes an OpenSpec on that branch, syncs it to Linear, then implements only those tasks. On `express`, it writes the test and the code.
6. The agent writes `.sdlc/intent.yaml` after the plan is approved so a new chat resumes at the next step. It runs `.githooks/pre-commit` and `make ci`, then opens one pull request into `main`. The body has the Linear link, the OpenSpec path when there is one, the commands it ran, and the risk box.
7. CI and, when the app has Terraform, the plan run. Dobby comments. The developer reviews the spec and the code together.
8. The developer squash-merges. The message is `feat: <ticket> <short summary>`. `main` does not deploy.
9. To try the change in staging, the developer pushes that branch directly to `staging`. That deploys staging. There is no pull request, and `main` is not merged into `staging`.
10. The developer opens a pull request from `main` into `production` and merges it. That is the only deploy that comes from `main`.
11. The developer moves the Linear issue to Done.

Product code and changes to `infra/`, workflows, `config/jobs.yaml` schedules, or `service.yaml` are separate pull requests.
