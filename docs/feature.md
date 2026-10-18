# Feature

1. A person opens a Linear issue with acceptance criteria.
2. The developer points the agent at the issue.
3. The agent branches from `main` as `feat/<ticket>-<short-slug>`.
4. The agent writes an OpenSpec on that branch, then implements only those tasks.
5. The agent opens one pull request into `main`. The body has the Linear link, the OpenSpec path, the commands it ran, and the risk box.
6. CI and, when the app has Terraform, the plan run. Dobby comments. The developer reviews the spec and the code together.
7. The developer squash-merges. The message is `feat: <ticket> <short summary>`. `main` does not deploy.
8. The developer pushes `main` onto `staging`. That deploys staging. There is no pull request. They open the URL.
9. The developer opens a pull request from `main` into `production` and merges it. That deploys production.
10. The developer moves the Linear issue to Done.

Product code and changes to `infra/`, workflows, or `service.yaml` are separate pull requests.
