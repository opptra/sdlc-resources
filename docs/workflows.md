# How an Opptra app is created, changed, and fixed

The skills `create-app`, `feature`, and `bug` are already on each developer's machine. They come from `opptra/skills`, installed once. Those skills pull `opptra/sdlc` when they need the generator. Nobody keeps a checkout of `opptra/sdlc`.

`main` is the default branch and does not deploy. A direct push to `staging` deploys staging. Developers push there without a pull request. `main` is not merged into `staging`. A pull request from `main` into `production` deploys production.

## Prerequisites

| What | When | Who sets it up | Where it comes from |
|---|---|---|---|
| Staging GCP project, Workload Identity pool, state buckets, Artifact Registry repo `apps`, billing budgets | Once for the company | Platform owner | `docs/gcp-bootstrap.md` in `opptra/sdlc`. The project id in the draft is `opptra-staging`. |
| `opptra/sdlc` on GitHub `main` | Once for the company | Platform owner | This repo. New apps always use the latest `main`. |
| `opptra/skills` linked into Cursor and Claude | Once per person | Each developer | The skills repo. After that, `create-app`, `feature`, and `bug` work in every repo on that machine. |
| Linear issue | Every new app, feature, and bug | The person who wants the work | Linear. The issue names users, outcome, production project, and who can sign in. A bug also includes steps, expected result, and actual result. |
| Empty GitHub repo in `opptra` | Once per app | The developer | GitHub. The agent does not create it. |
| `main`, `staging`, and `production` branches | Once per app | The developer, after the generator has written the files | `staging` and `production` are created from `main`. |
| Branch protection and the GitHub deploy identity | Once per app | Platform owner | `scripts/protect-branches.sh` protects `main` and `production` only. `scripts/bind-repo.sh` creates the deployer account and prints four Actions variables. `staging` is left open so a push can deploy it. |
| Production GCP project | Already exists | Whoever owns that product | Named in the Linear issue and written into `service.yaml` as `prod_project`. |

## New app

```mermaid
flowchart TD
  A[Requester opens a Linear issue] --> B[Developer creates an empty opptra repo]
  B --> C[Developer asks the create-app skill and pastes the issue]
  C --> D[Skill recommends archetype and auth]
  D --> E{Developer agrees?}
  E -->|No, or nothing fits| F[Stop. No files written]
  E -->|Yes| G[Skill clones opptra/sdlc main, writes service.yaml, runs the generator]
  G --> H[Folder has code, passing tests, rules, and only the CI and deploy this app needs]
  H --> I[Developer pushes main and creates staging and production from main]
  I --> J[Platform owner protects main and production and binds GitHub to GCP]
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

A change to `infra/`, workflows, or `service.yaml` is a separate pull request. It is not mixed into the feature.

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
