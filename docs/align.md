# Align an existing repository

`align-app` in `opptra/agent-skills` reads this file. It compares the open repository with the standard and shows two sections. It applies only the **Add now** lines the developer accepts. It does not start a **Later** item in that turn.

Apps Script is unsupported. Report it and leave the repository unchanged.

## Add now

These do not move the running app.

- `service.yaml` at the repo root, with `name`, `purpose`, `prod_project`, `region`, and `components`. Facts only. Archetype is `cloud-run-service`, `cloud-run-job`, `vm-worker`, or `config-only`.
- `AGENTS.md`, `CLAUDE.md`, and `.cursor/rules` from `rules/source/` for the parts that are present. A file that already exists is not finished. Compare it with `rules/source/always.md`. If it is missing the commit format, the Linear link, the confirmations, the feature-or-bug choice, or the OpenSpec requirement, recommend replacing it with the current source. Show the missing sentences before writing.
- A README that says what the app is, how to run it locally, and how to deploy. Use the purpose. Local commands match the parts: `uv` and uvicorn for an API, `npm run dev` for a UI, `python -m app.main` for a job or a worker. Deploy text says `main` does not deploy, a push of `main` onto `staging` deploys staging, and a pull request from `main` into `production` deploys production. A config-only repo says there is nothing to run or deploy. If the README already has these sections, skip this line.
- A pull-request-only CI caller for the languages that are already in the repo. Python gets `python-ci`. A Vite or React UI gets `frontend-ci`. Config with no service gets `config-ci`. The caller uses `opptra/sdlc-resources` at `main`.
- Branches `main`, `staging`, and `production` when they are missing. `main` is the default and does not deploy. `staging` stays unprotected. `production` is protected.

Do not delete the current deploy path as part of these lines.

## Later

Research each item that matches. Cite the files found. Say what the standard would do. End with one recommendation. Do not apply these in the same turn.

### Host is a VM, a MIG, or Vercel

Look for `deploy.sh`, `cloudbuild.yaml`, `vercel.json`, a startup script that pulls `latest`, or a compose file that runs the app and a database together.

Tell the developer which part would become `cloud-run-service` and which part would stay `vm-worker`. Postgres goes on Cloud SQL, not on the VM.

Recommendation: keep the current host until `service.yaml`, the rules, CI, and the three branches are in place.

### Cloud Run already exists and Terraform does not

Look for a Cloud Run service or job name in workflows or scripts, and no `infra/` directory.

The import is a separate pull request, after `service.yaml` exists. From `infra/`:

```bash
terraform init -backend-config="bucket=<project>-tfstate" -backend-config="prefix=<name>"
terraform import module.service.google_cloud_run_v2_service.app projects/<project>/locations/<region>/services/<name>
terraform import module.service.google_service_account.runtime projects/<project>/serviceAccounts/<name>-runtime@<project>.iam.gserviceaccount.com
```

For a job, import `module.service.google_cloud_run_v2_job.app` instead of the service. The first plan must be an update, not a second service.

Recommendation: import only after `service.yaml` exists, in its own pull request.

### A laptop script deploys production

Look for `deploy.sh` or a `gcloud` command whose default project is production.

Recommendation: leave the script until one staging deploy through GitHub has succeeded. Delete it in a follow-up pull request. Do not delete it in the alignment turn.

### A job or a worker has no deploy workflow

`deploy-job` updates the job image and must not run the job. `deploy-worker` pushes an image and must not restart the VM.

Recommendation: add that caller only when the component is ready to ship through GitHub.

### A database is not Cloud SQL

Look for Postgres in `docker-compose`, a database installed on the same VM as the app, Supabase, or a connection string in `.env` or `deploy.sh`.

The standard is Cloud SQL Postgres, with `database: postgres` on the component, SQLAlchemy, and Alembic. The password stays in Secret Manager. Staging and production use different instances.

Recommendation: do not create Cloud SQL or delete the current database during alignment. Move it in its own pull request after `service.yaml` exists.

### OpenSpec

Run `openspec --version`. Look for an `openspec/` directory.

If the command fails, or the directory is missing, show this recommendation. Do not install OpenSpec in the alignment turn. When the first feature starts, install it with `npm install -g @fission-ai/openspec@latest` and run `openspec init --tools cursor,claude` from the repo root.

### Linear

Try to read a Linear issue for this repository. If Linear is not connected, show this recommendation. Ask the developer to connect Linear in Cursor or Claude. Branch names, commit messages, and pull requests need a ticket id. Do not invent one. Do not block the **Add now** lines on this connection.
