"""The deploy creates the one Firestore database when the project has none."""

import sys
import tempfile
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_firestore import firestore_problem, main, uses_firestore  # noqa: E402

WITH_FIRESTORE = 'module "firestore" {\n  source = "./modules/firestore"\n}\n'
WITHOUT = 'module "bucket" {\n  source = "./modules/bucket"\n}\n'


def test_detects_the_firestore_module() -> None:
    assert uses_firestore(WITH_FIRESTORE) is True
    assert uses_firestore(WITHOUT) is False


def test_wrong_mode_and_wrong_region() -> None:
    mode = firestore_problem("asia-south1", {"type": "DATASTORE_MODE", "locationId": "asia-south1"})
    assert mode is not None
    assert "Native" in mode
    place = firestore_problem("asia-south1", {"type": "FIRESTORE_NATIVE", "locationId": "us-central1"})
    assert place is not None
    assert "us-central1" in place


def test_ready_database_passes() -> None:
    assert firestore_problem(
        "asia-south1",
        {"type": "FIRESTORE_NATIVE", "locationId": "asia-south1"},
    ) is None


def _run(main_tf: str, describer, creator=None) -> tuple[int, str]:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "main.tf"
        path.write_text(main_tf)
        errors = StringIO()
        real_stderr = sys.stderr
        sys.stderr = errors
        try:
            code = main(
                ["--project", "opptra-staging", "--region", "asia-south1", "--main-tf", str(path)],
                describer=describer,
                creator=creator,
            )
        finally:
            sys.stderr = real_stderr
    return code, errors.getvalue()


def test_missing_database_is_created_once() -> None:
    created: list[tuple[str, str]] = []

    def creator(project: str, region: str) -> None:
        created.append((project, region))
        return None

    code, errors = _run(WITH_FIRESTORE, lambda _project: None, creator)
    assert code == 0
    assert errors == ""
    assert created == [("opptra-staging", "asia-south1")]


def test_create_failure_stops_the_deploy() -> None:
    code, errors = _run(WITH_FIRESTORE, lambda _project: None, lambda _project, _region: "denied")
    assert code == 1
    assert "denied" in errors


def test_deploy_skips_the_check_without_firestore() -> None:
    code, errors = _run(WITHOUT, lambda _project: None)
    assert code == 0
    assert errors == ""
