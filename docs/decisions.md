# Decisions

These are the choices this draft implements. Reviewers who want to change one should say so on the pull request. The process sheet remains the status tracker. This repository is the source of the standard.

## Stack for a new app

Python 3.12, uv, Ruff, pytest, FastAPI. Vite, React, and TypeScript for the UI. One Docker image. FastAPI serves `/api` and the built UI on one Cloud Run service, so the browser and the API share an origin.

An existing app keeps its language. It still adopts the branches, the review rule, the agent rules, and the deploy workflow.

## Hosts

GCP only. New UI and API go on Cloud Run. A VM is only for a worker that cannot run as a request, such as a scraper or a browser. Postgres goes on Cloud SQL. Batch work is a Cloud Run Job, and shipping a new image does not start a backfill. Apps Script and config-only repos keep their host.

There is no Vercel path. `opptra-o2c` moves to Cloud Run when it is migrated.

## Environments

`staging` deploys the shared staging project. The project id in this draft is the placeholder `opptra-staging`. Production stays in the app's existing GCP project, named in `service.yaml` as `prod_project`.

## How code moves

`main` is the default branch. A feature branch is cut from `main` and the pull request targets `main`. Merging to `main` does not deploy.

A push of `main` onto `staging` deploys staging. `staging` is not a protected branch. A pull request from `main` into `production` deploys production on merge. One human approves. Dobby reviews every pull request and does not count as that approval.

A bad release is a revert through `main`, then `staging`, then `production`.

## CI

The required check is the reusable CI workflow. Ruff and the frontend lint always run. Pytest runs when `backend/tests` contains tests. The template ships with one health test, so a new app is covered from the first commit.

## Deploy mechanism

GitHub Actions reusable workflows in this repository. Workload Identity Federation. No service-account key in GitHub. The image is built on the GitHub runner and tagged with the git SHA. Artifact Registry repository name is `apps`.

Terraform is the only thing that creates, changes, or deletes GCP resources for an app. A pull request runs `terraform plan` and comments the add, change, and destroy list. The merge builds the image, plans again, and applies. Details are in [resources.md](resources.md).

## Auth

Each app records `auth` in `service.yaml`: `app-login`, `iap`, or `public`. The platform does not force one login.

## Agent rules

`rules/` in this repository is the source. Each app vendors `AGENTS.md` and `.cursor/rules`.

## Review of risky paths

CODEOWNERS adds the named owner when a diff touches `.github/workflows`, `service.yaml`, auth, billing, finance, or migrations. The placeholder team in the template is `@opptra/platform`. Replace it with a real team or with usernames before branch protection requires code owners.
