---
title: GCP bootstrap
parent: Platform
nav_order: 2
---

# GCP bootstrap

Do this once, before any app deploys through the workflow. The project id in the workflows is `opptra-staging`. If the real id differs, change the default input `staging_project` on [deploy-cloud-run.yml](../.github/workflows/deploy-cloud-run.yml) and the default `STAGING_PROJECT` in [scripts/bind-staging.sh](../scripts/bind-staging.sh).

Per-app GitHub setup and the two bind scripts are in [bind.md](bind.md). This page is the company-wide GCP setup.

Production projects stay as they are. This page does not merge them.

## 1. Create the staging project

Create a GCP project, attach billing, and name it `opptra-staging` unless you are changing the placeholder everywhere.

## 2. Enable APIs on the staging project

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  iamcredentials.googleapis.com \
  iam.googleapis.com \
  cloudresourcemanager.googleapis.com \
  iap.googleapis.com \
  storage.googleapis.com \
  sqladmin.googleapis.com \
  --project=opptra-staging
```

## 3. Workload Identity pool

The pool lives in the identity project `opptra-sdlc-ci`, not in the staging project. There is one pool for the company, `opptra-github`, and one OIDC provider, `github`. Every app trusts that pool. Do not create a second pool. Do not create deployer accounts, Terraform state buckets, or the `apps` Artifact Registry in `opptra-sdlc-ci`.

The provider admits any token from the GitHub org `opptra`. It does not name a repository. Per-repository restriction is the service-account binding written by the bind scripts. Both `WIF_PROVIDER_STAGING` and `WIF_PROVIDER_PROD` hold this provider. The project number below is the number of `opptra-sdlc-ci`. The bind scripts look it up. Do not hardcode it anywhere else.

```text
projects/1076116661894/locations/global/workloadIdentityPools/opptra-github/providers/github
```

Confirm the pool before binding a repository:

```bash
gcloud iam workload-identity-pools describe opptra-github \
  --project=opptra-sdlc-ci \
  --location=global
```

Create the pool only when that command says it is missing:

```bash
gcloud iam workload-identity-pools create opptra-github \
  --project=opptra-sdlc-ci \
  --location=global \
  --display-name="GitHub"

gcloud iam workload-identity-pools providers create-oidc github \
  --project=opptra-sdlc-ci \
  --location=global \
  --workload-identity-pool=opptra-github \
  --display-name="GitHub" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository_owner == 'opptra'"
```

The provider type is OpenID Connect. The issuer URL is what makes it GitHub Actions.

## 4. Terraform state bucket

One bucket per workload project. The name is `<project-id>-tfstate`. Versioning stays on, so a bad apply can be recovered from the previous object. Create the bucket only when it does not already exist. `gs://opptra-staging-tfstate` and `gs://opptra-applications-tfstate` already exist.

```bash
gcloud storage buckets create gs://opptra-staging-tfstate \
  --project=opptra-staging \
  --location=asia-south1 \
  --uniform-bucket-level-access

gcloud storage buckets update gs://opptra-staging-tfstate --versioning
```

Confirm versioning on every state bucket:

```bash
gcloud storage buckets describe gs://PROJECT_ID-tfstate --format='yaml(name,versioning)'
```

If `versioning.enabled` is not true:

```bash
gcloud storage buckets update gs://PROJECT_ID-tfstate --versioning
```

Create `<prod-project-id>-tfstate` the same way in each new production project before that project's first app is bound. The bind script does not create the bucket. App state is stored at prefix `<service name>` inside the shared bucket. Two apps that share a production project share the bucket and still use different prefixes.

## 5. Artifact Registry

Create a Docker repository named `apps` in `asia-south1`. [scripts/bind-staging.sh](../scripts/bind-staging.sh) creates it in `opptra-staging` if it is missing. [scripts/bind-production.sh](../scripts/bind-production.sh) creates it in that app's production project if it is missing. Neither script creates it in `opptra-sdlc-ci`.

```bash
gcloud artifacts repositories create apps \
  --project=opptra-staging \
  --location=asia-south1 \
  --repository-format=docker \
  --description="App images for opptra/sdlc-resources"
```

## 6. Bind each repository

Follow [bind.md](bind.md). The developer runs [scripts/bind-staging.sh](../scripts/bind-staging.sh). Someone who can change IAM in `prod_project` runs [scripts/bind-production.sh](../scripts/bind-production.sh). Each script creates `<repo-name>-deployer` in one project, grants it permission to apply Terraform and push images, and lets one GitHub environment impersonate it. Terraform creates the runtime account `<service-name>-rt` and the Cloud Run service.

Humans do not receive deploy roles. People who need to look at staging get viewer. Existing prod project owners stay as they are. After the pilot has deployed through GitHub, remove leftover user-wide Editor roles on those prod projects.

## 7. Budgets

On the billing account, add a budget for `opptra-staging` that notifies at 50%, 90%, and 100%. Send it to the billing owners. Add the same pattern on each existing production project. The billing account id is not stored in this repository.

## 8. Public invoker

`auth: app-login`, `auth: public`, and `auth: shared-secret` disable the Cloud Run invoker check. The application checks the caller. `auth: iap` keeps the check and grants the IAP service agent. The module does not grant `allUsers`, because domain restricted sharing rejects that member. Do not work around it by putting a service-account key in GitHub.

## 9. Region

New services use `asia-south1`, set in `service.yaml`. The Artifact Registry repository is created in that region.
