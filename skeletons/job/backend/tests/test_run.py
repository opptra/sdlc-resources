from app.main import run


def test_run() -> None:
    assert run() == "ok"
