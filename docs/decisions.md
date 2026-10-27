---
title: Decisions
parent: Platform
nav_order: 6
---

# Decisions

These are the choices this repository implements. Reviewers who want to change one should say so on the pull request.

## Stack for a new app

Python 3.12, uv, Ruff, pytest, FastAPI. Vite, React, and TypeScript for the UI. One Docker image per component. FastAPI serves `/api` and the built UI on one Cloud Run service, so the browser and the API share an origin. Scheduled jobs and an optional webhook receiver share one Docker image with per-workload commands.

An existing app keeps its language. It still adopts `service.yaml`, the branches, the required check, the agent rules, and the deploy workflow.

## Hosts and capabilities

GCP only. New UI and API go on Cloud Run (`cloud-run-service`). Batch and cron work runs on Cloud Run Jobs (`cloud-run-job` or `scheduled-jobs` when several jobs and an optional webhook receiver share one image), and shipping a new image does not start a run or backfill. A VM (`vm-worker`) is only for a worker that requires a persistent browser session, a long-lived process, or a local disk Cloud Run will not keep.

Data and platform capabilities are attached per component in `service.yaml`:
- `database: postgres` — Cloud SQL Postgres 16 with SQLAlchemy and Alembic
- `database: firestore` — IAM on the project's existing `(default)` Firestore Native database
- `bucket: private` — Private Cloud Storage bucket with uniform access
- `queue` — Cloud Tasks queue
- `secrets` — Secret Manager secret shells (values are never stored in Git or Terraform state)
- `alerts` — Log-based alert policy for failed job executions and unhandled `severity>=ERROR` logs

When a request includes something the platform does not yet generate, the supported parts are scaffolded and the gap is recorded under `unmet` in `service.yaml` with a recommendation.

## Environments

`staging` deploys the shared staging project (`opptra-staging`). Production stays in the app's existing GCP project, named in `service.yaml` as `prod_project`.

## How code moves

`main` is the default branch. A feature branch is cut from `main` and the pull request targets `main`. Merging to `main` does not deploy.

A direct push to `staging` deploys staging. `staging` is not a protected branch, so a developer can push there without the `main` review. Do not merge `main` into `staging`. A pull request from `main` into `production` is the only promotion from `main`, and that merge deploys production. One human approves. Dobby reviews every pull request and does not count as that approval.

Product code and changes to `infra/`, `.github/workflows`, `config/jobs.yaml` schedules, or `service.yaml` go in separate pull requests (`feature` / `bug` for product code, `change-app` for capabilities and schedules).

## CI

The required check is `ci` (plus `plan` when the app has Terraform). Ruff and frontend lint/tests run on every pull request, along with `pytest` when Python tests are present.

## Deploy mechanism

GitHub Actions reusable workflows in this repository. Workload Identity Federation through the pool `opptra-github` in `opptra-sdlc-ci`. No service-account key in GitHub. A staging workflow impersonates only the staging deployer. A production workflow impersonates only the production deployer. The image is built on the GitHub runner and tagged with the git SHA. Artifact Registry repository name is `apps`.

Terraform is the only thing that creates, changes, or deletes GCP resources for an app. A pull request runs `terraform plan` and comments the add, change, and destroy list. The merge builds the image, plans again, and applies. Details are in [resources.md](resources.md).

## Auth

Each callable service or receiver records `auth` in `service.yaml`: `iap` (Opptra staff), `app-login` (the app signs users in), `shared-secret` (webhook caller verified by header), or `public`. Jobs and workers use `none`.

## Agent rules

`rules/` in this repository is the source. `scripts/sdlc.py sync-infra` compiles `AGENTS.md`, `CLAUDE.md`, and `.cursor/rules/*.mdc` from the capabilities active in `service.yaml`.
