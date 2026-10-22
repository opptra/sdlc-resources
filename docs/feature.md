# Feature

1. A person opens a Linear issue with acceptance criteria.
2. The developer points the agent at the issue.
3. The agent runs `python3 scripts/sdlc.py status --check` (when present) and reads `service.yaml` to load the active capabilities and rules. If the feature requires a new cloud resource, bucket, database, queue, or cron schedule, that change is routed to `change-app` in a separate pull request first.
4. The agent branches from `main` as `feat/<ticket>-<short-slug>`.
5. The agent writes an OpenSpec on that branch, then implements only those tasks.
6. The agent runs the test and lint gates for every component touched, then opens one pull request into `main`. The body has the Linear link, the OpenSpec path, the commands it ran, and the risk box.
7. CI and, when the app has Terraform, the plan run. Dobby comments. The developer reviews the spec and the code together.
8. The developer squash-merges. The message is `feat: <ticket> <short summary>`. `main` does not deploy.
9. The developer pushes `main` onto `staging`. That deploys staging. There is no pull request.
10. The developer opens a pull request from `main` into `production` and merges it. That deploys production.
11. The developer moves the Linear issue to Done.

Product code and changes to `infra/`, workflows, `config/jobs.yaml` schedules, or `service.yaml` are separate pull requests.
