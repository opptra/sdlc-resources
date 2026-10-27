# Skeletons

Starting files for a new app. [scripts/generate.py](../scripts/generate.py) copies a skeleton when `service.yaml` selects that part, then the later phases add data files, tests, infra, and workflows. People do not copy a skeleton by hand.

| Folder | Copied when |
|---|---|
| [api](api/) | The component has an `api` part |
| [ui](ui/) | The component has a `ui` part |
| [job](job/) | The component has a `job` part |
| [worker](worker/) | The component has a `worker` part |
| [config](config/) | The component is config-only. Nothing deploys. |
| [data-postgres](data-postgres/) | `database: postgres`. Adds the database helper on top of the runtime skeleton. |
| [data-firestore](data-firestore/) | `database: firestore`. Adds the Firestore helper on top of the runtime skeleton. |

Which part maps to which capability, workflow, and Terraform module is [mapping.yaml](../mapping.yaml). The page for creating an app is [docs/new-app.md](../docs/new-app.md).
