# Terraform modules

These folders are the recipes an app's `infra/main.tf` calls. [scripts/generate.py](../scripts/generate.py) copies the folders that app uses into `infra/modules/`. A deploy applies that copy. It does not clone this repository.

Edit a recipe here. It reaches an app when someone regenerates that app's `infra/` and commits the copy. The steps are in [docs/local-terraform-modules.md](../docs/local-terraform-modules.md).

| Folder | Copied when `service.yaml` has | What the apply creates |
|---|---|---|
| [cloud-run-service](cloud-run-service/) | an `api` part, or a webhook `receiver` | The service, its runtime account, and read access on the secrets it mounts |
| [cloud-run-job](cloud-run-job/) | a `job` part | The jobs, one shared runtime account, and read access on the secrets those jobs mount |
| [secrets](secrets/) | a `secrets` list | Empty Secret Manager shells. Values stay out of Git and out of Terraform state. |
| [bucket](bucket/) | `bucket: private` | A private bucket and object access for the runtime account |
| [firestore](firestore/) | `database: firestore` | Access to the project's existing `(default)` database |
| [queue](queue/) | a `queue` name | The Cloud Tasks queue and enqueue permission |
| [schedule](schedule/) | an enabled cron on a job | A Cloud Scheduler entry that runs that job |
| [alerts](alerts/) | `alerts` | A log-based alert for error logs and failed job runs |
| [cloud-sql](cloud-sql/) | `database: postgres` | Postgres 16, with deletion protection, and a generated password secret |

Bucket, Firestore, queue, and schedule receive `module.service.runtime_service_account`. The secrets module does not. The workload that mounts a secret grants its own account.
