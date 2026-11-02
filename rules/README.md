# Rules

[source/](source/) is the text agents follow. [scripts/build_rules.py](../scripts/build_rules.py) compiles the files selected by the capabilities in `service.yaml` into the app as `AGENTS.md`, `CLAUDE.md`, and `.cursor/rules/*.mdc`.

`always.md` is included for every app. The other files are included when [mapping.yaml](../mapping.yaml) attaches them to a part or a capability. `odlc sync-infra` rewrites the compiled copies. Edit the source here, then sync the app.

The decisions those rules implement are in [docs/decisions.md](../docs/decisions.md).
