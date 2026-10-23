"""Local-first environment and secret loader.

In local development (`APP_ENV=local`), loads `.env` if present and reads
`SECRET_<ID>` (or `<ID>`) from environment variables. In `staging` and `prod`,
reads from environment or GCP Secret Manager.
"""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: Path | None = None) -> None:
    candidates = [path] if path else [Path(".env"), Path(__file__).resolve().parents[2] / ".env"]
    for candidate in candidates:
        if candidate and candidate.is_file():
            for raw in candidate.read_text().splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip("\"'"))
            break


def get_env(name: str, default: str = "") -> str:
    load_dotenv()
    return os.environ.get(name, default)


def get_secret(secret_id: str, default: str = "") -> str:
    load_dotenv()
    upper = secret_id.upper().replace("-", "_")
    for env_key in (f"SECRET_{upper}", upper, secret_id):
        if env_key in os.environ and os.environ[env_key]:
            return os.environ[env_key]
    if os.environ.get("APP_ENV", "local") == "local":
        return default
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT")
    if not project_id:
        return default
    from google.cloud import secretmanager  # type: ignore[import-untyped]

    client = secretmanager.SecretManagerServiceClient()
    resource = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": resource})
    return response.payload.data.decode("utf-8")
