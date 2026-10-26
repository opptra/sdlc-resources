---
title: Lifecycle
parent: Using it
nav_order: 2
---

# Lifecycle

`main` is the default branch and does not deploy. A direct push to `staging` deploys the shared staging project. `main` is not merged into `staging`. A pull request from `main` into `production` deploys the app's production project.

The steps for a person are [workflows.md](workflows.md), [new-app.md](new-app.md), [feature.md](feature.md), and [bug.md](bug.md). The same steps for an agent are the skills in [opptra/agent-skills](https://github.com/opptra/agent-skills). Start with the `opptra` skill when the sentence does not name one.

`service.yaml` is the only decision an app records. [../mapping.yaml](../mapping.yaml) and [../scripts/generate.py](../scripts/generate.py) turn those facts into the repo. GCP changes after that still go through Terraform, described in [resources.md](resources.md).
