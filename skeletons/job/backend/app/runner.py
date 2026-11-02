"""Shared job runner with enabled flag check, lease lock hook, and non-zero exit on error."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from pathlib import Path

from app.logging import configure_logging

configure_logging()
logger = logging.getLogger("job")


def load_jobs_config(config_path: Path | None = None) -> dict[str, dict]:
    path = config_path or (Path(__file__).resolve().parents[2] / "config" / "jobs.yaml")
    if not path.is_file():
        return {}
    jobs: dict[str, dict] = {}
    current_job: str | None = None
    in_jobs = False
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if indent == 0 and stripped == "jobs:":
            in_jobs = True
            current_job = None
            continue
        if indent == 0 and stripped.endswith(":"):
            in_jobs = False
            current_job = None
            continue
        if in_jobs and indent == 2 and stripped.endswith(":"):
            current_job = stripped[:-1].strip()
            jobs[current_job] = {"enabled": True}
        elif in_jobs and current_job and indent == 4 and ":" in stripped:
            k, _, v = stripped.partition(":")
            val = v.strip().strip("\"'")
            if val.lower() == "true":
                jobs[current_job][k.strip()] = True
            elif val.lower() == "false":
                jobs[current_job][k.strip()] = False
            else:
                jobs[current_job][k.strip()] = val
    return jobs


def run_job(
    name: str,
    handler: Callable[[], str] | None = None,
    config_path: Path | None = None,
    acquire_lock: Callable[[str], bool] | None = None,
    release_lock: Callable[[str], None] | None = None,
) -> tuple[int, str]:
    jobs = load_jobs_config(config_path)
    spec = jobs.get(name, {"enabled": True})
    if not spec.get("enabled", True):
        logger.info("job_skipped_disabled name=%s", name, extra={"job": name})
        return 0, "disabled"

    if acquire_lock is not None and not acquire_lock(name):
        logger.info("job_skipped_locked name=%s", name, extra={"job": name})
        return 0, "locked"

    run_id = uuid.uuid4().hex[:12]
    logger.info("run_start name=%s run_id=%s", name, run_id, extra={"job": name, "run_id": run_id})
    try:
        result = handler() if handler is not None else "ok"
        logger.info("run_ok name=%s run_id=%s", name, run_id, extra={"job": name, "run_id": run_id})
        return 0, result
    except Exception:
        logger.exception("run_failed name=%s run_id=%s", name, run_id, extra={"job": name, "run_id": run_id})
        return 1, "failed"
    finally:
        if release_lock is not None:
            release_lock(name)
