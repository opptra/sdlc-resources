# Schedule module

Recipe for Cloud Scheduler entries that start Cloud Run jobs. `scripts/generate.py` copies this folder into an app at `infra/modules/schedule/` when a job has an enabled cron. A deploy applies the copy. See [docs/local-terraform-modules.md](../../docs/local-terraform-modules.md).

One scheduler job is created per enabled schedule. The name drops underscores, matching the Cloud Run job name. The runtime account is granted `roles/run.invoker` so the scheduler can call the job. A disabled job is left out, so its cron is not created.

The job resource itself comes from [modules/cloud-run-job](../cloud-run-job/). This module only starts it on the cron.
