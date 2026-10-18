#!/usr/bin/env python3
"""Check a service.yaml against the facts the generator understands."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from yaml_subset import parse

ROOT = Path(__file__).resolve().parents[1]
NAME = re.compile(r"^[a-z][a-z0-9-]{1,48}$")
COMPONENT = re.compile(r"^[a-z][a-z0-9-]{1,40}$")

ARCHETYPES = {
    "cloud-run-service": {
        "parts": {"api", "ui"},
        "required": {"api"},
        "auth": {"app-login", "iap", "public"},
    },
    "cloud-run-job": {
        "parts": {"job"},
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
    components = data.get("components")
    if not isinstance(components, list) or not components:
        errors.append("components must be a non-empty list")
        return errors
    seen = set()
    for component in components:
        if not isinstance(component, dict):
            errors.append("each component must be a mapping")
            continue
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
                "cloud-run-job, vm-worker, or config-only."
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
