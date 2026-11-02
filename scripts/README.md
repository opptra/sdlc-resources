# Scripts

Two kinds of files live here. The guide runs the first kind from a checkout of this repository. A deploy runs the second kind from the app repository, because GitHub checks out the app.

## Run from this repository

| Script | What it does in the guide |
|---|---|
| [odlc.py](odlc.py) | Phase CLI `odlc`: `check`, `status`, `next`, `secrets`, `doctor`, `discover-infra`, `init-runtime`, `add-data`, `add-tests`, `sync-infra`, `all`. `discover` and `sync` are aliases. |
| [sdlc.py](sdlc.py) | Forwards to `odlc` so older callers that still run `scripts/sdlc.py` keep working. |
| [generate.py](generate.py) | Turns `service.yaml` into the app: workflows, infra, rules, hooks, and the copied scripts below |
| [check_manifest.py](check_manifest.py) | Rejects a `service.yaml` that does not match [service.schema.json](../service.schema.json) |
| [build_rules.py](build_rules.py) | Compiles [rules/source](../rules/source/) into `AGENTS.md`, `CLAUDE.md`, and `.cursor/rules` |
| [status.py](status.py) | Compares an app with the standard. `align-app` reads its JSON. |
| [discover_infra.py](discover_infra.py) | Reads an existing repo when aligning it |
| [docs_site.py](docs_site.py) | Checks links in `docs/` and prepares the GitHub Pages build |
| [protect-branches.sh](protect-branches.sh) | Protects `main` and `production` after CI has run once |
| [bind-staging.sh](bind-staging.sh) | Template. The generator fills in a copy inside the app. |
| [bind-production.sh](bind-production.sh) | Template. The generator fills in a copy inside the app. |

## Copied into the app

`init-runtime` and `sync-infra` copy these next to the filled-in bind scripts. The deploy workflows call them as `python3 "$GITHUB_WORKSPACE/scripts/..."`.

| Script | What calls it |
|---|---|
| [render_tfvars.py](render_tfvars.py) | Plan and deploy workflows, to write `ci.auto.tfvars.json` |
| [yaml_subset.py](yaml_subset.py) | Imported by `render_tfvars.py` and the other Python tools |
| [check_secret_versions.py](check_secret_versions.py) | `deploy-cloud-run` and `deploy-job`, after the secret shells exist |

An app generated before `check_secret_versions.py` was added needs one `sync-infra`, then a commit of that file, before the next deploy. The workflow fails if the file is missing.
