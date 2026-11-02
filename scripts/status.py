#!/usr/bin/env python3
"""Inspect an existing repository and render the 17-point Opptra SDLC scorecard."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
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
        elif db == "bigquery" or comp.get("bigquery"):
            if "bigquery" not in rules:
                rules.append("bigquery")
        if (
            comp.get("bucket", "none") == "private"
            or comp.get("queue")
            or comp.get("secrets")
            or comp.get("alerts")
        ):
            if "terraform" not in rules:
                rules.append("terraform")
    return rules


def _check_resource_prefixes(manifest_data: dict, normalized_data: dict, repo_dir: Path) -> tuple[bool, str, list[str]]:
    if not manifest_data or not normalized_data:
        return False, "No service.yaml", ["Define prefix and resources in service.yaml"]
    app_name = str(manifest_data.get("name", ""))
    prefix = str(manifest_data.get("prefix") or app_name)
    valid_prefixes = tuple(
        f"{p}-" for p in dict.fromkeys([prefix, app_name]) if p
    )
    unprefixed: list[str] = []
    for comp in normalized_data.get("components", []):
        if comp.get("archetype") == "config-only":
            continue
        q = comp.get("queue")
        if q and not str(q).replace("_", "-").startswith(valid_prefixes):
            unprefixed.append(f"queue:{q}")
        recv = comp.get("receiver")
        if isinstance(recv, dict) and recv.get("name"):
            rname = str(recv["name"]).replace("_", "-")
            if not rname.startswith(valid_prefixes):
                unprefixed.append(f"receiver:{recv['name']}")
        secret_map = comp.get("secret_map") if isinstance(comp.get("secret_map"), dict) else {}
        existing_secs = {str(s) for s in comp.get("existing_secrets", [])}
        for s in comp.get("secrets", []):
            if str(s) in secret_map or str(s) in existing_secs:
                continue
            sname = str(s).replace("_", "-")
            if not sname.startswith(valid_prefixes):
                unprefixed.append(f"secret:{s}")
        for j in comp.get("jobs", []):
            jname = str(j.get("name", "")).replace("_", "-")
            if jname and not jname.startswith(valid_prefixes):
                unprefixed.append(f"job:{j.get('name')}")
    if unprefixed:
        summary = f"prefix='{prefix}'; unprefixed in service.yaml: {', '.join(unprefixed[:6])}" + (
            f" (+{len(unprefixed) - 6} more)" if len(unprefixed) > 6 else ""
        )
        return False, summary, unprefixed
    return True, f"prefix='{prefix}' applied to all jobs, services, queues, and secrets (or mapped via secret_map)", []


def _git_branches(repo_dir: Path) -> list[str]:
    if not (repo_dir / ".git").exists():
        return []
    res = subprocess.run(
        ["git", "-C", str(repo_dir), "branch", "-a", "--format=%(refname:short)"],
        check=False,
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        return []
    return [line.strip() for line in res.stdout.splitlines() if line.strip()]


def inspect_repo(repo_dir: Path) -> dict:
    manifest_path = repo_dir / "service.yaml"
    has_manifest = manifest_path.is_file()
    manifest_errors: list[str] = []
    manifest_data: dict = {}
    normalized_data: dict = {}
    unmet: list[dict] = []

    if has_manifest:
        try:
            manifest_data = parse(manifest_path.read_text())
            manifest_errors = check(manifest_data)
            if not manifest_errors:
                normalized_data = normalize(manifest_data)
            unmet = (
                manifest_data.get("unmet", [])
                if isinstance(manifest_data.get("unmet"), list)
                else []
            )
        except SystemExit as exc:
            manifest_errors = [str(exc)]

    pyprojects = [
        p
        for p in repo_dir.glob("**/pyproject.toml")
        if ".venv" not in p.parts and "node_modules" not in p.parts
    ]
    req_files = [
        p
        for p in repo_dir.glob("**/requirements*.txt")
        if ".venv" not in p.parts and "node_modules" not in p.parts
    ]
    py_files = [
        p
        for p in repo_dir.glob("**/*.py")
        if ".venv" not in p.parts and "node_modules" not in p.parts
    ]
    package_jsons = [
        p
        for p in repo_dir.glob("**/package.json")
        if "node_modules" not in p.parts and ".venv" not in p.parts
    ]
    py_tests = [
        p
        for p in repo_dir.glob("**/test_*.py")
        if ".venv" not in p.parts and "node_modules" not in p.parts
    ]
    ui_tests = [
        p
        for p in repo_dir.glob("**/*.test.{ts,tsx}")
        if "node_modules" not in p.parts
    ]
    tf_files = [
        p for p in repo_dir.glob("**/infra/main.tf") if ".terraform" not in p.parts
    ]
    custom_tf_files = [
        p for p in repo_dir.glob("**/infra/*.keep.tf") if ".terraform" not in p.parts
    ]
    bq_sql_files = [
        p
        for p in list(repo_dir.glob("scripts/**/*.sql"))
        + list(repo_dir.glob("bq-schema/**/*.sql"))
    ]

    detected_capabilities: list[str] = []
    dep_text = "\n".join(
        p.read_text(errors="ignore") for p in (*pyprojects, *req_files)
    )
    if "firestore" in dep_text:
        detected_capabilities.append("firestore")
    if "sqlalchemy" in dep_text or "psycopg" in dep_text:
        detected_capabilities.append("postgres")
    if "bigquery" in dep_text or bq_sql_files:
        detected_capabilities.append("bigquery")
    if "google-cloud-storage" in dep_text:
        detected_capabilities.append("bucket")
    if "google-cloud-tasks" in dep_text:
        detected_capabilities.append("queue")
    if "google-cloud-secret-manager" in dep_text or "secretmanager" in dep_text:
        detected_capabilities.append("secrets")

    legacy_deploy: list[str] = []
    for candidate in (
        "deploy.sh",
        "vercel.json",
        "fly.toml",
        "cloudbuild.yaml",
        ".clasp.json",
        "appsscript.json",
    ):
        if (repo_dir / candidate).exists() or any(repo_dir.glob(f"**/{candidate}")):
            legacy_deploy.append(candidate)

    has_openspec_dir = (repo_dir / "openspec").is_dir()
    has_openspec_cli = shutil.which("openspec") is not None

    agents_text = (
        (repo_dir / "AGENTS.md").read_text(errors="ignore")
        if (repo_dir / "AGENTS.md").is_file()
        else ""
    )
    claude_text = (
        (repo_dir / "CLAUDE.md").read_text(errors="ignore")
        if (repo_dir / "CLAUDE.md").is_file()
        else ""
    )
    combined_rules_text = agents_text + "\n" + claude_text
    has_managed_always = "<!-- sdlc-rule: always -->" in combined_rules_text

    rule_pillars = {
        "5.1_tdd": {
            "title": "Test-Driven Development (TDD)",
            "ok": (
                has_managed_always
                or "uv run pytest" in combined_rules_text
                or "test-first" in combined_rules_text.lower()
                or "failing test" in combined_rules_text.lower()
            ),
            "current": "Present"
            if (
                has_managed_always
                or "uv run pytest" in combined_rules_text
                or "test-first" in combined_rules_text.lower()
            )
            else "Missing",
            "action": "Keep TDD & component test commands"
            if (
                has_managed_always
                or "uv run pytest" in combined_rules_text
                or "test-first" in combined_rules_text.lower()
            )
            else "Add TDD rule and component test commands",
        },
        "5.2_commit_pr_github": {
            "title": "Commit, PR & GitHub Branch Flow",
            "ok": (
                has_managed_always
                or (
                    "feat: <ticket-id>" in combined_rules_text
                    and "staging" in combined_rules_text
                    and "separate pull requests" in combined_rules_text
                )
            ),
            "current": "Complete"
            if (
                has_managed_always
                or (
                    "feat: <ticket-id>" in combined_rules_text
                    and "staging" in combined_rules_text
                )
            )
            else ("Partial" if "pull request" in combined_rules_text.lower() else "Missing"),
            "action": "None"
            if (
                has_managed_always
                or (
                    "feat: <ticket-id>" in combined_rules_text
                    and "staging" in combined_rules_text
                )
            )
            else "Sync commit/branch format, staging push, and infra PR split rules",
        },
        "5.3_linear": {
            "title": "Linear Ticket Rules",
            "ok": "Linear issue" in combined_rules_text
            and "Do not invent a ticket id" in combined_rules_text,
            "current": "Present"
            if "Linear issue" in combined_rules_text
            else "Missing",
            "action": "None"
            if "Linear issue" in combined_rules_text
            else "Add mandatory Linear issue & ticket-ID rule",
        },
        "5.4_openspec": {
            "title": "OpenSpec Rules",
            "ok": "OpenSpec" in combined_rules_text and "openspec/" in combined_rules_text,
            "current": "Present" if "openspec/" in combined_rules_text else "Missing",
            "action": "None"
            if "openspec/" in combined_rules_text
            else "Add mandatory OpenSpec before feature code rule",
        },
        "5.5_infra_gcp_terraform": {
            "title": "Infra (GCP Only, Terraform, Resource Prefix, No Laptop Deploy)",
            "ok": "Do not add deploy.sh" in combined_rules_text
            and "<prefix>-<resource>" in combined_rules_text
            and "Do not apply Terraform against production from a laptop"
            in combined_rules_text,
            "current": "Present (with <prefix>-<resource> rule)"
            if (
                "Do not add deploy.sh" in combined_rules_text
                and "<prefix>-<resource>" in combined_rules_text
            )
            else "Missing or outdated resource prefix rule",
            "action": "None"
            if (
                "Do not add deploy.sh" in combined_rules_text
                and "<prefix>-<resource>" in combined_rules_text
            )
            else "Sync GCP + Terraform + <prefix>-<resource> naming rule",
        },
        "5.6_github_workflows": {
            "title": "GitHub Workflow Guidelines",
            "ok": ".github/workflows" in combined_rules_text
            and (repo_dir / ".github" / "workflows" / "ci.yml").is_file(),
            "current": "Present"
            if (repo_dir / ".github" / "workflows" / "ci.yml").is_file()
            else "Missing",
            "action": "None"
            if (repo_dir / ".github" / "workflows" / "ci.yml").is_file()
            else "Sync workflow rules and generate .github/workflows/ci.yml",
        },
        "5.7_logging_and_exit_codes": {
            "title": "Structured JSON Logging & Job Exit Codes",
            "ok": (
                "<!-- sdlc-rule: python -->" in combined_rules_text
                or "severity, message, service, and environment" in combined_rules_text
            ),
            "current": "Present"
            if (
                "<!-- sdlc-rule: python -->" in combined_rules_text
                or "severity, message, service, and environment" in combined_rules_text
            )
            else "Missing",
            "action": "None"
            if (
                "<!-- sdlc-rule: python -->" in combined_rules_text
                or "severity, message, service, and environment" in combined_rules_text
            )
            else "Add JSON stdout logging & non-zero 429/5xx job exit rules",
        },
        "5.8_data_and_warehouse": {
            "title": "Database, Firestore & BigQuery Safety",
            "ok": True
            if not detected_capabilities
            else (
                "<!-- sdlc-rule: database -->" in combined_rules_text
                or "<!-- sdlc-rule: firestore -->" in combined_rules_text
                or "<!-- sdlc-rule: bigquery -->" in combined_rules_text
                or "prevent_destroy" in combined_rules_text
                or "locks/{job}" in combined_rules_text
                or "currencies" in combined_rules_text
            ),
            "current": "Present"
            if (
                "<!-- sdlc-rule: database -->" in combined_rules_text
                or "<!-- sdlc-rule: firestore -->" in combined_rules_text
                or "<!-- sdlc-rule: bigquery -->" in combined_rules_text
                or "prevent_destroy" in combined_rules_text
                or "locks/{job}" in combined_rules_text
                or "currencies" in combined_rules_text
                or not detected_capabilities
            )
            else "Missing for detected data store",
            "action": "None"
            if (
                "<!-- sdlc-rule: database -->" in combined_rules_text
                or "<!-- sdlc-rule: firestore -->" in combined_rules_text
                or "<!-- sdlc-rule: bigquery -->" in combined_rules_text
                or "prevent_destroy" in combined_rules_text
                or "locks/{job}" in combined_rules_text
                or "currencies" in combined_rules_text
                or not detected_capabilities
            )
            else f"Add data safety rules for {', '.join(detected_capabilities)}",
        },
        "5.9_secrets_and_pii": {
            "title": "Secrets & PII Protection",
            "ok": "Do not commit a .env or a credential" in combined_rules_text,
            "current": "Present"
            if "Do not commit a .env or a credential" in combined_rules_text
            else "Missing",
            "action": "None"
            if "Do not commit a .env or a credential" in combined_rules_text
            else "Add secret/credential & PII redaction rules",
        },
        "5.10_product_contract": {
            "title": "Product / Domain Contract Preservation",
            "ok": True,
            "current": "Preserved under ## Product contract"
            if "## Product contract" in combined_rules_text
            else "Standard rules only (no extra domain block)",
            "action": "Keep domain rules outside <!-- sdlc-rules-end -->",
        },
    }

    expected_rules = (
        selected_rules_for_manifest(manifest_data)
        if (has_manifest and not manifest_errors)
        else ["always"]
    )
    rule_errors = check_bundle(repo_dir, expected_rules)

    missing_hygiene: list[str] = []
    for req in (".gitignore", "README.md", ".github/workflows/ci.yml"):
        if not (repo_dir / req).is_file():
            missing_hygiene.append(req)

    # Check if ci.yml references working_directory paths that actually exist
    ci_path_errors: list[str] = []
    ci_file = repo_dir / ".github" / "workflows" / "ci.yml"
    if ci_file.is_file():
        for line in ci_file.read_text(errors="ignore").splitlines():
            stripped = line.strip()
            if stripped.startswith("working_directory:"):
                wd = stripped.split(":", 1)[1].strip()
                if wd != "." and not (repo_dir / wd).is_dir():
                    ci_path_errors.append(f"ci.yml references missing directory {wd}")

    branches = _git_branches(repo_dir)
    has_staging = any(b == "staging" or b.endswith("/staging") for b in branches)
    has_production = any(b == "production" or b.endswith("/production") for b in branches)
    prefix_ok, prefix_summary, unprefixed_items = _check_resource_prefixes(
        manifest_data, normalized_data, repo_dir
    )

    components_list = normalized_data.get("components", []) if normalized_data else []
    comp_summary = (
        ", ".join(
            f"{c['name']} ({c['archetype']}, {c.get('region', manifest_data.get('region', 'asia-south1'))})"
            for c in components_list
        )
        if components_list
        else f"Unmapped (detected Python={bool(py_files)}, React={bool(package_jsons)})"
    )

    pillars_passed = sum(1 for p in rule_pillars.values() if p["ok"])
    total_pillars = len(rule_pillars)

    sections_14 = [
        {
            "id": 1,
            "area": "Components & Architecture",
            "current": comp_summary,
            "target": "All services, jobs, regions, and repo paths declared",
            "status": "Up to the mark" if (has_manifest and not manifest_errors) else "Needs mapping",
            "action": "None"
            if (has_manifest and not manifest_errors)
            else "Declare all components, regions, and paths in service.yaml",
        },
        {
            "id": 2,
            "area": "OpenSpec Setup",
            "current": f"CLI={'installed' if has_openspec_cli else 'missing'}, openspec/={'present' if has_openspec_dir else 'missing'}",
            "target": "openspec CLI installed + openspec/ initialized (Strongly Recommended)",
            "status": "Up to the mark"
            if (has_openspec_cli and has_openspec_dir)
            else ("Partial" if (has_openspec_cli or has_openspec_dir) else "Missing"),
            "action": "None"
            if (has_openspec_cli and has_openspec_dir)
            else "Strongly Recommended: run `openspec init --tools cursor,claude`",
        },
        {
            "id": 3,
            "area": "Linear Setup",
            "current": "Rule present in AGENTS.md"
            if rule_pillars["5.3_linear"]["ok"]
            else "Linear rule missing",
            "target": "Linear MCP connected + mandatory ticket rule (Strongly Recommended)",
            "status": "Up to the mark" if rule_pillars["5.3_linear"]["ok"] else "Missing",
            "action": "Verify Linear MCP in IDE"
            if rule_pillars["5.3_linear"]["ok"]
            else "Strongly Recommended: connect Linear MCP & sync rule 5.3",
        },
        {
            "id": 4,
            "area": "service.yaml Manifest",
            "current": "Valid service.yaml"
            if (has_manifest and not manifest_errors)
            else ("Invalid: " + "; ".join(manifest_errors) if has_manifest else "Missing"),
            "target": "Valid root service.yaml with components, secrets & unmet list",
            "status": "Up to the mark"
            if (has_manifest and not manifest_errors)
            else "Missing / Invalid",
            "action": "None"
            if (has_manifest and not manifest_errors)
            else "Create or fix service.yaml and run `odlc check`",
        },
        {
            "id": 5,
            "area": "Agentic Rules (AGENTS.md, CLAUDE.md, .cursor/rules)",
            "current": f"{pillars_passed}/{total_pillars} pillars passing"
            + (f" ({len(rule_errors)} file/stamp issues)" if rule_errors else ""),
            "target": "10/10 pillars + .cursor/rules/*.mdc + Product Contract preserved",
            "status": "Up to the mark"
            if (pillars_passed == total_pillars and not rule_errors)
            else f"Partial ({pillars_passed}/{total_pillars})",
            "action": "None"
            if (pillars_passed == total_pillars and not rule_errors)
            else "Run `odlc sync-infra` to update managed rules block (Table B)",
        },
        {
            "id": 6,
            "area": "GitHub Workflows (.github/workflows)",
            "current": (
                "ci.yml present (valid paths)"
                if (ci_file.is_file() and not ci_path_errors)
                else (
                    "ci.yml has broken paths: " + "; ".join(ci_path_errors)
                    if ci_file.is_file()
                    else "Missing ci.yml"
                )
            ),
            "target": "PR-only ci.yml matching repo paths + plan/deploy workflows",
            "status": "Up to the mark"
            if (ci_file.is_file() and not ci_path_errors)
            else "Needs fix / Missing",
            "action": "None"
            if (ci_file.is_file() and not ci_path_errors)
            else "Set component `path` / `frontend_path` and run `odlc sync-infra`",
        },
        {
            "id": 7,
            "area": "Testing Setup & Coverage",
            "current": f"Python test files: {len(py_tests)}, UI test files: {len(ui_tests)}, pyproject.toml: {bool(pyprojects)}",
            "target": "Ruff + pytest for Python; lint + typecheck + test for UI",
            "status": "Up to the mark"
            if ((not py_files or (py_tests and pyprojects)) and (not package_jsons or True))
            else "Partial",
            "action": "None"
            if (not py_files or (py_tests and pyprojects))
            else "Run `odlc add-tests` or add pyproject.toml / test scripts",
        },
        {
            "id": 8,
            "area": "Deployment & Infrastructure",
            "current": (
                f"Terraform infra/ present ({len(tf_files)} modules"
                + (f", {len(custom_tf_files)} custom.keep.tf" if custom_tf_files else "")
                + ")"
                + (f"; legacy scripts: {', '.join(legacy_deploy)}" if legacy_deploy else "")
                if tf_files
                else (
                    f"Legacy deploy only ({', '.join(legacy_deploy)})"
                    if legacy_deploy
                    else "No deploy files"
                )
            ),
            "target": "Terraform in infra/ (plus custom.keep.tf for extensions) + GitHub Actions WIF",
            "status": "Up to the mark"
            if (tf_files and not legacy_deploy)
            else ("Transitional" if legacy_deploy else "Missing"),
            "action": "None"
            if (tf_files and not legacy_deploy)
            else "Run `/adopt-terraform` to scan deploy scripts, generate `infra/` + `imports.tf.example`, and retire legacy scripts",
        },
        {
            "id": 9,
            "area": "Git Branches & Governance",
            "current": f"CODEOWNERS={(repo_dir / '.github/CODEOWNERS').is_file()}, PR template={(repo_dir / '.github/pull_request_template.md').is_file()}, staging={has_staging}, production={has_production}",
            "target": "main, staging, production branches + CODEOWNERS + PR template",
            "status": "Up to the mark"
            if (
                (repo_dir / ".github/CODEOWNERS").is_file()
                and (repo_dir / ".github/pull_request_template.md").is_file()
            )
            else "Partial",
            "action": "None"
            if (repo_dir / ".github/CODEOWNERS").is_file()
            else "Create staging/production branches & write CODEOWNERS + PR template",
        },
        {
            "id": 10,
            "area": "Secrets, Credentials & Security",
            "current": f".gitignore={(repo_dir / '.gitignore').is_file()}, local secrets/ dir={(repo_dir / 'secrets').is_dir()}",
            "target": "Secret IDs in service.yaml (Secret Manager); no keys in Git",
            "status": "Up to the mark"
            if (
                (repo_dir / ".gitignore").is_file()
                and not (repo_dir / ".env").is_file()
            )
            else "Review needed",
            "action": "Ensure .env and secrets/ are in .gitignore; keep values in Secret Manager",
        },
        {
            "id": 11,
            "area": "Database, Warehouse & State",
            "current": ", ".join(detected_capabilities) if detected_capabilities else "none",
            "target": "Declared in service.yaml with matching client/migration rules",
            "status": "Up to the mark" if has_manifest else "Needs declaration",
            "action": "None"
            if has_manifest
            else "Declare database/bigquery/bucket in service.yaml",
        },
        {
            "id": 12,
            "area": "Authentication & Access Control",
            "current": ", ".join(f"{c['name']}:{c['auth']}" for c in components_list)
            if components_list
            else "Unmapped",
            "target": "iap for staff UIs, shared-secret for webhooks, none for jobs",
            "status": "Up to the mark" if components_list else "Needs mapping",
            "action": "None"
            if components_list
            else "Record auth mode per component in service.yaml",
        },
        {
            "id": 13,
            "area": "Observability, Health & Alerts",
            "current": "JSON logging & alerts configured"
            if rule_pillars["5.7_logging_and_exit_codes"]["ok"]
            else "Standard logging",
            "target": "/api/health + JSON logs + non-zero exit on job errors + alerts",
            "status": "Up to the mark"
            if rule_pillars["5.7_logging_and_exit_codes"]["ok"]
            else "Partial",
            "action": "None"
            if rule_pillars["5.7_logging_and_exit_codes"]["ok"]
            else "Enable alerts: true and structured JSON logging",
        },
        {
            "id": 14,
            "area": "README, Runbook & Local Dev",
            "current": "Present" if (repo_dir / "README.md").is_file() else "Missing",
            "target": "Purpose, local run, tests, deploy flow, and unmet notes",
            "status": "Up to the mark"
            if (
                (repo_dir / "README.md").is_file()
                and "## Deploy" in (repo_dir / "README.md").read_text(errors="ignore")
            )
            else "Incomplete",
            "action": "None"
            if (
                (repo_dir / "README.md").is_file()
                and "## Deploy" in (repo_dir / "README.md").read_text(errors="ignore")
            )
            else "Sync README sections while preserving existing architecture notes",
        },
        {
            "id": 15,
            "area": "Local Development & .env.example",
            "current": (
                f".env.example={(repo_dir / '.env.example').is_file()}, "
                f"Makefile={(repo_dir / 'Makefile').is_file()}, "
                f"devcontainer={(repo_dir / '.devcontainer' / 'devcontainer.json').is_file()}"
            ),
            "target": ".env.example + Makefile (`make setup`, `make dev`, `make test`) + .devcontainer/devcontainer.json",
            "status": "Up to the mark"
            if (
                (repo_dir / ".env.example").is_file()
                and (repo_dir / "Makefile").is_file()
                and (repo_dir / ".devcontainer" / "devcontainer.json").is_file()
            )
            else "Missing / Partial",
            "action": "None"
            if (
                (repo_dir / ".env.example").is_file()
                and (repo_dir / "Makefile").is_file()
                and (repo_dir / ".devcontainer" / "devcontainer.json").is_file()
            )
            else "Run `odlc sync-infra` to generate `.env.example`, `Makefile`, and `.devcontainer`",
        },
        {
            "id": 16,
            "area": "External Resource Prefixing (<prefix>-<resource>)",
            "current": prefix_summary,
            "target": "All external GCP resources (jobs, services, queues, secrets, buckets) prefixed with `<prefix>-`",
            "status": "Up to the mark" if prefix_ok else "Needs prefixing",
            "action": "None"
            if prefix_ok
            else f"Prefix {', '.join(unprefixed_items[:5])} with `{manifest_data.get('prefix') or manifest_data.get('name', '<prefix>')}-` in service.yaml and run `odlc sync-infra`",
        },
        {
            "id": 17,
            "area": "Pre-Commit Hooks & Local CI Gate (.githooks + make ci)",
            "current": (
                f"pre-commit={(repo_dir / '.githooks/pre-commit').is_file()}, "
                f"pre-push={(repo_dir / '.githooks/pre-push').is_file()}, "
                f"make ci={'ci:' in (repo_dir / 'Makefile').read_text(errors='ignore') if (repo_dir / 'Makefile').is_file() else False}"
            ),
            "target": ".githooks/pre-commit + .githooks/pre-push + `make ci` verified locally",
            "status": "Up to the mark"
            if (
                (repo_dir / ".githooks/pre-commit").is_file()
                and (repo_dir / ".githooks/pre-push").is_file()
                and (repo_dir / "Makefile").is_file()
                and "ci:" in (repo_dir / "Makefile").read_text(errors="ignore")
            )
            else "Missing / Partial",
            "action": "None"
            if (
                (repo_dir / ".githooks/pre-commit").is_file()
                and (repo_dir / ".githooks/pre-push").is_file()
            )
            else "Run `odlc sync-infra` and execute `.githooks/pre-commit` + `make ci`",
        },
    ]

    aligned = (
        has_manifest
        and not manifest_errors
        and not rule_errors
        and not missing_hygiene
        and not ci_path_errors
    )

    return {
        "aligned": aligned,
        "has_service_yaml": has_manifest,
        "manifest_errors": manifest_errors,
        "rule_version": VERSION,
        "expected_rules": expected_rules,
        "rule_errors": rule_errors,
        "missing_hygiene": missing_hygiene,
        "ci_path_errors": ci_path_errors,
        "openspec": {
            "cli_installed": has_openspec_cli,
            "dir_present": has_openspec_dir,
        },
        "detected": {
            "python": bool(pyprojects or req_files or py_files),
            "react": bool(package_jsons),
            "python_tests": len(py_tests),
            "ui_tests": len(ui_tests),
            "terraform": bool(tf_files),
            "capabilities_in_deps": detected_capabilities,
            "legacy_deploy": legacy_deploy,
        },
        "sections_14": sections_14,
        "rule_pillars_5": rule_pillars,
        "unmet": unmet,
    }


MEANS = {
    1: "This is the list of programs this repo runs. After it is filled in, later changes know which service or job they belong to.",
    2: "OpenSpec is the design note written before feature code. After it is initialized, a feature starts with a spec instead of jumping straight into code.",
    3: "Linear is where the ticket id comes from. After it is connected, branch names, commits, and pull requests use that id.",
    4: "service.yaml is the fact sheet for deploy. After it exists, CI and Terraform are generated from it instead of being edited by hand.",
    5: "These are the rules the agent follows on the next feature or bug. After they are present, the agent keeps the product rules and uses the standard commit, test, and deploy path.",
    6: "These are the GitHub checks and deploy jobs. After they match this repo, a pull request runs the real tests and a staging push deploys only what was pushed.",
    7: "This is how you prove a change. After the test command exists, a bug starts with a failing test and a feature ends with that command passing.",
    8: "This is how the app reaches the cloud. After Terraform is the deploy path, a direct push to staging updates staging, and only a pull request from main into production updates production.",
    9: "These are the three branches. After they exist, developers push tries straight to staging, and main is promoted only into production. Organization rules protect main and production.",
    10: "This keeps passwords out of git. After it is in place, the app reads secret ids from Secret Manager and logs never contain those values.",
    11: "This is where data lives. After it is declared, the app uses Postgres, Firestore, or BigQuery on purpose and does not invent a second database.",
    12: "This is who can open the app. After it is set, staff use Google sign-in, a webhook checks a shared secret, and jobs stay private.",
    13: "This is how you notice a failure. After it is set, a failed job or a server error sends an alert instead of looking like a quiet success.",
    14: "This is the page a teammate reads first. After it matches the repo, they can run, test, and deploy without guessing.",
    15: "This lets you run and test on your laptop first. After it is in place, open the devcontainer or copy `.env.example` to `.env` and run `make setup && make dev` before pushing to staging.",
    16: "This ensures every Cloud Run service, job, scheduler entry, queue, secret, and bucket in shared GCP projects starts with your project prefix (`<prefix>-<resource>`) so resources are easy to identify and never collide.",
    17: "This runs fast secret/branch/manifest checks on `git commit` and runs `make ci` (lint + tests) on `git push` so broken code or secrets never leave your laptop.",
}

PILLAR_MEANS = {
    "5.1": "New behaviour starts with a test. After this rule is in the repo, the agent writes the test before the code.",
    "5.2": "Work lands through a pull request into main. After this rule is in the repo, staging is a direct push and main promotes only to production.",
    "5.3": "Every change names a Linear issue. After this rule is in the repo, the agent stops if Linear is not connected.",
    "5.4": "A feature writes an OpenSpec first. After this rule is in the repo, product code waits until that spec exists.",
    "5.5": "Cloud resources are Terraform on GCP. After this rule is in the repo, a laptop deploy script is no longer the way to ship.",
    "5.6": "GitHub runs the checks. After this rule is in the repo, a pull request must pass ci before it merges.",
    "5.7": "Logs are JSON and a failed fetch fails the job. After this rule is in the repo, an empty run is not mistaken for success.",
    "5.8": "Data changes have a safe path. After this rule is in the repo, schema and warehouse loads follow the store this app actually uses.",
    "5.9": "Secrets and personal data stay out of git and logs. After this rule is in the repo, the agent refuses to commit them.",
    "5.10": "The product rules already in this repo stay. After alignment, those rules remain under Product contract and the standard rules are added above them.",
}


def render_tables(report: dict) -> str:
    lines = [
        "### Table A: 17-Point SDLC Scorecard",
        "",
        "| # | Area | Current Setup | Target Standard | Up to the Mark? | Action / Changes to be Done | What this means for you |",
        "|---|---|---|---|---|---|---|",
    ]
    for sec in report["sections_14"]:
        means = MEANS.get(sec["id"], "")
        lines.append(
            f"| **{sec['id']}** | **{sec['area']}** | {sec['current']} | {sec['target']} | **{sec['status']}** | {sec['action']} | {means} |"
        )

    lines += [
        "",
        "### Table B: Section 5 Breakdown — Agentic Rules (5.1 – 5.10)",
        "",
        "| Sub-step | Rule Pillar | Current State | Up to the Mark? | Changes to be Done | What this means for you |",
        "|---|---|---|---|---|---|",
    ]
    for key, pillar in report["rule_pillars_5"].items():
        num = key.split("_", 1)[0]
        mark = "Yes" if pillar["ok"] else "No"
        means = PILLAR_MEANS.get(num, "")
        lines.append(
            f"| **{num}** | **{pillar['title']}** | {pillar['current']} | **{mark}** | {pillar['action']} | {means} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo", nargs="?", type=Path, default=Path("."))
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    parser.add_argument("--table", action="store_true", help="Print 17-point Markdown tables")
    parser.add_argument("--check", action="store_true", help="Exit non-zero if repo is not aligned")
    args = parser.parse_args(argv)

    report = inspect_repo(args.repo.resolve())
    if args.json:
        print(json.dumps(report, indent=2))
    elif args.table:
        print(render_tables(report))
    else:
        status = "ok" if report["aligned"] else "needs-alignment"
        print(f"odlc status: {status}")
        for err in (
            report["manifest_errors"]
            + report["rule_errors"]
            + report["ci_path_errors"]
        ):
            print(f"  - {err}", file=sys.stderr)
        for missing in report["missing_hygiene"]:
            print(f"  - missing {missing}", file=sys.stderr)

    if args.check and not report["aligned"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
