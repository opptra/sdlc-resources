# Cloud Run job module

Recipe for one or more Cloud Run jobs that share an image and a runtime account. `scripts/generate.py` copies this folder into an app at `infra/modules/cloud-run-job/` when a component has a `job` part (`scheduled-jobs` in [mapping.yaml](../../mapping.yaml)). A deploy applies the copy. See [docs/local-terraform-modules.md](../../docs/local-terraform-modules.md).

It declares:

- Runtime service account `<name>-rt`
- One Cloud Run job per entry. Underscores in the job name become hyphens, because Cloud Run rejects underscores.
- `RESOURCE_PREFIX`, a bucket name, and other plain settings as environment variables
- Each listed secret mounted back into the variable name the process reads, from `secret_map` when that variable is mapped, otherwise from `<prefix>-<ENV_NAME>`, at `latest`
- Read access on those secrets for this account, finished before the job is saved

The secret shells come from [modules/secrets](../secrets/). This module does not create them. A job name is not part of the secret id.

Shipping a new image updates the job definition. It does not start a run or backfill. Cloud Scheduler, when a job has an enabled cron, comes from [modules/schedule](../schedule/).
