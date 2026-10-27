# Cloud SQL module

Recipe for one Postgres 16 instance. `scripts/generate.py` copies this folder into an app at `infra/modules/cloud-sql/` when a component has `database: postgres`. A deploy applies the copy. See [docs/local-terraform-modules.md](../../docs/local-terraform-modules.md).

It creates the instance `<name>-db`, a database named `app`, a user, and a Secret Manager secret `<name>-db-password` with the generated password as version 1. That password is produced by Terraform. It is not a value from the `secrets` list, and it is not committed.

`deletion_protection` and `prevent_destroy` are on. A plan that would drop the instance fails until someone removes that block on purpose. The tier is `db-g1-small`, backups are on, and connections require SSL.
