---
title: Align
parent: Using it
nav_order: 6
---

# Align an existing repository

`align-app` in `opptra/agent-skills` runs `odlc status` against the open repository and offers three paths. The developer says yes once. The 17-point scorecard still prints. It is the receipt, not a checklist of 17 decisions.

| Path | What happens |
|---|---|
| Ship today | No files. The next step is `feature` or `bug`. |
| Make the agent safe | The **Adopt now** list below. If `deploy.sh`, `vercel.json`, or `fly.toml` is present, CI is generated and that deploy path stays. |
| Move the host | `adopt-terraform` in the same chat. `deploy.sh` stays until the first production Terraform apply has succeeded. |

A bug on a repository that has never been aligned still uses `bug`. Alignment is not required to merge that fix.

Apps Script is unsupported. Report it and leave the repository unchanged.

## 1. Adopt now (safe, no host move)

- `service.yaml` at the repo root, with `name`, `purpose`, `prod_project`, `region`, `components` (or `workloads` / `capabilities`), and any `unmet` items.
- `.gitignore` and `.github/CODEOWNERS` when missing.
- `AGENTS.md`, `CLAUDE.md`, and `.cursor/rules/*.mdc` compiled from `rules/source/` for the active capabilities (`always`, plus `python`, `react`, `terraform`, `job`, `worker`, `config`, `database`, or `firestore`).
- `README.md` with the purpose, local run commands, test commands, any `unmet` platform recommendations, and the deploy steps.
- A pull-request-only `.github/workflows/ci.yml` calling `opptra/sdlc-resources` at `main`.
- Branches `main`, `staging`, and `production` when missing. `main` is the default and does not deploy. `staging` stays unprotected. `production` is protected by the organization ruleset, not by a script the developer runs.
- `scripts/bind-staging.sh` and `scripts/bind-production.sh` when the app deploys. They are filled in from `service.yaml`. The developer runs the staging script. They send the production script to someone who can change IAM in `prod_project`. The steps are in [bind.md](bind.md). Running either script grants GitHub Actions a deployer account. It does not deploy and it does not protect branches.

Do not delete the current deploy path during **Adopt now**.

## 2. Fill capability gaps (phased scripts + skill)

When `odlc status --json` detects code using a capability that is missing its standard wiring or tests:
- Run `odlc add-data` to add missing DB/Firestore/storage/secret helpers.
- Run `odlc add-tests` to add missing entrypoint/health tests and local fixtures.
- Run `odlc sync-infra` when the developer approves generating `infra/` and workflows.

## 3. Later recommendations

Research each item that matches, cite the files found, state what the standard would do, and record any platform gap under `unmet` in `service.yaml`. Applying one of these later is a dedicated pull request via `change-app` or `feature`.
