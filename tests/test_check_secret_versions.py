"""The deploy names mounted secrets that have no version and stops."""

import sys
import tempfile
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_secret_versions import (  # noqa: E402
    format_failure,
    main,
    missing_versions,
    mounted_secret_ids,
)

MAIN_TF = """
module "service" {
  mounted_secret_ids = [
    module.secrets.by_id["cx-SMTP_PASSWORD"],
    module.secrets.by_id["cx-FRESHDESK_CUSTOMERCARE_API_KEY"],
  ]
}

module "receiver" {
  mounted_secret_ids = [
    module.secrets.by_id["cx-WEBHOOK_SECRET"],
    module.secrets.by_id["cx-SMTP_PASSWORD"],
  ]
}
"""


def test_mounted_ids_are_unique_and_keep_order() -> None:
    assert mounted_secret_ids(MAIN_TF) == [
        "cx-SMTP_PASSWORD",
        "cx-FRESHDESK_CUSTOMERCARE_API_KEY",
        "cx-WEBHOOK_SECRET",
    ]


def test_no_mounts_is_an_empty_list() -> None:
    assert mounted_secret_ids('module "secrets" { secret_ids = ["cx-SMTP_PASSWORD"] }') == []


def test_missing_versions_uses_the_lister() -> None:
    ready = {"cx-SMTP_PASSWORD"}

    def lister(_project: str, secret_id: str) -> bool:
        return secret_id in ready

    assert missing_versions("opptra-staging", mounted_secret_ids(MAIN_TF), lister) == [
        "cx-FRESHDESK_CUSTOMERCARE_API_KEY",
        "cx-WEBHOOK_SECRET",
    ]


def test_failure_names_the_ids_and_asks_for_a_rerun() -> None:
    message = format_failure(["cx-WEBHOOK_SECRET"])
    assert "cx-WEBHOOK_SECRET" in message
    assert "re-run this workflow" in message
    assert "latest" in message

    with tempfile.TemporaryDirectory() as tmp:
        main_tf = Path(tmp) / "main.tf"
        main_tf.write_text('mounted_secret_ids = [module.secrets.by_id["cx-WEBHOOK_SECRET"]]\n')
        errors = StringIO()
        real_stderr = sys.stderr
        sys.stderr = errors
        try:
            code = main(
                ["--project", "opptra-staging", "--main-tf", str(main_tf)],
                versions_lister=lambda _project, _secret_id: False,
            )
        finally:
            sys.stderr = real_stderr
    assert code == 1
    assert "cx-WEBHOOK_SECRET" in errors.getvalue()
    assert "re-run this workflow" in errors.getvalue()


def test_ready_secrets_pass() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        main_tf = Path(tmp) / "main.tf"
        main_tf.write_text('mounted_secret_ids = [module.secrets.by_id["cx-WEBHOOK_SECRET"]]\n')
        code = main(
            ["--project", "opptra-staging", "--main-tf", str(main_tf)],
            versions_lister=lambda _project, _secret_id: True,
        )
    assert code == 0
