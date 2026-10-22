#!/usr/bin/env python3
"""Check and normalize a service.yaml against the facts the generator understands."""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from yaml_subset import parse

ROOT = Path(__file__).resolve().parents[1]
NAME = re.compile(r"^[a-z][a-z0-9-]{1,48}$")
COMPONENT = re.compile(r"^[a-z][a-z0-9-]{1,40}$")
JOB_NAME = re.compile(r"^[a-z][a-z0-9_-]{1,40}$")
SECRET_ID = re.compile(r"^[a-z][a-z0-9_-]{1,48}$")

ARCHETYPES = {
    "cloud-run-service": {
        "parts": {"api", "ui"},
        "required": {"api"},
        "auth": {"app-login", "iap", "public", "shared-secret"},
    },
    "cloud-run-job": {
        "parts": {"job"},
        "required": {"job"},
        "auth": {"none"},
    },
    "scheduled-jobs": {
        "parts": {"job", "api"},
        "required": {"job"},
        "auth": {"none"},
    },
    "vm-worker": {
        "parts": {"worker"},
        "required": {"worker"},
        "auth": {"none"},
    },
    "config-only": {
        "parts": {"config"},
        "required": {"config"},
        "auth": {"none"},
    },
}

PRESET_DEFAULTS = {
    "staff-dashboard": {"archetype": "cloud-run-service", "auth": "iap", "parts": ["ui", "api"]},
    "http-api": {"archetype": "cloud-run-service", "auth": "app-login", "parts": ["api"]},
    "scheduled-jobs": {"archetype": "scheduled-jobs", "auth": "none", "parts": ["job"]},
    "worker": {"archetype": "vm-worker", "auth": "none", "parts": ["worker"]},
    "config": {"archetype": "config-only", "auth": "none", "parts": ["config"]},
}

ALLOWED_COMPONENT_KEYS = {
    "name",
    "archetype",
    "auth",
    "parts",
    "database",
    "bucket",
    "queue",
    "secrets",
    "alerts",
    "receiver",
    "jobs",
}

ALLOWED_CAPABILITIES = {
    "postgres",
    "firestore",
    "bucket",
    "queue",
    "schedule",
    "secrets",
    "alerts",
}


def normalize(raw: dict) -> dict:
    """Return a copy of manifest data where preset/workloads/capabilities are expanded into components."""
    data = copy.deepcopy(raw)
    if "components" in data and isinstance(data["components"], list):
        for comp in data["components"]:
            if not isinstance(comp, dict):
                continue
            _normalize_component_fields(comp)
        return data

    # Expand from workloads and/or preset + capabilities
    app_name = str(data.get("name", "app"))
    comp_name = str(data.get("image") or app_name)[:40].rstrip("-")
    caps = data.get("capabilities") if isinstance(data.get("capabilities"), dict) else {}
    workloads = data.get("workloads") if isinstance(data.get("workloads"), list) else []
    preset = data.get("preset")

    database = "none"
    if caps.get("postgres"):
        database = "postgres"
    elif caps.get("firestore"):
        database = "firestore"

    bucket = "none"
    if caps.get("bucket"):
        bval = caps["bucket"]
        if isinstance(bval, dict):
            bucket = str(bval.get("access", "private"))
        elif isinstance(bval, str) and bval in {"private", "none"}:
            bucket = bval
        else:
            bucket = "private"

    queue = None
    if caps.get("queue"):
        qval = caps["queue"]
        if isinstance(qval, dict):
            queue = str(qval.get("name", f"{app_name}-tasks"))
        elif isinstance(qval, str) and qval not in {"true", "false"}:
            queue = qval
        else:
            queue = f"{app_name}-tasks"

    secrets = list(caps.get("secrets", [])) if isinstance(caps.get("secrets"), list) else []
    alerts = bool(caps.get("alerts", False))

    if workloads:
        job_items = [w for w in workloads if isinstance(w, dict) and w.get("run") == "job"]
        service_items = [
            w for w in workloads if isinstance(w, dict) and w.get("run") in {"service", "site"}
        ]
        worker_items = [w for w in workloads if isinstance(w, dict) and w.get("run") == "worker"]
        config_items = [w for w in workloads if isinstance(w, dict) and w.get("run") == "config"]

        components: list[dict] = []
        if job_items:
            archetype = "scheduled-jobs" if (len(job_items) > 1 or service_items or caps.get("schedule") or any(j.get("schedules") for j in job_items)) else "cloud-run-job"
            comp: dict = {
                "name": comp_name if len(job_items) > 1 or service_items else str(job_items[0].get("name", comp_name)),
                "archetype": archetype,
                "auth": "none",
                "parts": ["job"],
                "database": database,
                "bucket": bucket,
                "secrets": secrets,
                "alerts": alerts,
                "jobs": [
                    {
                        "name": str(j["name"]),
                        "command": str(j.get("command", f"python -m app.jobs.{str(j['name']).replace('-', '_')}")),
                        "enabled": bool(j.get("enabled", True)),
                        "timezone": str(j.get("timezone", "Asia/Kolkata")),
                        "schedules": list(j.get("schedules", [])),
                        "timeout_seconds": int(j.get("timeout_seconds", 1800)),
                        "memory": str(j.get("memory", "1Gi")),
                        "secrets": list(j.get("secrets", [])),
                    }
                    for j in job_items
                ],
            }
            if queue:
                comp["queue"] = queue
            if service_items:
                svc = service_items[0]
                comp["receiver"] = {
                    "name": str(svc.get("name", f"{app_name}-webhook")),
                    "auth": str(svc.get("auth", "shared-secret")),
                    "command": str(svc.get("command", "uvicorn app.receiver:app --app-dir backend --host 0.0.0.0 --port 8080")),
                }
                if queue:
                    comp["receiver"]["queue"] = queue
                if svc.get("secrets"):
                    comp["receiver"]["secrets"] = list(svc["secrets"])
            _normalize_component_fields(comp)
            components.append(comp)
        else:
            for svc in service_items:
                parts = ["ui", "api"] if svc.get("run") == "site" else ["api"]
                comp = {
                    "name": str(svc.get("name", comp_name)),
                    "archetype": "cloud-run-service",
                    "auth": str(svc.get("auth", "iap" if svc.get("run") == "site" else "app-login")),
                    "parts": parts,
                    "database": database,
                    "bucket": bucket,
                    "secrets": list(svc.get("secrets", secrets)),
                    "alerts": alerts,
                }
                if queue:
                    comp["queue"] = queue
                _normalize_component_fields(comp)
                components.append(comp)
        for wrk in worker_items:
            comp = {
                "name": str(wrk.get("name", comp_name)),
                "archetype": "vm-worker",
                "auth": "none",
                "parts": ["worker"],
                "database": database,
                "bucket": bucket,
                "secrets": list(wrk.get("secrets", secrets)),
                "alerts": alerts,
            }
            _normalize_component_fields(comp)
            components.append(comp)
        for cfg in config_items:
            comp = {
                "name": str(cfg.get("name", comp_name)),
                "archetype": "config-only",
                "auth": "none",
                "parts": ["config"],
            }
            _normalize_component_fields(comp)
            components.append(comp)
        if components:
            data["components"] = components
            return data

    if preset in PRESET_DEFAULTS:
        spec = PRESET_DEFAULTS[preset]
        comp = {
            "name": comp_name,
            "archetype": spec["archetype"],
            "auth": spec["auth"],
            "parts": list(spec["parts"]),
            "database": database,
            "bucket": bucket,
            "secrets": secrets,
            "alerts": alerts,
        }
        if queue:
            comp["queue"] = queue
        _normalize_component_fields(comp)
        data["components"] = [comp]
    return data


def _normalize_component_fields(comp: dict) -> None:
    comp.setdefault("database", "none")
    comp.setdefault("bucket", "none")
    comp.setdefault("secrets", [])
    comp.setdefault("alerts", False)
    if comp.get("receiver") and isinstance(comp["receiver"], dict):
        recv = comp["receiver"]
        if recv.get("queue") and not comp.get("queue"):
            comp["queue"] = recv["queue"]
        for s in recv.get("secrets", []):
            if s not in comp["secrets"]:
                comp["secrets"].append(s)
    if comp.get("jobs") and isinstance(comp["jobs"], list):
        for job in comp["jobs"]:
            if not isinstance(job, dict):
                continue
            job.setdefault("enabled", True)
            job.setdefault("timezone", "Asia/Kolkata")
            job.setdefault("schedules", [])
            job.setdefault("timeout_seconds", 1800)
            job.setdefault("memory", "1Gi")
            job.setdefault("secrets", [])
            for s in job["secrets"]:
                if s not in comp["secrets"]:
                    comp["secrets"].append(s)


def check(data: dict) -> list[str]:
    schema = json.loads((ROOT / "service.schema.json").read_text())
    errors: list[str] = []
    allowed = set(schema["properties"])
    extra = sorted(set(data) - allowed)
    if extra:
        errors.append(f"unknown fields: {', '.join(extra)}")
    for key in schema["required"]:
        if not data.get(key):
            errors.append(f"missing {key}")
    if data.get("name") and NAME.fullmatch(str(data["name"])) is None:
        errors.append(f"name {data['name']!r} is not a lowercase slug")

    if "preset" in data and data["preset"] not in PRESET_DEFAULTS:
        errors.append(
            f"preset {data['preset']!r} is not supported. "
            "Apps Script is not generated. Choose staff-dashboard, http-api, scheduled-jobs, worker, or config."
        )

    if "capabilities" in data:
        caps = data["capabilities"]
        if not isinstance(caps, dict):
            errors.append("capabilities must be a mapping")
        else:
            extra_caps = sorted(set(caps) - ALLOWED_CAPABILITIES)
            if extra_caps:
                errors.append(
                    f"unknown capabilities: {', '.join(extra_caps)}. "
                    "Record unsupported needs under unmet."
                )
            if caps.get("postgres") and caps.get("firestore"):
                errors.append("choose either postgres or firestore per component, not both")

    if "unmet" in data:
        unmet = data["unmet"]
        if not isinstance(unmet, list):
            errors.append("unmet must be a list")
        else:
            for idx, item in enumerate(unmet):
                if not isinstance(item, dict):
                    errors.append(f"unmet[{idx}] must be a mapping")
                    continue
                for req in ("name", "need", "suggestion"):
                    if not item.get(req):
                        errors.append(f"unmet[{idx}] missing {req}")

    if "workloads" in data:
        workloads = data["workloads"]
        if not isinstance(workloads, list) or not workloads:
            errors.append("workloads must be a non-empty list")
            return errors
        for w in workloads:
            if not isinstance(w, dict):
                errors.append("each workload must be a mapping")
                continue
            wname = str(w.get("name", ""))
            if JOB_NAME.fullmatch(wname) is None:
                errors.append(f"workload name {wname!r} is not a lowercase slug")
            run = w.get("run")
            if run not in {"service", "job", "worker", "site", "config"}:
                errors.append(
                    f"{wname}: workload run {run!r} is not supported. "
                    "Apps Script is not generated. Choose service, job, worker, site, or config."
                )

    normalized = normalize(data)
    components = normalized.get("components")
    if not isinstance(components, list) or not components:
        errors.append("components (or workloads/preset) must be a non-empty list")
        return errors

    seen = set()
    for component in components:
        if not isinstance(component, dict):
            errors.append("each component must be a mapping")
            continue
        extra_c = sorted(set(component) - ALLOWED_COMPONENT_KEYS)
        if extra_c:
            errors.append(f"{component.get('name', 'component')}: unknown fields: {', '.join(extra_c)}")
        cname = str(component.get("name", ""))
        if COMPONENT.fullmatch(cname) is None:
            errors.append(f"component name {cname!r} is not a lowercase slug")
        if cname in seen:
            errors.append(f"duplicate component {cname}")
        seen.add(cname)
        archetype = component.get("archetype")
        rule = ARCHETYPES.get(archetype)
        if rule is None:
            errors.append(
                f"{cname}: archetype {archetype!r} is not supported. "
                "Apps Script is not generated. Choose cloud-run-service, "
                "cloud-run-job, scheduled-jobs, vm-worker, or config-only."
            )
            continue
        parts = component.get("parts")
        if not isinstance(parts, list):
            errors.append(f"{cname}: parts must be a list")
            continue
        part_set = set(parts)
        if not rule["required"] <= part_set:
            errors.append(f"{cname}: {archetype} requires {', '.join(sorted(rule['required']))}")
        if not part_set <= rule["parts"]:
            errors.append(f"{cname}: parts {sorted(part_set)} do not fit {archetype}")
        if component.get("auth") not in rule["auth"]:
            errors.append(
                f"{cname}: auth {component.get('auth')!r} does not fit {archetype}. "
                f"Use one of: {', '.join(sorted(rule['auth']))}."
            )
        database = component.get("database", "none")
        if database not in {"postgres", "firestore", "none"}:
            errors.append(f"{cname}: database must be postgres, firestore, or none")
        bucket = component.get("bucket", "none")
        if bucket not in {"private", "none"}:
            errors.append(f"{cname}: bucket must be private or none")
        if archetype == "config-only":
            if database != "none":
                errors.append(f"{cname}: config-only cannot use a database")
            if bucket != "none":
                errors.append(f"{cname}: config-only cannot use a bucket")
            if component.get("queue"):
                errors.append(f"{cname}: config-only cannot use a queue")

        for sec in component.get("secrets", []):
            if SECRET_ID.fullmatch(str(sec)) is None:
                errors.append(f"{cname}: secret id {sec!r} is not a lowercase slug")

        receiver = component.get("receiver")
        if receiver is not None:
            if not isinstance(receiver, dict):
                errors.append(f"{cname}: receiver must be a mapping")
            else:
                rname = str(receiver.get("name", ""))
                if COMPONENT.fullmatch(rname) is None:
                    errors.append(f"{cname}: receiver name {rname!r} is not a lowercase slug")
                if receiver.get("auth") not in {"shared-secret", "public", "iap"}:
                    errors.append(f"{cname}: receiver auth must be shared-secret, public, or iap")
                if receiver.get("queue") and COMPONENT.fullmatch(str(receiver["queue"])) is None:
                    errors.append(f"{cname}: receiver queue {receiver['queue']!r} is not a lowercase slug")

        jobs = component.get("jobs")
        if archetype == "scheduled-jobs" and (not isinstance(jobs, list) or not jobs):
            errors.append(f"{cname}: scheduled-jobs requires a non-empty jobs list")
        if jobs is not None:
            if not isinstance(jobs, list) or not jobs:
                errors.append(f"{cname}: jobs must be a non-empty list")
            else:
                seen_jobs = set()
                for job in jobs:
                    if not isinstance(job, dict):
                        errors.append(f"{cname}: each job must be a mapping")
                        continue
                    jname = str(job.get("name", ""))
                    if JOB_NAME.fullmatch(jname) is None:
                        errors.append(f"{cname}: job name {jname!r} is not a lowercase slug")
                    if jname in seen_jobs:
                        errors.append(f"{cname}: duplicate job {jname}")
                    seen_jobs.add(jname)
                    if not job.get("command") or not isinstance(job.get("command"), str):
                        errors.append(f"{cname}.{jname}: command is required")
                    if not isinstance(job.get("enabled", True), bool):
                        errors.append(f"{cname}.{jname}: enabled must be true or false")
                    schedules = job.get("schedules", [])
                    if not isinstance(schedules, list):
                        errors.append(f"{cname}.{jname}: schedules must be a list")
                    for sec in job.get("secrets", []):
                        if SECRET_ID.fullmatch(str(sec)) is None:
                            errors.append(f"{cname}.{jname}: secret id {sec!r} is not a lowercase slug")
    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: scripts/check_manifest.py <service.yaml>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    errors = check(parse(path.read_text()))
    if errors:
        for error in errors:
            print(f"{path}: {error}", file=sys.stderr)
        return 1
    print(f"{path}: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
