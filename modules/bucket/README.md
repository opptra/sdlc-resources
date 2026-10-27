# Bucket module

Recipe for one private Cloud Storage bucket. `scripts/generate.py` copies this folder into an app at `infra/modules/bucket/` when a component has `bucket: private`. A deploy applies the copy. See [docs/local-terraform-modules.md](../../docs/local-terraform-modules.md).

The bucket name is `<project>-<name>-assets`. Uniform access is on, and public access is blocked. The runtime account from the service or job module receives `roles/storage.objectAdmin` on that bucket.

The bucket name is passed to a job as `GCS_BUCKET_NAME`. It is not a secret.
