#!/usr/bin/env python3
"""Validate a service.yaml against the fields in service.schema.json.

The schema is JSON Schema. This script checks the same required fields and
enums without a third-party dependency so CI can run it with the system Python.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "service.schema.json"

ARCHETYPES = {
    "cloud-run-service",
    "cloud-run-job",
    "vm-worker",
    "apps-script",
    "config-only",
}
AUTH = {"app-login", "iap", "public"}
NAME = re.compile(r"^[a-z][a-z0-9-]{1,48}$")


def parse_flat_yaml(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for line_number, raw in enumerate(path.read_text().splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if ":" not in line:
            raise SystemExit(f"{path}:{line_number}: expected key: value")
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip("\"'")
    return data


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: scripts/check_manifest.py <service.yaml>", file=sys.stderr)
        return 2
    manifest_path = Path(argv[1])
    schema = json.loads(SCHEMA_PATH.read_text())
    required = schema["required"]
    data = parse_flat_yaml(manifest_path)
    extra = sorted(set(data) - set(schema["properties"]))
    missing = [key for key in required if key not in data or not data[key]]
    errors: list[str] = []
    if extra:
        errors.append(f"unknown fields: {', '.join(extra)}")
    if missing:
        errors.append(f"missing fields: {', '.join(missing)}")
    name = data.get("name", "")
    if name and NAME.fullmatch(name) is None:
        errors.append(f"name {name!r} must match {NAME.pattern}")
    if data.get("archetype") and data["archetype"] not in ARCHETYPES:
        errors.append(f"archetype must be one of: {', '.join(sorted(ARCHETYPES))}")
    if data.get("auth") and data["auth"] not in AUTH:
        errors.append(f"auth must be one of: {', '.join(sorted(AUTH))}")
    if errors:
        for error in errors:
            print(f"{manifest_path}: {error}", file=sys.stderr)
        return 1
    print(f"{manifest_path}: ok ({data['name']}, {data['archetype']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
