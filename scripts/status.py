#!/usr/bin/env python3
"""Inspect an existing repository and check SDLC alignment."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_rules import VERSION, check_bundle
from check_manifest import check, normalize
from yaml_subset import parse

ROOT = Path(__file__).resolve().parents[1]


def selected_rules_for_manifest(app: dict) -> list[str]:
    mapping = parse((ROOT / "mapping.yaml").read_text())
    normalized = normalize(app)
    rules = ["always"]
    for comp in normalized.get("components", []):
        for part in comp.get("parts", []):
            spec = mapping["parts"].get(part, {})
            for r in spec.get("rules", []):
                if r not in rules:
                    rules.append(r)
        db = comp.get("database", "none")
        if db == "postgres":
            for r in ("database", "terraform"):
                if r not in rules:
                    rules.append(r)
        elif db == "firestore":
            for r in ("firestore", "terraform"):
                if r not in rules:
                    rules.append(r)
        if comp.get("bucket", "none") == "private" or comp.get("queue") or comp.get("secrets") or comp.get("alerts"):
            if "terraform" not in rules:
                rules.append("terraform")
    return rules


def inspect_repo(repo_dir: Path) -> dict:
    manifest_path = repo_dir / "service.yaml"
    has_manifest = manifest_path.is_file()
    manifest_errors: list[str] = []
    manifest_data: dict = {}
    unmet: list[dict] = []

    if has_manifest:
        try:
            manifest_data = parse(manifest_path.read_text())
            manifest_errors = check(manifest_data)
            unmet = manifest_data.get("unmet", []) if isinstance(manifest_data.get("unmet"), list) else []
        except SystemExit as exc:
            manifest_errors = [str(exc)]

    pyprojects = list(repo_dir.glob("**/pyproject.toml"))
    package_jsons = [p for p in repo_dir.glob("**/package.json") if "node_modules" not in p.parts]
    py_tests = list(repo_dir.glob("**/test_*.py"))
    ui_tests = [
        p
        for p in repo_dir.glob("**/*.test.{ts,tsx}")
        if "node_modules" not in p.parts
    ]
    tf_files = [p for p in repo_dir.glob("**/infra/main.tf") if ".terraform" not in p.parts]

    detected_capabilities: list[str] = []
    all_py_text = "\n".join(p.read_text(errors="ignore") for p in pyprojects)
    if "firestore" in all_py_text:
        detected_capabilities.append("firestore")
    if "sqlalchemy" in all_py_text or "psycopg" in all_py_text:
        detected_capabilities.append("postgres")
    if "google-cloud-storage" in all_py_text:
        detected_capabilities.append("bucket")
    if "google-cloud-tasks" in all_py_text:
        detected_capabilities.append("queue")
    if "google-cloud-secret-manager" in all_py_text:
        detected_capabilities.append("secrets")

    legacy_deploy = []
    for candidate in ("deploy.sh", "vercel.json", "cloudbuild.yaml", ".clasp.json", "appsscript.json"):
        if (repo_dir / candidate).exists() or any(repo_dir.glob(f"**/{candidate}")):
            legacy_deploy.append(candidate)

    expected_rules = selected_rules_for_manifest(manifest_data) if (has_manifest and not manifest_errors) else ["always"]
    rule_errors = check_bundle(repo_dir, expected_rules)

    missing_hygiene = []
    for req in (".gitignore", "README.md", ".github/workflows/ci.yml"):
        if not (repo_dir / req).is_file():
            missing_hygiene.append(req)

    aligned = (
        has_manifest
        and not manifest_errors
        and not rule_errors
        and not missing_hygiene
    )

    return {
        "aligned": aligned,
        "has_service_yaml": has_manifest,
        "manifest_errors": manifest_errors,
        "rule_version": VERSION,
        "expected_rules": expected_rules,
        "rule_errors": rule_errors,
        "missing_hygiene": missing_hygiene,
        "detected": {
            "python": bool(pyprojects),
            "react": bool(package_jsons),
            "python_tests": len(py_tests),
            "ui_tests": len(ui_tests),
            "terraform": bool(tf_files),
            "capabilities_in_deps": detected_capabilities,
            "legacy_deploy": legacy_deploy,
        },
        "unmet": unmet,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo", nargs="?", type=Path, default=Path("."))
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    parser.add_argument("--check", action="store_true", help="Exit non-zero if repo is not aligned")
    args = parser.parse_args(argv)

    report = inspect_repo(args.repo.resolve())
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        status = "ok" if report["aligned"] else "needs-alignment"
        print(f"sdlc status: {status}")
        for err in report["manifest_errors"] + report["rule_errors"]:
            print(f"  - {err}", file=sys.stderr)
        for missing in report["missing_hygiene"]:
            print(f"  - missing {missing}", file=sys.stderr)

    if args.check and not report["aligned"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
