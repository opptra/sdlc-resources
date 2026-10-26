---
title: Resources
parent: Platform
nav_order: 1
---

# Resources

Git holds the resources an app should have. A Cloud Storage object holds the resources Terraform last created. `terraform plan` prints what an apply would add, change, or destroy. Apply is the only step that changes the project.

## Where each step runs

All of this runs on a GitHub-hosted runner, in the app repository, by calling workflows in this repository. The runner is not a machine in the GCP project.

| Step | When | What it does to GCP |
|---|---|---|
| Lint and tests | Every pull request | Nothing |
| `terraform plan` | Every pull request | Reads state and the live project. Writes a comment. Changes nothing. |
| `docker build` and push | Merge to `staging` or `production` | Pushes an image tagged with that commit's SHA to Artifact Registry in the target project |
| `terraform plan` again, then `terraform apply` | Same merge, after the push | Creates, updates, or deletes resources so the project matches `infra/` |

A pull request into `main` plans `opptra-staging` and does not apply. A push to `staging` applies that plan in the staging project. A pull request into `production` plans `prod_project`, and the merge applies it.

The plan on the pull request is the one a person reads. The merge creates a new commit, so the apply job plans again for that commit and applies that plan. The image tag in the applied plan is the commit that landed on the branch.

## What Terraform owns

[modules/cloud-run-service](../modules/cloud-run-service/) declares, for one app in one project:

- Runtime service account `<name>-runtime`
- The Cloud Run service, including CPU, memory, env, and the image
- Who can invoke it

Removing a resource from that module shows a destroy in the plan. Apply then deletes it. `deletion_protection` on the Cloud Run service is false so that destroy is allowed.

The state object is `gs://<project>-tfstate/<app name>`. Staging state is in the `opptra-staging` bucket. Production state is in the prod project's bucket. Two applies cannot change the same app at once. The state bucket has object versioning, so a bad apply can be recovered from the previous object.

## What stays outside Terraform

The state bucket and the Workload Identity pool are created once, before Terraform can run. [gcp-bootstrap.md](gcp-bootstrap.md) is that procedure. Terraform cannot store state in a bucket that does not exist yet.

`scripts/bind-repo.sh` creates the CI service account GitHub authenticates as, and grants it permission to apply and to push images. It does not create the Cloud Run service. The first apply does that.

A Cloud SQL instance is added in the app's `infra/` when the app needs a database, with `lifecycle { prevent_destroy = true }`. Apply then refuses to drop it until someone removes that block in a reviewed change.

## An existing service

Import it once, from a machine that can read the project, before the first apply. Otherwise Terraform plans a second service.

```bash
cd infra
terraform init -backend-config="bucket=<project>-tfstate" -backend-config="prefix=<name>"
terraform import module.service.google_cloud_run_v2_service.app projects/<project>/locations/<region>/services/<name>
terraform import module.service.google_service_account.runtime projects/<project>/serviceAccounts/<name>-runtime@<project>.iam.gserviceaccount.com
```

Then open a pull request. The plan should be an update, not a create.
