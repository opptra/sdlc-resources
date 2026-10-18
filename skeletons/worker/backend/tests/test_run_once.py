from app.main import run_once


def test_run_once() -> None:
    assert run_once() == "ok"
