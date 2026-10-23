from __future__ import annotations

import sys

from app.runner import run_job


def run() -> str:
    code, status = run_job("default", lambda: "ok")
    if code != 0:
        raise RuntimeError(status)
    return status


if __name__ == "__main__":
    job_name = sys.argv[1] if len(sys.argv) > 1 else "default"
    code, status = run_job(job_name, lambda: "ok")
    print(status)
    raise SystemExit(code)
