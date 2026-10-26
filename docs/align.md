---
title: Align
parent: Using it
nav_order: 6
---

# Align an existing repository

`align-app` in `opptra/agent-skills` runs `scripts/sdlc.py status --json` against the open repository, compares it with the standard, and presents three sections: **Adopt now**, **Fill capability gaps**, and **Later recommendations**. It applies only the items the developer accepts.

Apps Script is unsupported. Report it and leave the repository unchanged.

## 1. Adopt now (safe, no host move)

- `service.yaml` at the repo root, with `name`, `purpose`, `prod_project`, `region`, `components` (or `workloads` / `capabilities`), and any `unmet` items.
- `.gitignore` and `.github/CODEOWNERS` when missing.
- `AGENTS.md`, `CLAUDE.md`, and `.cursor/rules/*.mdc` compiled from `rules/source/` for the active capabilities (`always`, plus `python`, `react`, `terraform`, `job`, `worker`, `config`, `database`, or `firestore`).
- `README.md` with the purpose, local run commands, test commands, any `unmet` platform recommendations, and the deploy steps.
- A pull-request-only `.github/workflows/ci.yml` calling `opptra/sdlc-resources` at `main`.
- Branches `main`, `staging`, and `production` when missing. `main` is the default and does not deploy. `staging` stays unprotected. `production` is protected by the organization ruleset, not by a script the developer runs.
- `scripts/bind-repo.sh` when the app deploys. It is filled in from `service.yaml`. Running it grants GitHub Actions a deployer account. It does not deploy and it does not protect branches.

Do not delete the current deploy path during **Adopt now**.

## 2. Fill capability gaps (phased scripts + skill)

When `sdlc.py status --json` detects code using a capability that is missing its standard wiring or tests:
- Run `sdlc.py add-data` to add missing DB/Firestore/storage/secret helpers.
- Run `sdlc.py add-tests` to add missing entrypoint/health tests and local fixtures.
- Run `sdlc.py sync-infra` when the developer approves generating `infra/` and workflows.

## 3. Later recommendations

Research each item that matches, cite the files found, state what the standard would do, and record any platform gap under `unmet` in `service.yaml`. Applying one of these later is a dedicated pull request via `change-app` or `feature`.
