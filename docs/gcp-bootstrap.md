# GCP bootstrap

Do this once, before any app deploys through the workflow. The project id in the workflows is the placeholder `opptra-staging`. If the real id differs, change the default input `staging_project` on [deploy-cloud-run.yml](../.github/workflows/deploy-cloud-run.yml) and the default in [scripts/bind-repo.sh](../scripts/bind-repo.sh).

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
  --project=opptra-staging
```

## 3. Workload Identity pool

The pool lives in the staging project. Production deployer accounts in other projects trust the same pool.

```bash
gcloud iam workload-identity-pools create opptra-github \
  --project=opptra-staging \
  --location=global \
  --display-name="GitHub"

gcloud iam workload-identity-pools providers create-oidc github \
  --project=opptra-staging \
  --location=global \
  --workload-identity-pool=opptra-github \
  --display-name="GitHub" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository_owner == 'opptra'"
```

## 4. Terraform state bucket

One bucket per project. The name is `<project-id>-tfstate`. Versioning stays on, so a bad apply can be recovered from the previous object.

```bash
gcloud storage buckets create gs://opptra-staging-tfstate \
  --project=opptra-staging \
  --location=asia-south1 \
  --uniform-bucket-level-access

gcloud storage buckets update gs://opptra-staging-tfstate --versioning
```

Create `<prod-project-id>-tfstate` the same way in each production project before that app's first apply. App state is stored at prefix `<service name>` inside the bucket.

## 5. Artifact Registry

Create a Docker repository named `apps` in `asia-south1`. [scripts/bind-repo.sh](../scripts/bind-repo.sh) creates it if it is missing, in the staging project and in the app's prod project.

```bash
gcloud artifacts repositories create apps \
  --project=opptra-staging \
  --location=asia-south1 \
  --repository-format=docker \
  --description="App images for opptra/sdlc"
```

## 6. Bind each repository

```bash
scripts/bind-repo.sh opptra/<repo> <prod-project-id>
```

The script creates `<app>-deployer` in both projects, grants it permission to apply Terraform and push images, and lets the GitHub repository impersonate it. Terraform creates `<app>-runtime` and the Cloud Run service. The script prints the Actions variables to set on that GitHub repository.

Humans do not receive deploy roles. People who need to look at staging get viewer. Existing prod project owners stay as they are. After the pilot has deployed through GitHub, remove leftover user-wide Editor roles on those prod projects.

## 7. Budgets

On the billing account, add a budget for `opptra-staging` that notifies at 50%, 90%, and 100%. Send it to the billing owners. Add the same pattern on each existing production project. The billing account id is not stored in this repository.

## 8. Public invoker

`auth: app-login` and `auth: public` grant `roles/run.invoker` to `allUsers`. If an organization policy blocks `allUsers`, the apply fails. The fix is an organization exception for that service, or `auth: iap`. Do not work around it by putting a service-account key in GitHub.

## 9. Region

New services use `asia-south1`, set in `service.yaml`. The Artifact Registry repository is created in that region.
