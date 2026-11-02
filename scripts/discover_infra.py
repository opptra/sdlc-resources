#!/usr/bin/env python3
"""Scan an existing repository to discover GCP resources, deploy scripts, and Terraform imports."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_manifest import normalize, prefixed_name, secret_resource_id
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
_SECRET_NAME_RE = re.compile(r"([A-Za-z0-9_]+)=([a-zA-Z0-9_-]+):")
_VAR_ASSIGN_RE = re.compile(r"^([A-Z_][A-Z0-9_]*)=[\"']?([^\"'\n#]+)[\"']?", re.M)
_DOCKER_CMD_RE = re.compile(r"^\s*(?:CMD|ENTRYPOINT)\s+(.*)$", re.M)
_SENSITIVE_ENV_RE = re.compile(r"(?:SECRET|TOKEN|PASSWORD|PASSWD|API_KEY|PRIVATE_KEY|CREDENTIAL|AUTH_KEY|DSN)$", re.I)
_IAM_ROLE_RE = re.compile(r"--role[=\s]+[\"']?(roles/[A-Za-z0-9._-]+)[\"']?")
_CLOUDSQL_FLAG_RE = re.compile(r"--(?:add|set)-cloudsql-instances[=\s]+[\"']?([a-zA-Z0-9_:.-]+)[\"']?")
_GCLOUD_COMMAND_RE = re.compile(r"--command(?:=|\s+)(\"[^\"]*\"|'[^']*'|\S+)")
_GCLOUD_ARGS_RE = re.compile(r"--args(?:=|\s+)(\"[^\"]*\"|'[^']*'|\S+)")
_BUILD_VALUE_FLAGS = {
    "-f",
    "--file",
    "-t",
    "--tag",
    "--build-arg",
    "--target",
    "--platform",
    "-o",
    "--output",
    "--iidfile",
    "--label",
    "--network",
    "--secret",
    "--ssh",
}
_PUBSUB_TOPIC_RE = re.compile(r"gcloud\s+pubsub\s+topics\s+create\s+[\"']?([a-zA-Z0-9_-]+)[\"']?")
_REDIS_INSTANCE_RE = re.compile(r"gcloud\s+redis\s+instances\s+create\s+[\"']?([a-zA-Z0-9_-]+)[\"']?")


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


def _norm_repo_path(value: str) -> str | None:
    path = value.strip().strip("'\"")
    if path.startswith("./"):
        path = path[2:]
    if not path or path.startswith(("/", "\\")) or ".." in Path(path).parts:
        return None
    return path or "."


def _parse_build_args(tokens: list[str]) -> tuple[str, str] | None:
    dockerfile = None
    positional: list[str] = []
    index = 0
    while index < len(tokens):
        tok = tokens[index].strip("'\"")
        if tok in _BUILD_VALUE_FLAGS and index + 1 < len(tokens):
            val = tokens[index + 1].strip("'\"")
            if tok in {"-f", "--file"}:
                dockerfile = val
            index += 2
            continue
        if tok.startswith("--file="):
            dockerfile = tok.split("=", 1)[1].strip("'\"")
            index += 1
            continue
        if tok.startswith("-"):
            index += 1
            continue
        positional.append(tok)
        index += 1
    if dockerfile is None and not positional:
        return None
    context = _norm_repo_path(positional[-1] if positional else ".")
    if context is None:
        return None
    if dockerfile is None:
        dockerfile = str(Path(context) / "Dockerfile")
    dockerfile = _norm_repo_path(dockerfile)
    if dockerfile is None:
        return None
    return context, dockerfile


def _build_arg_lists(text: str) -> list[list[str]]:
    flat = text.replace("\\\n", " ")
    lists: list[list[str]] = []
    for match in re.finditer(r"docker\s+build\b([^\n]*)", flat):
        lists.append(match.group(1).split())
    for match in re.finditer(r"cloud-builders/docker(.*?)(?:\n\s*- name:|\Z)", text, re.S):
        args = re.findall(r"^\s*-\s+[\"']?([^\"'\n#]+)[\"']?\s*$", match.group(1), re.M)
        if args and args[0] == "build":
            lists.append(args[1:])
    return lists


def _copy_sources(dockerfile_text: str) -> list[str]:
    sources: list[str] = []
    for raw in dockerfile_text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line.upper().startswith(("COPY ", "ADD ")) or "--from=" in line.lower():
            continue
        body = line.split(None, 1)[1].strip()
        if body.startswith("["):
            try:
                parts = json.loads(body)
            except json.JSONDecodeError:
                continue
            tokens = [str(part) for part in parts[:-1]]
        else:
            tokens = [tok for tok in body.split() if not tok.startswith("--")][:-1]
        sources.extend(
            src for src in tokens if not src.startswith(("http://", "https://", "$"))
        )
    return sources


def _source_exists(base: Path, src: str) -> bool:
    candidate = base / (Path(src).parent if "*" in src or "?" in src else src)
    try:
        candidate.resolve().relative_to(base.resolve())
    except ValueError:
        return False
    if "*" in src or "?" in src:
        return candidate.is_dir()
    return candidate.exists()


def _context_for_dockerfile(repo_dir: Path, rel_df: str) -> str:
    parent = str(Path(rel_df).parent)
    if parent == ".":
        return "."
    sources = _copy_sources((repo_dir / rel_df).read_text(errors="ignore"))
    if not sources or all(_source_exists(repo_dir / parent, src) for src in sources):
        return parent
    if all(_source_exists(repo_dir, src) for src in sources):
        return "."
    return parent


def _ignored_dockerfile(rel: str) -> bool:
    return any(part in {".git", ".venv", "node_modules", "infra"} for part in Path(rel).parts)


def _choose_docker_build(repo_dir: Path, shell_files: list[Path], dockerfiles: list[Path]) -> dict | None:
    """The build the existing deploy runs, when it is not `<path>/Dockerfile` at the repo root."""
    existing = {
        str(path.relative_to(repo_dir))
        for path in dockerfiles
        if not _ignored_dockerfile(str(path.relative_to(repo_dir)))
    }
    parsed: list[tuple[str, str]] = []
    for shell in shell_files:
        for args in _build_arg_lists(shell.read_text(errors="ignore")):
            found = _parse_build_args(args)
            if found:
                parsed.append(found)
    for context, dockerfile in parsed:
        if dockerfile in existing or (repo_dir / dockerfile).is_file():
            if context == "." and dockerfile == "Dockerfile":
                return None
            return {"context": context, "dockerfile": dockerfile}
    rels = sorted(existing, key=len)
    if not rels:
        return None
    chosen = "Dockerfile" if "Dockerfile" in existing else rels[0]
    context = _context_for_dockerfile(repo_dir, chosen)
    if context == "." and chosen == "Dockerfile":
        return None
    return {"context": context, "dockerfile": chosen}


def _gcloud_run_command(body: str) -> str | None:
    command_m = _GCLOUD_COMMAND_RE.search(body)
    args_m = _GCLOUD_ARGS_RE.search(body)
    command = command_m.group(1).strip("'\"") if command_m else ""
    args = args_m.group(1).strip("'\"") if args_m else ""
    if command and args:
        return f"{command} {' '.join(part for part in args.split(',') if part)}".strip()
    return command or args or None


def discover_repo(repo_dir: Path) -> dict:
    repo_dir = repo_dir.resolve()
    app_name = re.sub(r"[^a-z0-9-]", "-", repo_dir.name.lower()).strip("-") or "app"

    shell_files = [
        p
        for p in list(repo_dir.glob("deploy/**/*.sh"))
        + list(repo_dir.glob("scripts/**/*.sh"))
        + list(repo_dir.glob("*.sh"))
        + list(repo_dir.glob("**/cloudbuild.y*ml"))
        if ".venv" not in p.parts and "node_modules" not in p.parts and p.name not in {"bind-repo.sh", "bind-staging.sh", "bind-production.sh"}
    ]
    dockerfiles = [
        p
        for p in repo_dir.glob("**/Dockerfile*")
        if ".venv" not in p.parts and "node_modules" not in p.parts
    ]

    services: list[dict] = []
    jobs: list[dict] = []
    secrets_found: list[str] = []
    secret_map_found: dict[str, str] = {}
    plain_env_found: dict[str, str] = {}
    extra_roles_found: list[str] = []
    custom_resources_found: list[dict] = []
    cloudsql_instances_found: list[str] = []
    has_database_url_ref = False
    dockerfile_commands: dict[str, str] = {}
    regions_found: list[str] = []
    prod_project = "opptra-applications"

    for df in dockerfiles:
        df_text = df.read_text(errors="ignore")
        rel_df = str(df.relative_to(repo_dir))
        cmds = _DOCKER_CMD_RE.findall(df_text)
        if cmds:
            raw_cmd = cmds[-1].strip()
            if raw_cmd.startswith("[") and raw_cmd.endswith("]"):
                try:
                    parsed_cmd = json.loads(raw_cmd)
                    if isinstance(parsed_cmd, list):
                        raw_cmd = " ".join(str(x) for x in parsed_cmd)
                except ValueError:
                    pass
            dockerfile_commands[rel_df] = raw_cmd

    env_example = repo_dir / ".env.example"
    if env_example.is_file():
        for line in env_example.read_text(errors="ignore").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            k, _, v = stripped.partition("=")
            k = k.strip()
            v = v.strip().strip("\"'")
            if k == "DATABASE_URL" and any(
                host in v for host in ("neon.tech", "supabase", "amazonaws.com", "sslmode=")
            ):
                has_database_url_ref = True
            if not k or k in {
                "APP_ENV",
                "SERVICE_NAME",
                "RESOURCE_PREFIX",
                "GOOGLE_CLOUD_PROJECT",
                "DATABASE_URL",
                "FIRESTORE_EMULATOR_HOST",
                "BIGQUERY_PROJECT",
                "BIGQUERY_DATASET",
                "GCS_BUCKET_NAME",
                "CLOUD_TASKS_QUEUE",
            }:
                continue
            if _SENSITIVE_ENV_RE.search(k) or v == "replace-me":
                if k not in secrets_found:
                    secrets_found.append(k)
            else:
                plain_env_found[k] = v

    for sh in shell_files:
        raw = sh.read_text(errors="ignore")
        joined = raw.replace("\\\n", " ")
        sh_vars = {
            m.group(1): _clean_var_val(m.group(2)) for m in _VAR_ASSIGN_RE.finditer(raw)
        }
        for sub_m in re.finditer(r"^\s*(_[A-Z0-9_]+):\s*[\"']?([^\"'\n#]+)[\"']?", raw, re.M):
            sh_vars[sub_m.group(1)] = _clean_var_val(sub_m.group(2))
        prod_m = re.search(r'prod\)\s+SERVICE=["\']?([a-zA-Z0-9_-]+)["\']?', raw)
        if prod_m:
            sh_vars["SERVICE"] = prod_m.group(1)
        for proj_key in ("PROJECT_ID", "PROJECT", "_PROJECT_ID"):
            if proj_key in sh_vars and not sh_vars[proj_key].startswith("$"):
                prod_project = sh_vars[proj_key]
        if sh.name.startswith("cloudbuild."):
            joined = re.sub(r"\n\s*-\s*[\"']?([^\"'\n]+)[\"']?", r" \1", joined)
        resolved = _resolve_shell_vars(joined, sh_vars)
        rel = str(sh.relative_to(repo_dir))

        for env_var, sec_id in _extract_secret_pairs(raw):
            if sec_id not in secrets_found:
                secrets_found.append(sec_id)
            if env_var and sec_id:
                secret_map_found[env_var] = sec_id
            if env_var == "DATABASE_URL":
                has_database_url_ref = True

        for csql_m in _CLOUDSQL_FLAG_RE.finditer(resolved):
            inst = csql_m.group(1).strip()
            if inst and not inst.startswith("$") and inst not in cloudsql_instances_found:
                cloudsql_instances_found.append(inst)

        for role_m in _IAM_ROLE_RE.finditer(resolved):
            role = role_m.group(1).strip()
            if role not in {
                "roles/run.invoker",
                "roles/secretmanager.secretAccessor",
                "roles/cloudsql.client",
                "roles/datastore.user",
                "roles/bigquery.jobUser",
            } and role not in extra_roles_found:
                extra_roles_found.append(role)

        for ps_m in _PUBSUB_TOPIC_RE.finditer(resolved):
            tname = ps_m.group(1).strip()
            if not tname.startswith("$") and not any(
                c["type"] == "pubsub_topic" and c["name"] == tname for c in custom_resources_found
            ):
                custom_resources_found.append({"type": "pubsub_topic", "name": tname, "source": rel})

        for rd_m in _REDIS_INSTANCE_RE.finditer(resolved):
            rname = rd_m.group(1).strip()
            if not rname.startswith("$") and not any(
                c["type"] == "redis_instance" and c["name"] == rname for c in custom_resources_found
            ):
                custom_resources_found.append({"type": "redis_instance", "name": rname, "source": rel})

        for loop_m in re.finditer(r"for\s+job\s+in\s+([^;\n]+);", raw):
            for tok in loop_m.group(1).split():
                tok_clean = tok.strip("\"'")
                if tok_clean and not tok_clean.startswith("$"):
                    job = {
                        "name": tok_clean,
                        "source": rel,
                        "region": sh_vars.get("REGION", "asia-south1"),
                        "memory": "2Gi",
                        "timeout_seconds": 3000,
                        "secrets": [],
                    }
                    command = _gcloud_run_command(raw)
                    if command:
                        job["command"] = command
                    jobs.append(job)

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
            job = {
                "name": name,
                "source": rel,
                "region": region,
                "memory": mem_m.group(1) if mem_m else "1Gi",
                "timeout_seconds": int(timeout_m.group(1)) if timeout_m else 1800,
                "secrets": sec_ids,
            }
            command = _gcloud_run_command(body)
            if command:
                job["command"] = command
            jobs.append(job)

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
            "bigquery": "modules/bigquery",
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
    for cr in custom_resources_found:
        resources_table.append(
            {
                "resource": cr["name"],
                "kind": f"Custom Resource ({cr['type']})",
                "source": cr["source"],
                "module": "infra/custom.keep.tf",
                "action": "Generate in infra/custom.keep.tf + Import",
                "means": "Managed in preserved infra/custom.keep.tf alongside main.tf.",
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
        "dockerfile_commands": dockerfile_commands,
        "docker_build": _choose_docker_build(repo_dir, shell_files, dockerfiles),
        "shell_scripts": [str(s.relative_to(repo_dir)) for s in shell_files],
        "legacy_hosts": legacy_hosts,
        "services": services,
        "jobs": jobs,
        "secrets": secrets_found,
        "secret_map": secret_map_found,
        "plain_env": plain_env_found,
        "extra_roles": extra_roles_found,
        "custom_resources": custom_resources_found,
        "cloudsql_instances": cloudsql_instances_found,
        "postgres_external": bool(
            "postgres" in stores
            and not cloudsql_instances_found
            and (has_database_url_ref or bool(services or jobs))
        ),
        "stores": stores,
        "resources_table": resources_table,
    }


def _extract_secret_pairs(body: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for m in _FLAG_SECRETS_RE.finditer(body):
        raw = m.group(1)
        for pair in raw.split(","):
            sm = _SECRET_NAME_RE.search(pair)
            if sm:
                env_var = sm.group(1).strip()
                sec = sm.group(2).strip()
                if sec and not sec.startswith("$") and (env_var, sec) not in found:
                    found.append((env_var, sec))
    return found


def _extract_secrets(body: str) -> list[str]:
    return [sec for _, sec in _extract_secret_pairs(body)]


def propose_manifest(report: dict) -> str:
    app_name = report["app_name"]
    prefix = app_name[:20].rstrip("-")
    default_region = report["default_region"]
    stores = report.get("stores", [])
    db = "none"
    for candidate in ("postgres", "firestore", "bigquery"):
        if candidate in stores:
            db = candidate
            break
    bucket = "private" if "bucket" in stores else "none"
    secret_map = report.get("secret_map", {})
    secrets = list(secret_map.keys()) if secret_map else list(report.get("secrets", []))
    plain_env = report.get("plain_env", {})
    extra_roles = report.get("extra_roles", [])
    has_custom_tf = bool(report.get("custom_resources"))
    cloudsql_instances = report.get("cloudsql_instances", [])
    postgres_external = bool(report.get("postgres_external", False))

    components: list[dict] = []

    def apply_build(comp: dict) -> None:
        build = report.get("docker_build") or {}
        parts = set(comp.get("parts") or [])
        if not build or not parts & {"api", "job", "worker"}:
            return
        comp["docker_context"] = build["context"]
        comp["dockerfile"] = build["dockerfile"]

    def job_command(job: dict, module_name: str) -> str:
        if job.get("command"):
            return str(job["command"])
        jobs = report.get("jobs") or []
        commands = report.get("dockerfile_commands") or {}
        build = report.get("docker_build") or {}
        if len(jobs) == 1 and not report.get("services"):
            dockerfile = str(build.get("dockerfile") or "")
            if dockerfile and dockerfile in commands:
                return str(commands[dockerfile])
            if len(commands) == 1:
                return str(next(iter(commands.values())))
        return f"python -m app.jobs.{module_name}"

    for svc in report.get("services", []):
        raw_svc_name = str(svc["name"])
        parts = ["ui", "api"] if report.get("has_ui") else ["api"]
        comp: dict = {
            "name": raw_svc_name[:40].rstrip("-"),
            "archetype": "cloud-run-service",
            "region": str(svc.get("region", default_region)),
            "path": ".",
            "auth": str(svc.get("auth", "iap")),
            "database": db,
            "bucket": bucket,
            "parts": parts,
        }
        if not raw_svc_name.startswith(f"{prefix}-") and raw_svc_name != prefix:
            comp["legacy_service_name"] = raw_svc_name
        if secrets:
            comp["secrets"] = secrets
        if secret_map:
            comp["secret_map"] = secret_map
        if plain_env:
            comp["env"] = plain_env
        if extra_roles:
            comp["extra_roles"] = extra_roles
        if has_custom_tf:
            comp["custom_terraform"] = True
        if db == "postgres":
            if cloudsql_instances:
                comp["postgres_instance"] = cloudsql_instances[0]
            elif postgres_external:
                comp["postgres_external"] = True
        apply_build(comp)
        components.append(comp)

    if report.get("jobs"):
        job_entries = []
        for j in report["jobs"]:
            jname = str(j["name"])
            py_mod = jname.replace("-", "_")
            job_entries.append(
                {
                    "name": jname,
                    "command": job_command(j, py_mod),
                    "enabled": True,
                    "timezone": "Asia/Kolkata",
                    "schedules": [],
                    "timeout_seconds": int(j.get("timeout_seconds", 1800)),
                    "memory": str(j.get("memory", "1Gi")),
                    "secrets": secrets,
                }
            )
        comp = {
            "name": f"{prefix}-jobs"[:40].rstrip("-"),
            "archetype": "scheduled-jobs" if len(job_entries) > 1 else "cloud-run-job",
            "region": str(report["jobs"][0].get("region", default_region)),
            "path": ".",
            "auth": "none",
            "database": db,
            "bucket": bucket,
            "parts": ["job"],
            "jobs": job_entries,
        }
        if secrets:
            comp["secrets"] = secrets
        if secret_map:
            comp["secret_map"] = secret_map
        if plain_env:
            comp["env"] = plain_env
        if extra_roles:
            comp["extra_roles"] = extra_roles
        if has_custom_tf:
            comp["custom_terraform"] = True
        if db == "postgres":
            if cloudsql_instances:
                comp["postgres_instance"] = cloudsql_instances[0]
            elif postgres_external:
                comp["postgres_external"] = True
        apply_build(comp)
        components.append(comp)

    if not components:
        parts = ["ui", "api"] if report.get("has_ui") else ["api"]
        comp = {
            "name": app_name[:40].rstrip("-"),
            "archetype": "cloud-run-service",
            "region": default_region,
            "path": ".",
            "auth": "iap" if "ui" in parts else "app-login",
            "database": db,
            "bucket": bucket,
            "parts": parts,
        }
        if secrets:
            comp["secrets"] = secrets
        if secret_map:
            comp["secret_map"] = secret_map
        if plain_env:
            comp["env"] = plain_env
        if extra_roles:
            comp["extra_roles"] = extra_roles
        if has_custom_tf:
            comp["custom_terraform"] = True
        if db == "postgres":
            if cloudsql_instances:
                comp["postgres_instance"] = cloudsql_instances[0]
            elif postgres_external:
                comp["postgres_external"] = True
        apply_build(comp)
        components.append(comp)

    manifest = {
        "name": app_name,
        "prefix": prefix,
        "purpose": f"Service manifest for {app_name}.",
        "prod_project": report.get("prod_project", "opptra-applications"),
        "region": default_region,
        "components": components,
    }
    return dump(manifest)


def render_discovery_markdown(report: dict) -> str:
    lines = [
        f"### Terraform Adoption Scorecard (`{report['app_name']}`)",
        "",
        "| Resource Found | Type & Settings | Where It Lives Today | Target Terraform Module | Action (`Create` vs `Import`) | What this means for you |",
        "|---|---|---|---|---|---|",
    ]
    if not report["resources_table"]:
        lines.append(
            "| *(none detected in scripts)* | Configure in `service.yaml` | Repo root | `modules/cloud-run-*` | **Create** | `odlc sync-infra` will create fresh Terraform in `infra/`. |"
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
        legacy_svc = str(comp.get("legacy_service_name") or "").strip()
        res_name = (legacy_svc if legacy_svc else prefixed_name(prefix, app_name, cname))[:48].rstrip("-")
        sa_id = f"{res_name}-rt"[:28]
        secret_map = comp.get("secret_map") if isinstance(comp.get("secret_map"), dict) else None

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
        seen_secrets: set[str] = set()
        for sec in comp.get("secrets", []):
            psec = secret_resource_id(prefix, str(sec), secret_map)
            if psec in seen_secrets:
                continue
            seen_secrets.add(psec)
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

    disc = discover_repo(dest)
    if disc.get("custom_resources") and by_infra_dir:
        first_infra = next(iter(by_infra_dir.keys()))
        custom_tf = first_infra / "custom.keep.tf"
        custom_blocks = [
            "# Custom GCP resources discovered by `odlc discover-infra`.",
            "# Preserved across `odlc sync-infra` runs.",
        ]
        for cr in disc["custom_resources"]:
            slug = re.sub(r"[^a-zA-Z0-9_]", "_", cr["name"])
            if cr["type"] == "pubsub_topic":
                custom_blocks.append(
                    f'\nresource "google_pubsub_topic" "{slug}" {{\n'
                    f"  project = var.project_id\n"
                    f'  name    = "{cr["name"]}"\n'
                    f"}}"
                )
            elif cr["type"] == "redis_instance":
                custom_blocks.append(
                    f'\nresource "google_redis_instance" "{slug}" {{\n'
                    f"  project        = var.project_id\n"
                    f"  region         = var.region\n"
                    f'  name           = "{cr["name"]}"\n'
                    f"  memory_size_gb = 1\n"
                    f"}}"
                )
        custom_tf.write_text("\n".join(custom_blocks) + "\n")
        written.append(custom_tf)
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
    parser.add_argument(
        "--propose-manifest",
        action="store_true",
        help="Print a proposed service.yaml from discovered repo resources",
    )
    args = parser.parse_args(argv)

    repo_dir = args.repo.resolve()
    if args.write_imports:
        files = write_imports_for_manifest(args.write_imports.resolve(), repo_dir)
        for f in files:
            print(f)
        return 0

    report = discover_repo(repo_dir)
    if args.propose_manifest:
        print(propose_manifest(report), end="")
    elif args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render_discovery_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
