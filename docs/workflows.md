---
title: Which skill
parent: Using it
nav_order: 1
---

# How an Opptra app is created, changed, and fixed

The skills are already on each developer's machine. They come from `opptra/agent-skills`, installed once. Those skills clone `opptra/sdlc-resources` `main` when they need the generator and record that commit as `generator_sha` in `.sdlc/state.yaml`. Nobody keeps a checkout of `opptra/sdlc-resources`.

If the sentence does not name a skill, use `opptra`. It only picks the route:

| Ask | Skill |
|---|---|
| New repository | `create-app` |
| Existing repository onto this standard | `align-app` |
| `deploy.sh`, Cloud Build, Vercel, or manual GCP onto Terraform | `adopt-terraform` |
| Database, bucket, queue, secret, job, cron, region, or workload | `change-app` |
| New product behavior | `feature` |
| Broken or incorrect behavior | `bug` |

A capability change and a product change are two pull requests. `change-app` goes first. A feature is `express` when it is one file (test and pull request, no OpenSpec), `standard` when it needs an OpenSpec, or `migration` when a local plan already decided the shape. After the plan is approved, `feature` and `bug` write `.sdlc/intent.yaml` so a new chat continues. That directory is gitignored.

`main` is the default branch and does not deploy. A direct push to `staging` deploys staging. Developers push there without a pull request. `main` is not merged into `staging`. A pull request from `main` into `production` deploys production.

## Prerequisites

| What | When | Who sets it up | Where it comes from |
|---|---|---|---|
| Identity project `opptra-sdlc-ci` and the Workload Identity pool `opptra-github` | Once for the company | Platform owner | [gcp-bootstrap.md](gcp-bootstrap.md). The pool already exists. Do not create a second one. |
| Staging project `opptra-staging`, state buckets, Artifact Registry repo `apps`, billing budgets | Once for the company | Platform owner | [gcp-bootstrap.md](gcp-bootstrap.md). |
| `opptra/sdlc-resources` on GitHub `main` | Once for the company | Platform owner | This repo. A phase records the commit it ran as `generator_sha`. |
| `opptra/agent-skills` linked into Cursor and Claude | Once per person | Each developer | The skills repo. `fetch-skill` updates them. The route banner prints that commit. |
| Linear issue | Every new app, feature, and bug | The person who wants the work | Linear. The issue names users, outcome, production project, and who can sign in. A bug also includes steps, expected result, and actual result. |
| Empty GitHub repo in `opptra` | Once per app | The developer | GitHub. The agent does not create it. |
| `main`, `staging`, and `production` branches | Once per app | The developer, after the generator has written the files | `staging` and `production` are created from `main`. |
| GitHub environments `staging` and `production`, and the four Actions variables | Once per app | Repository admin | [bind.md](bind.md). Add a required reviewer on `production` when the plan allows it. |
| Staging deployer | Once per app | Developer, when they can change IAM in `opptra-staging` | Run `scripts/bind-staging.sh`, then the two `gh variable set` commands it prints. |
| Production deployer | Once per app | Someone who can change IAM in `prod_project` | The developer sends them `scripts/bind-production.sh`. They run it and set the two production variables. |
| Branch protection | Once per app | Platform owner | An organization ruleset protects `main` and `production`. `staging` is left open so a push can deploy it. |
| Production GCP project | Already exists | Whoever owns that product | Named in the Linear issue and written into `service.yaml` as `prod_project`. |

## New app

```mermaid
flowchart TD
  A[Requester opens a Linear issue] --> B[Developer creates an empty opptra repo]
  B --> C[Developer asks the create-app skill and pastes the issue]
  C --> D[Skill recommends archetype and auth]
  D --> E{Developer agrees?}
  E -->|No, or nothing fits| F[Stop. No files written]
  E -->|Yes| G[Skill clones opptra/sdlc-resources main, writes service.yaml, runs the generator]
  G --> H[Folder has code, passing tests, rules, and only the CI and deploy this app needs]
  H --> I[Developer pushes main and creates staging and production from main]
  I --> J[Admin creates GitHub environments. Developer binds staging. Production bind goes to someone with production IAM]
  J --> K[App is ready. First product change is a feature]
```

The health check or entrypoint test is already green. Nothing has deployed yet.

## New feature

```mermaid
flowchart TD
  A[Requester opens a Linear issue with acceptance criteria] --> B[Developer points the feature skill at the ticket]
  B --> C["Agent branches from main: feat/TICKET-short-slug"]
  C --> D[Agent writes an OpenSpec, then implements only those tasks]
  D --> E[Agent runs the tests for each part it touched]
  E --> F[Agent opens one pull request into main]
  F --> G[GitHub runs CI and, if needed, comments a staging Terraform plan]
  G --> H[Dobby posts the review brief]
  H --> I[Developer reviews spec and code, approves, squash-merges]
  I --> J["Commit on main: feat: TICKET summary. main does not deploy"]
  J --> K[Developer pushes the feature branch directly to staging]
  K --> L[GitHub builds the image, pushes it, applies Terraform in the staging project]
  L --> M[Developer opens the staging URL]
  M --> N[Developer opens a pull request from main into production]
  N --> O[GitHub plans the production project. Dobby comments]
  O --> P[Developer merges. GitHub deploys production]
  P --> Q[Developer moves the Linear issue to Done]
```

A change to `infra/`, workflows, or `service.yaml` is a `change-app` pull request. It is not mixed into the feature. `express` skips the OpenSpec and still opens one pull request into `main`.

A deploy that mounts secrets creates the Secret Manager shells first. If a mounted secret has no version, the action stops and lists the ids. Add a version in Secret Manager and re-run the workflow. The value is not committed. Cloud Run mounts `latest` on that next run.

Those checks are `scripts/check_secret_versions.py` and `scripts/check_firestore.py` in the app repository. The deploy checks out the app, so the files have to be there. `init-runtime` and `sync-infra` copy them from this repository, next to `render_tfvars.py` and `yaml_subset.py`.

An app with `database: firestore` creates one Native `(default)` database in the app region when the project has none. The next app in that project finds it and does not create another. A database that is not Native, or that is in a different region from `service.yaml`, stops the deploy. The deployer needs `roles/datastore.owner` from `scripts/bind-staging.sh` or `scripts/bind-production.sh`. Terraform only grants the runtime account access, so the database is not stored in an app's state.

## Bug

```mermaid
flowchart TD
  A[Requester opens a Linear issue with steps, expected, and actual] --> B{Does the fix need a product or design choice?}
  B -->|Yes| C[Use the feature flow, including an OpenSpec]
  B -->|No| D[Developer points the bug skill at the ticket]
  D --> E["Agent branches from main: fix/TICKET-short-slug"]
  E --> F[Agent writes a test that fails, then the fix]
  F --> G[Agent opens one pull request into main with the reproduction and the test name]
  G --> H[GitHub runs CI and the plan. Dobby comments. Nothing deploys]
  H --> I[Developer approves and squash-merges]
  I --> J["Commit on main: fix: TICKET summary"]
  J --> K[Developer pushes the fix branch directly to staging and checks the URL]
  K --> L[Developer opens a pull request from main into production]
  L --> M[Production deploys. Developer moves the issue to Done]
```

A production bug uses this same path. Staging is a direct push, not a merge from `main`. A rollback is a revert merged to `main`, then a pull request into `production`. The revert branch can also be pushed straight to `staging`. It is not a button that redeploys an older image.
