# Cloud Run service module

Recipe for one Cloud Run service in one GCP project. `scripts/generate.py` copies this folder into an app at `infra/modules/cloud-run-service/` when `service.yaml` has an `api` part, and again when that component has a webhook `receiver`. A deploy applies the copy. See [docs/local-terraform-modules.md](../../docs/local-terraform-modules.md).

It declares:

- Runtime service account `<name>-rt` (the account id is cut at 28 characters)
- Cloud Run service, image set to the commit SHA passed in by the workflow
- Invoker: `app-login`, `public`, and `shared-secret` disable the Cloud Run invoker check. The app checks the caller. `iap` keeps the check and grants the IAP service agent.
- Read access on each secret this service mounts, granted to this service account before the revision is saved. The secret shell itself comes from [modules/secrets](../secrets/).

`deletion_protection` is false, so removing this module from an app's config shows a destroy in the plan, and apply deletes the service.

A Cloud SQL instance is a separate recipe, [modules/cloud-sql](../cloud-sql/), copied when the component has `database: postgres`. That module sets `prevent_destroy`, so a plan that would drop the instance fails until someone removes that block on purpose.

The CI identity that runs Terraform is created by `scripts/bind-staging.sh` and `scripts/bind-production.sh`. It is not a resource in this module, because GitHub has to authenticate as that identity before the first apply.
