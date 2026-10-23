GCP resources are declared in infra and the shared module. Do not apply Terraform against production from a laptop.

Every GCP resource—Cloud Run services and jobs, Cloud Scheduler entries, Cloud Tasks queues, Secret Manager secrets, Cloud Storage buckets, Cloud SQL instances, service accounts, and alert policies—must be prefixed with the app's `prefix` (or `name`) from `service.yaml` (`<prefix>-<resource>`) so resources in shared staging and production projects are immediately identifiable and never collide.

Read the plan comment on the pull request before you call the change done. A database, when one is added, uses lifecycle prevent_destroy.
