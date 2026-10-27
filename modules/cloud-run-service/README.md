# Cloud Run service module

Declares the resources for one app in one GCP project:

- Runtime service account `<name>-runtime`
- Cloud Run service, image set to the commit SHA passed in by the workflow
- Invoker IAM: `allUsers` for `app-login` and `public`, the IAP service agent for `iap`

`deletion_protection` is false, so removing this module from an app's config shows a destroy in the plan, and apply deletes the service.

A Cloud SQL instance does not belong in this module until an app needs one. When it does, add it in the app repository with `lifecycle { prevent_destroy = true }`. A plan that would drop the instance then fails until someone removes that block on purpose.

The CI identity that runs Terraform is created by `scripts/bind-staging.sh` and `scripts/bind-production.sh`. It is not a resource in this module, because GitHub has to authenticate as that identity before the first apply.
