Use Python 3.12, uv, Ruff, and pytest. Keep HTTP routes under /api. Log JSON to stdout through the app logger. Fields are severity, message, service, and environment.

Read a plain setting with `get_env` and a secret with `get_secret`. Declare the name in `service.yaml` and run `sync-infra` before using it. Do not hardcode a key, domain, or email list, and do not read `os.environ` for those values directly.

Put tests in backend/tests. Run uv run ruff check . and uv run pytest from the component directory before you stop.
