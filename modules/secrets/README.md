# Secrets module

Recipe for empty Secret Manager shells. `scripts/generate.py` copies this folder into an app at `infra/modules/secrets/` when a component lists `secrets`. A deploy applies the copy. See [docs/local-terraform-modules.md](../../docs/local-terraform-modules.md).

Each id is `<prefix>-<ENV_NAME>`, the same variable the process reads, with the app prefix in front. `FRESHDESK_CUSTOMERCARE_API_KEY` is stored as `cx-FRESHDESK_CUSTOMERCARE_API_KEY`. Underscores stay. The job name is not part of the id.

This module creates the shells only. It does not store a value, and it does not grant read access. The job or service that mounts a shell grants its own runtime account and waits for that grant. Domains, ports, and flags are plain environment variables on the workload, not secrets.

On deploy, `deploy-cloud-run` and `deploy-job` apply this module first, then run `scripts/check_secret_versions.py` from the app checkout. If a mounted secret has no version, the workflow stops and prints the ids. A person adds version 1 in Secret Manager and re-runs the same workflow. The value is not committed.
