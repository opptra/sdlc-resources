from pathlib import Path

from app.main import run
from app.runner import run_job


def test_run_returns_ok() -> None:
    assert run() == "ok"


def test_disabled_job_exits_zero_without_running(tmp_path: Path) -> None:
    cfg = tmp_path / "jobs.yaml"
    cfg.write_text("jobs:\n  disabled_job:\n    enabled: false\n")
    called = False

    def _boom() -> str:
        nonlocal called
        called = True
        raise RuntimeError("should not be called")

    code, status = run_job("disabled_job", _boom, config_path=cfg)
    assert code == 0
    assert status == "disabled"
    assert not called


def test_unhandled_error_exits_nonzero(tmp_path: Path) -> None:
    cfg = tmp_path / "jobs.yaml"
    cfg.write_text("jobs:\n  failing_job:\n    enabled: true\n")

    def _fail() -> str:
        raise RuntimeError("upstream 429 rate limit")

    code, status = run_job("failing_job", _fail, config_path=cfg)
    assert code == 1
    assert status == "failed"
