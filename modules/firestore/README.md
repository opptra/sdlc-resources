# Firestore module

Recipe for access to Firestore. `scripts/generate.py` copies this folder into an app at `infra/modules/firestore/` when a component has `database: firestore`. A deploy applies the copy. See [docs/local-terraform-modules.md](../../docs/local-terraform-modules.md).

It grants `roles/datastore.user` on the project to the runtime account. It uses the project's existing `(default)` database so the free tier still applies. It does not create a second database.
