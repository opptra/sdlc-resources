Postgres runs on Cloud SQL. Do not install Postgres on the app VM, and do not use a database container in production.

Use SQLAlchemy 2 and Alembic. Put the engine and session in `backend/app/db.py`. Put migrations in `backend/alembic/`. A schema change ships in the same pull request as the code that needs it.

Open a session per request and close it when the request ends. Pass values as bound parameters. Do not build SQL by concatenating strings.

The password and connection name come from Secret Manager. Do not put them in `service.yaml`, source, or the image. `DATABASE_URL` on a laptop points at a local Postgres only. Do not point it at the production instance.

Do not run Alembic against production from a laptop. Staging and production each have their own Cloud SQL instance. Applying a migration there is a reviewed change, after the pull request that added the migration is merged.

The Cloud SQL instance is protected with `prevent_destroy`. A plan that destroys it is a mistake unless the pull request says the database is being retired on purpose.
