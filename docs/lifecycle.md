---
title: Lifecycle
parent: Using it
nav_order: 2
---

# Lifecycle

`main` is the default branch and does not deploy. Apps with deployment IAM open a reviewed candidate PR into `staging`. Legacy callers deploy staging on push. Production always uses a PR from `main` into `production`. See [promotion and approvals](infra-handoff.md#deployment-iam-in-the-feature-pr).

The steps for a person are [workflows.md](workflows.md), [new-app.md](new-app.md), [feature.md](feature.md), and [bug.md](bug.md). The same steps for an agent are the skills in [opptra/agent-skills](https://github.com/opptra/agent-skills). Start with the `opptra` skill when the sentence does not name one.

`service.yaml` is the only decision an app records. [../mapping.yaml](../mapping.yaml) and [../scripts/generate.py](../scripts/generate.py) turn those facts into the repo. GCP changes after that still go through Terraform, described in [resources.md](resources.md).
