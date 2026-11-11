---
title: Local Terraform modules
parent: Platform
nav_order: 2
---

# Local Terraform modules

`infra/main.tf` is the list of resources for one app. The module folders are the recipes for those resources. A deploy applies that list from files already in the app repository. It does not clone `opptra/sdlc-resources`.

## Why

`terraform init` used to download each module with a source like:

```hcl
source = "git::https://github.com/opptra/sdlc-resources.git//modules/bucket?ref=main"
```

That failed on GitHub Actions for two reasons.

- `sdlc-resources` is private. The runner's token can read the app repository. Git then asks for a username to clone this repository, and the runner has no keyboard, so init stops with `could not read Username for 'https://github.com'`.
- Terraform clones once per module block. One app with a service, a bucket, Firestore access, a queue, secrets, a schedule, a webhook, and alerts clones this repository eight times on every deploy.

`ref=main` also meant a deploy could pick up a module edit that was never reviewed in the app repository.

## What changed

`scripts/generate.py` `write_infra` now does two things for each module the app uses:

1. Copy `modules/<name>/` into the app at `infra/modules/<name>/`.
2. Set that block's source to `./modules/<name>`.

The recipes still live in this repository. The copy in the app is what a deploy runs. A later edit here reaches an app only when someone regenerates that app's `infra/` and commits the result.

## How one apply uses every module

`infra/main.tf` is the only entrypoint. Terraform reads it, builds one plan, and writes one state file, `gs://<project>-tfstate/<app name>`.

The service module runs first. It creates the Cloud Run jobs or service and the runtime service account. Later blocks receive that account:

| Module folder | What the apply creates |
|---|---|
| `cloud-run-job` or `cloud-run-service` | The workload and `runtime_service_account` |
| `bucket` | `<project>-<name>-assets`, and object access for that account |
| `firestore` | Access to the project's `(default)` database. The deploy creates that Native database in the app region when it is missing. The module does not own it. A database in another mode or region stops the deploy. |
| `queue` | The Cloud Tasks queue named in `service.yaml` |
| `secrets` | Empty Secret Manager shells. The workload that mounts a shell grants its own account. The deploy creates the shells, stops when a mounted secret has no version, and mounts `latest` on the next run. |
| `schedule` | A scheduler entry for each enabled cron |
| `cloud-run-service` | The webhook receiver, when `service.yaml` has a `receiver` |
| `alerts` | The alert policies |
| `cloud-sql` | The database, only when `database: postgres` |

A secret shell does not receive the runtime account. The workload passes `module.secrets.by_id` into `mounted_secret_ids`, grants its own account, and waits for that grant. Bucket, Firestore, queue, and schedule still receive `module.service.runtime_service_account`.

## Refresh an app

From a machine that has this repository checked out:

```bash
python3 - << 'PY'
import sys
from pathlib import Path
sys.path.insert(0, "/path/to/sdlc-resources/scripts")
from generate import _load_and_normalize, component_dir_for, write_infra

dest = Path("/path/to/app")
app, mapping, components = _load_and_normalize(dest / "service.yaml")
for component in components:
    write_infra(mapping, app, component, component_dir_for(dest, component))
PY
```

`write_infra` replaces that component's `infra/` directory, including `infra/modules/`. Commit the new `main.tf` and the copied modules in the app repository. Push that commit to `staging` to deploy it.

## Scripts the deploy runs from the app

The runner checks out the app. These files have to be in that checkout:

| File in the app | What calls it |
|---|---|
| `scripts/render_tfvars.py` | Plan and deploy workflows, to write `ci.auto.tfvars.json` |
| `scripts/yaml_subset.py` | Imported by `render_tfvars.py` |
| `scripts/check_secret_versions.py` | `deploy-cloud-run` and `deploy-job`, after the secret shells exist |
| `scripts/summarize_plan.py` | `terraform-plan`, to write the pull request comment |

For generator-owned apps, `init-runtime` and `sync-infra` copy these files. During adoption and after handoff, review and update the specific helpers or modules in the app repo. Sync refreshes agent rules in those modes.

Do not run a full `odlc sync-infra` only to refresh modules. That command also rewrites workflows, rules, and hooks.

`terraform init` still downloads the HashiCorp `google` provider. That download is the public provider registry, not this repository, and it does not need a GitHub login.
