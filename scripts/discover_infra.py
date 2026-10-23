#!/usr/bin/env python3
"""Scan an existing repository to discover GCP resources, deploy scripts, and Terraform imports."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_manifest import normalize, prefixed_name
from yaml_subset import dump, parse

_GCLOUD_SVC_RE = re.compile(
    r'gcloud\s+run\s+deploy\s+["\']?([a-zA-Z0-9_${}-]+)["\']?(.*?)(?:\n\n|\Z)', re.DOTALL
)
_GCLOUD_JOB_RE = re.compile(
    r'gcloud\s+run\s+jobs\s+(?:deploy|update|create)\s+["\']?([a-zA-Z0-9_${}-]+)["\']?(.*?)(?:\n\n|\Z)',
    re.DOTALL,
)
_FLAG_REGION_RE = re.compile(r"--region[=\s]+([a-z0-9-]+)")
_FLAG_MEM_RE = re.compile(r"--memory[=\s]+([0-9]+[GMK]i?)")
_FLAG_TIMEOUT_RE = re.compile(r"--(?:task-)?timeout[=\s]+([0-9]+)s?")
_FLAG_SECRETS_RE = re.compile(r"--(?:set|update)-secrets[=\s]+[\"']?([^\"'\s\\]+)")
_SECRET_NAME_RE = re.compile(r"=([a-zA-Z0-9_-]+):")
_VAR_ASSIGN_RE = re.compile(r"^([A-Z_][A-Z0-9_]*)=[\"']?([^\"'\n#]+)[\"']?", re.M)


def _clean_var_val(val: str) -> str:
    v = val.strip().strip("\"'")
    if v.startswith("${") and ":-" in v and v.endswith("}"):
        v = v.split(":-", 1)[1][:-1]
    return v


def _resolve_shell_vars(text: str, env_vars: dict[str, str]) -> str:
    out = text
    for k, v in env_vars.items():
        out = out.replace(f"${{{k}}}", v).replace(f"${k}", v)
    return out


def discover_repo(repo_dir: Path) -> dict:
    repo_dir = repo_dir.resolve()
    app_name = re.sub(r"[^a-z0-9-]", "-", repo_dir.name.lower()).strip("-") or "app"

    shell_files = [
        p
        for p in list(repo_dir.glob("deploy/**/*.sh"))
        + list(repo_dir.glob("scripts/**/*.sh"))
        + list(repo_dir.glob("*.sh"))
        if ".venv" not in p.parts and "node_modules" not in p.parts and p.name != "bind-repo.sh"
    ]
    dockerfiles = [
        p
        for p in repo_dir.glob("**/Dockerfile*")
        if ".venv" not in p.parts and "node_modules" not in p.parts
    ]

    services: list[dict] = []
    jobs: list[dict] = []
    secrets_found: list[str] = []
    regions_found: list[str] = []
    prod_project = "opptra-applications"

    for sh in shell_files:
        raw = sh.read_text(errors="ignore")
        joined = raw.replace("\\\n", " ")
        sh_vars = {
            m.group(1): _clean_var_val(m.group(2)) for m in _VAR_ASSIGN_RE.finditer(raw)
        }
        prod_m = re.search(r'prod\)\s+SERVICE=["\']?([a-zA-Z0-9_-]+)["\']?', raw)
        if prod_m:
            sh_vars["SERVICE"] = prod_m.group(1)
        for proj_key in ("PROJECT_ID", "PROJECT"):
            if proj_key in sh_vars and not sh_vars[proj_key].startswith("$"):
                prod_project = sh_vars[proj_key]
        resolved = _resolve_shell_vars(joined, sh_vars)
        rel = str(sh.relative_to(repo_dir))

        for sec_id in _extract_secrets(raw):
            if sec_id not in secrets_found:
                secrets_found.append(sec_id)

        for loop_m in re.finditer(r"for\s+job\s+in\s+([^;\n]+);", raw):
            for tok in loop_m.group(1).split():
                tok_clean = tok.strip("\"'")
                if tok_clean and not tok_clean.startswith("$"):
                    jobs.append(
                        {
                            "name": tok_clean,
                            "source": rel,
                            "region": sh_vars.get("REGION", "asia-south1"),
                            "memory": "2Gi",
                            "timeout_seconds": 3000,
                            "secrets": [],
                        }
                    )

        for match in _GCLOUD_SVC_RE.finditer(resolved):
            name = match.group(1).strip("\"'")
            if "$" in name or name.endswith("-dev"):
                continue
            body = match.group(2)
            region_m = _FLAG_REGION_RE.search(body)
            region = (
                region_m.group(1)
                if region_m
                else sh_vars.get("REGION", "asia-south1")
            )
            if region not in regions_found and not region.startswith("$"):
                regions_found.append(region)
            auth = "public" if "--allow-unauthenticated" in body else "iap"
            sec_ids = _extract_secrets(body)
            for s in sec_ids:
                if s not in secrets_found:
                    secrets_found.append(s)
            services.append(
                {
                    "name": name,
                    "source": rel,
                    "region": region,
                    "auth": auth,
                    "secrets": sec_ids,
                }
            )

        for match in _GCLOUD_JOB_RE.finditer(resolved):
            name = match.group(1).strip("\"'")
            if "$" in name:
                continue
            body = match.group(2)
            region_m = _FLAG_REGION_RE.search(body)
            region = (
                region_m.group(1)
                if region_m
                else sh_vars.get("REGION", "asia-south1")
            )
            if region not in regions_found and not region.startswith("$"):
                regions_found.append(region)
            mem_m = _FLAG_MEM_RE.search(body)
            timeout_m = _FLAG_TIMEOUT_RE.search(body)
            sec_ids = _extract_secrets(body)
            for s in sec_ids:
                if s not in secrets_found:
                    secrets_found.append(s)
            if any(j["name"] == name for j in jobs):
                continue
            jobs.append(
                {
                    "name": name,
                    "source": rel,
                    "region": region,
                    "memory": mem_m.group(1) if mem_m else "1Gi",
                    "timeout_seconds": int(timeout_m.group(1)) if timeout_m else 1800,
                    "secrets": sec_ids,
                }
            )

    # Check dependency files and SQL for data stores
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
    pkg_files = [
        p
        for p in repo_dir.glob("**/package.json")
        if "node_modules" not in p.parts and ".venv" not in p.parts
    ]
    bq_sql = list(repo_dir.glob("scripts/**/*.sql")) + list(repo_dir.glob("bq-schema/**/*.sql"))
    dep_text = "\n".join(
        p.read_text(errors="ignore") for p in (*pyprojects, *req_files, *pkg_files)
    )

    stores: list[str] = []
    if "sqlalchemy" in dep_text or "psycopg" in dep_text or (repo_dir / "prisma").is_dir():
        stores.append("postgres")
    if "firestore" in dep_text:
        stores.append("firestore")
    if "bigquery" in dep_text or bq_sql:
        stores.append("bigquery")
    if "google-cloud-storage" in dep_text:
        stores.append("bucket")
    if "google-cloud-tasks" in dep_text:
        stores.append("queue")

    has_ui = any(
        "react" in p.read_text(errors="ignore") or "vite" in p.read_text(errors="ignore")
        for p in pkg_files
    )

    legacy_hosts = []
    for f in ("vercel.json", "fly.toml", "cloudbuild.yaml"):
        if (repo_dir / f).is_file():
            legacy_hosts.append(f)

    resources_table: list[dict] = []
    for svc in services:
        resources_table.append(
            {
                "resource": svc["name"],
                "kind": f"Cloud Run Service ({svc['region']}, auth={svc['auth']})",
                "source": svc["source"],
                "module": "modules/cloud-run-service",
                "action": "Import if live in GCP, else Create",
                "means": "Replaces gcloud run deploy in shell script with Terraform state.",
            }
        )
    for job in jobs:
        resources_table.append(
            {
                "resource": job["name"],
                "kind": f"Cloud Run Job ({job['region']}, {job['memory']}, {job['timeout_seconds']}s)",
                "source": job["source"],
                "module": "modules/cloud-run-job + modules/schedule",
                "action": "Import if live in GCP, else Create",
                "means": "Manages job image, memory, timeout, and Cloud Scheduler crons in Terraform.",
            }
        )
    if secrets_found:
        resources_table.append(
            {
                "resource": ", ".join(secrets_found[:6])
                + (f" (+{len(secrets_found) - 6} more)" if len(secrets_found) > 6 else ""),
                "kind": f"Secret Manager ({len(secrets_found)} secret IDs)",
                "source": "deploy scripts (--set-secrets)",
                "module": "modules/secrets",
                "action": "Import existing secret shells (versions stay untouched)",
                "means": "Grants runtime service account secretAccessor without storing values in Git.",
            }
        )
    for st in stores:
        mod_map = {
            "postgres": "modules/cloud-sql",
            "firestore": "modules/firestore",
            "bigquery": "bigquery rule (external dataset)",
            "bucket": "modules/bucket",
            "queue": "modules/queue",
        }
        resources_table.append(
            {
                "resource": st,
                "kind": f"Data / Cloud Capability ({st})",
                "source": "dependencies / SQL schema",
                "module": mod_map.get(st, st),
                "action": "Import or bind IAM",
                "means": f"Wires {st} IAM and local .env.example configuration.",
            }
        )

    default_region = regions_found[0] if regions_found else "asia-south1"
    has_existing_manifest = (repo_dir / "service.yaml").is_file()

    return {
        "app_name": app_name,
        "prod_project": prod_project,
        "default_region": default_region,
        "has_service_yaml": has_existing_manifest,
        "has_ui": has_ui,
        "dockerfiles": [str(d.relative_to(repo_dir)) for d in dockerfiles],
        "shell_scripts": [str(s.relative_to(repo_dir)) for s in shell_files],
        "legacy_hosts": legacy_hosts,
        "services": services,
        "jobs": jobs,
        "secrets": secrets_found,
        "stores": stores,
        "resources_table": resources_table,
    }


def _extract_secrets(body: str) -> list[str]:
    found: list[str] = []
    for m in _FLAG_SECRETS_RE.finditer(body):
        raw = m.group(1)
        for pair in raw.split(","):
            sm = _SECRET_NAME_RE.search(pair)
            if sm:
                sec = sm.group(1).strip()
                if sec and not sec.startswith("$") and sec not in found:
                    found.append(sec)
    return found


def render_discovery_markdown(report: dict) -> str:
    lines = [
        f"### Terraform Adoption Scorecard (`{report['app_name']}`)",
        "",
        "| Resource Found | Type & Settings | Where It Lives Today | Target Terraform Module | Action (`Create` vs `Import`) | What this means for you |",
        "|---|---|---|---|---|---|",
    ]
    if not report["resources_table"]:
        lines.append(
            "| *(none detected in scripts)* | Configure in `service.yaml` | Repo root | `modules/cloud-run-*` | **Create** | `sdlc.py sync-infra` will create fresh Terraform in `infra/`. |"
        )
    else:
        for row in report["resources_table"]:
            lines.append(
                f"| `{row['resource']}` | {row['kind']} | `{row['source']}` | `{row['module']}` | **{row['action']}** | {row['means']} |"
            )
    return "\n".join(lines) + "\n"


def write_imports_for_manifest(manifest_path: Path, dest: Path, project_id: str | None = None) -> list[Path]:
    raw = parse(manifest_path.read_text())
    app = normalize(raw)
    prod = project_id or str(app["prod_project"])
    app_name = str(app["name"])
    prefix = str(app.get("prefix") or app_name)
    written: list[Path] = []

    by_infra_dir: dict[Path, list[str]] = {}
    for comp in app["components"]:
        if comp.get("archetype") == "config-only":
            continue
        custom = comp.get("path")
        comp_dir = (dest if custom == "." else dest / str(custom)) if custom else (dest / "components" / comp["name"])
        infra_dir = comp_dir / "infra"
        infra_dir.mkdir(parents=True, exist_ok=True)
        region = str(comp.get("region", app["region"]))
        cname = str(comp["name"])
        res_name = prefixed_name(prefix, app_name, cname)[:48].rstrip("-")
        sa_id = f"{res_name}-rt"[:28]

        blocks = by_infra_dir.setdefault(
            infra_dir,
            [
                "# Declarative Terraform 1.9+ import blocks for existing GCP resources.",
                "# Remove any block below for a resource that does not exist in GCP yet.",
            ],
        )
        blocks += [
            "",
            f"# Component: {cname}",
            "import {",
            "  to = module.service.google_service_account.runtime",
            f'  id = "projects/{prod}/serviceAccounts/{sa_id}@{prod}.iam.gserviceaccount.com"',
            "}",
        ]
        if comp["archetype"] == "cloud-run-service":
            blocks += [
                "",
                "import {",
                "  to = module.service.google_cloud_run_v2_service.app",
                f'  id = "projects/{prod}/locations/{region}/services/{res_name}"',
                "}",
            ]
        elif comp["archetype"] in {"cloud-run-job", "scheduled-jobs"}:
            jobs = comp.get("jobs") or [{"name": cname}]
            for j in jobs:
                jname = prefixed_name(prefix, app_name, str(j["name"]))
                slug = jname.replace("_", "-")
                blocks += [
                    "",
                    "import {",
                    f'  to = module.service.google_cloud_run_v2_job.app["{jname}"]',
                    f'  id = "projects/{prod}/locations/{region}/jobs/{slug}"',
                    "}",
                ]
        for sec in comp.get("secrets", []):
            psec = prefixed_name(prefix, app_name, str(sec))
            blocks += [
                "",
                "import {",
                f'  to = module.secrets.google_secret_manager_secret.secret["{psec}"]',
                f'  id = "projects/{prod}/secrets/{psec}"',
                "}",
            ]
    for infra_dir, blocks in by_infra_dir.items():
        imports_file = infra_dir / "imports.tf.example"
        imports_file.write_text("\n".join(blocks) + "\n")
        written.append(imports_file)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo", nargs="?", type=Path, default=Path("."))
    parser.add_argument("--json", action="store_true", help="Print JSON discovery report")
    parser.add_argument("--table", action="store_true", help="Print Markdown adoption table")
    parser.add_argument(
        "--write-imports",
        type=Path,
        help="Path to service.yaml to generate infra/imports.tf.example files",
    )
    args = parser.parse_args(argv)

    repo_dir = args.repo.resolve()
    if args.write_imports:
        files = write_imports_for_manifest(args.write_imports.resolve(), repo_dir)
        for f in files:
            print(f)
        return 0

    report = discover_repo(repo_dir)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render_discovery_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
