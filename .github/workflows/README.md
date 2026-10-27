# Workflows

An app does not copy these files. [scripts/generate.py](../../scripts/generate.py) writes a thin `.github/workflows/ci.yml` in the app that calls the ones below with `workflow_call`, pinned at the `ref` in [mapping.yaml](../../mapping.yaml). The call checks out the app. Scripts it runs, such as `render_tfvars.py`, have to already be in the app. See [scripts/README.md](../../scripts/README.md).

## Called by an app

| Workflow | When it runs | What it does |
|---|---|---|
| [python-ci.yml](python-ci.yml) | Pull request, for a Python component | Lint and tests |
| [frontend-ci.yml](frontend-ci.yml) | Pull request, for a UI | Frontend install and tests |
| [config-ci.yml](config-ci.yml) | Pull request, for a config-only repo | Checks that `service.yaml` and `README.md` exist |
| [sdlc-check.yml](sdlc-check.yml) | Pull request | Checks the manifest, the rule stamp, and `sdlc.py status` when the app has that CLI |
| [terraform-plan.yml](terraform-plan.yml) | Pull request | Plans staging, or production when the pull request targets `production`. Comments the plan. Changes nothing. |
| [deploy-cloud-run.yml](deploy-cloud-run.yml) | Push to `staging`, or merge into `production`, for an API | Creates secret shells, stops when a mounted secret has no version, builds the image, applies Terraform |
| [deploy-job.yml](deploy-job.yml) | Same branches, for a job | Same secret check, then build and apply. A new image does not start a run. |
| [deploy-worker.yml](deploy-worker.yml) | Same branches, for a VM worker | Pushes an image. It does not restart the VM. |

`deploy-cloud-run` and `deploy-job` run `scripts/check_secret_versions.py` from the app before the image build. The generator copies that file. A missing copy fails the deploy.

## Run in this repository

| Workflow | What it does |
|---|---|
| [pr.yml](pr.yml) | Runs the generator tests and the docs link check on a pull request |
| [docs.yml](docs.yml) | Publishes `docs/` to GitHub Pages from `main` |
