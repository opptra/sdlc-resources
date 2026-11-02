#!/usr/bin/env python3
"""odlc, the Opptra SDLC phase CLI for new and existing repositories.

Subcommands:
  check <service.yaml>                        Validate service.yaml against schema and rules
  status [repo_dir] [--json|--table|--check]  Inspect repo & render 17-point scorecard
  next [repo_dir] [--json]                    Show current SDLC state, pending items, and next command
  secrets [repo_dir] [--env staging|prod]     List resolved Secret Manager IDs for service.yaml
  doctor [repo_dir]                           Alias for `status --table`
  discover [repo_dir]                         Alias for `discover-infra`
  discover-infra [repo_dir]                   Scan a repo and propose service.yaml or Terraform imports
  init-runtime <service.yaml> [dest]          Phase 2: Scaffold runtime, openspec/, and entrypoints
  add-data <service.yaml> [dest]              Phase 3: Install data/storage/queue/secret packages & helpers
  add-tests <service.yaml> [dest]             Phase 4: Configure test runners and capability test fixtures
  sync [service.yaml] [dest]                  Alias for `sync-infra`
  sync-infra <service.yaml> [dest] [--ci-only] Phase 5: Generate Terraform, workflows, rules, and README
  all <service.yaml> [dest]                   Run all phases in order and record state
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_manifest
import discover_infra
import status as status_mod
from generate import (
    phase_add_data,
    phase_add_tests,
    phase_init_runtime,
    phase_sync_infra,
)
from yaml_subset import dump, parse


def github_slug(url: str) -> str:
    text = url.strip()
    if text.endswith(".git"):
        text = text[: -len(".git")]
    if text.startswith("git@github.com:"):
        text = text.split(":", 1)[1]
    elif "github.com/" in text:
        text = text.split("github.com/", 1)[1]
    text = text.strip("/")
    if text.count("/") != 1 or " " in text:
        raise SystemExit("give a GitHub repository URL or org/repo")
    return text


def set_github_repo(dest: Path, url: str) -> str:
    slug = github_slug(url)
    state_dir = dest / ".sdlc"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / "state.yaml"
    state: dict = {}
    if state_file.is_file():
        try:
            state = parse(state_file.read_text())
        except SystemExit:
            state = {}
    state["github_repo"] = slug
    state["updated_at"] = int(time.time())
    state_file.write_text(dump(state))
    for name in ("bind-staging.sh", "bind-production.sh", "bind-repo.sh"):
        script = dest / "scripts" / name
        if not script.is_file():
            continue
        text = script.read_text()
        updated = []
        replaced = False
        for line in text.splitlines():
            if line.startswith('REPO="${1:-') and not replaced:
                updated.append(f'REPO="${{1:-{slug}}}"')
                replaced = True
            else:
                updated.append(line)
        script.write_text("\n".join(updated) + "\n")
    print(slug)
    return slug


def generator_sha() -> str:
    root = Path(__file__).resolve().parents[1]
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def record_phase_state(dest: Path, phase: str, manifest_path: Path) -> None:
    state_dir = dest / ".sdlc"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / "state.yaml"
    state: dict = {}
    if state_file.is_file():
        try:
            state = parse(state_file.read_text())
        except SystemExit:
            state = {}
    completed = list(state.get("completed_phases", []))
    if phase not in completed:
        completed.append(phase)
    state["manifest"] = str(manifest_path.name)
    state["last_phase"] = phase
    state["completed_phases"] = completed
    sha = generator_sha()
    if sha:
        state["generator_sha"] = sha
    state["updated_at"] = int(time.time())
    state_file.write_text(dump(state))


def run_next(rest: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="odlc next")
    parser.add_argument("repo", nargs="?", type=Path, default=Path("."))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(rest)
    repo_dir = args.repo.resolve()

    report = status_mod.inspect_repo(repo_dir)
    branch = "uninitialized"
    if (repo_dir / ".git").exists():
        res = subprocess.run(
            ["git", "-C", str(repo_dir), "rev-parse", "--abbrev-ref", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
        if res.returncode == 0 and res.stdout.strip():
            branch = res.stdout.strip()

    intent_file = repo_dir / ".sdlc" / "intent.yaml"
    intent = parse(intent_file.read_text()) if intent_file.is_file() else {}
    state_file = repo_dir / ".sdlc" / "state.yaml"
    state = parse(state_file.read_text()) if state_file.is_file() else {}

    passing_sections = sum(1 for s in report["sections_14"] if s["status"] == "Up to the mark")
    total_sections = len(report["sections_14"])
    pending: list[str] = []
    if not report["has_service_yaml"]:
        pending.append("missing service.yaml")
    elif report["manifest_errors"]:
        pending.append(f"manifest errors ({len(report['manifest_errors'])})")
    if report["rule_errors"]:
        pending.append(f"rule sync needed ({len(report['rule_errors'])})")
    if report["detected"]["legacy_deploy"]:
        pending.append(f"legacy deploy scripts ({', '.join(report['detected']['legacy_deploy'])})")
    if report["unmet"]:
        pending.append(f"{len(report['unmet'])} unmet extension item(s)")
    if intent.get("next_step"):
        pending.append(f"active {intent.get('route', 'task')} at step '{intent['next_step']}'")

    if not report["has_service_yaml"]:
        next_cmd = "odlc discover --propose-manifest > service.yaml && odlc sync"
    elif report["manifest_errors"]:
        next_cmd = "odlc check service.yaml"
    elif not report["aligned"]:
        next_cmd = "odlc sync"
    elif intent.get("next_step") in {"test", "code", "code-stacked-on-infra", "ci"}:
        next_cmd = f"Continue {intent.get('route', 'feature')} on {intent.get('branch', branch)} and run `make ci`"
    elif branch not in {"main", "staging", "production", "uninitialized"}:
        next_cmd = f"make ci && git push --force-with-lease origin {branch}:staging"
    else:
        next_cmd = "Start a feature (`feat/<ticket>-<slug>`) or bug fix (`fix/<ticket>-<slug>`)"

    payload = {
        "aligned": report["aligned"],
        "score": f"{passing_sections}/{total_sections}",
        "branch": branch,
        "openspec": report["openspec"],
        "intent": intent,
        "state": state,
        "pending": pending,
        "recommended_next_step": next_cmd,
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        status_label = f"Aligned ({passing_sections}/{total_sections})" if report["aligned"] else f"Needs Alignment ({passing_sections}/{total_sections})"
        os_label = "ready" if report["openspec"]["dir_present"] else "missing"
        print(f"Current State: {status_label} | Branch: {branch} | OpenSpec: {os_label}")
        print(f"Pending Items: {', '.join(pending) if pending else 'None'}")
        print(f"Recommended Next Step: {next_cmd}")
    return 0


def run_secrets(rest: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="odlc secrets")
    parser.add_argument("repo", nargs="?", type=Path, default=Path("."))
    parser.add_argument("--env", choices=("staging", "prod"), default="staging")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(rest)
    repo_dir = args.repo.resolve()
    manifest_path = repo_dir / "service.yaml"
    if not manifest_path.is_file():
        print("missing service.yaml", file=sys.stderr)
        return 1
    app = check_manifest.normalize(parse(manifest_path.read_text()))
    project = "opptra-staging" if args.env == "staging" else str(app["prod_project"])
    prefix = str(app.get("prefix") or app["name"])
    resolved_secrets: list[dict] = []
    seen: set[str] = set()
    for comp in app.get("components", []):
        smap = comp.get("secret_map") if isinstance(comp.get("secret_map"), dict) else None
        for sec in comp.get("secrets", []):
            gcp_id = check_manifest.secret_resource_id(prefix, str(sec), smap)
            if gcp_id not in seen:
                seen.add(gcp_id)
                resolved_secrets.append(
                    {
                        "env_var": str(sec),
                        "secret_id": gcp_id,
                        "project": project,
                    }
                )
    if args.json:
        print(json.dumps({"project": project, "secrets": resolved_secrets}, indent=2))
    else:
        if not resolved_secrets:
            print(f"No secrets declared in {manifest_path.name}.")
        else:
            print(f"Target GCP project ({args.env}): {project}")
            for item in resolved_secrets:
                print(f"  {item['env_var']} -> {item['secret_id']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args_list = argv if argv is not None else sys.argv[1:]
    if not args_list:
        print(__doc__, file=sys.stderr)
        return 2

    entered = args_list[0]
    rest = args_list[1:]
    cmd = {"discover": "discover-infra", "sync": "sync-infra"}.get(entered, entered)

    if cmd == "check":
        return check_manifest.main(["check_manifest.py", *rest])
    if cmd == "status":
        return status_mod.main(rest)
    if cmd == "next":
        return run_next(rest)
    if cmd == "secrets":
        return run_secrets(rest)
    if cmd == "doctor":
        return status_mod.main([*rest, "--table"])
    if cmd == "discover-infra":
        return discover_infra.main(rest)
    if cmd == "set-github-repo":
        if len(rest) < 1:
            print("usage: odlc set-github-repo <github-url> [dest]", file=sys.stderr)
            return 2
        dest = Path(rest[1]).resolve() if len(rest) > 1 else Path(".").resolve()
        set_github_repo(dest, rest[0])
        return 0

    parser = argparse.ArgumentParser(prog=f"odlc {entered}")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("dest", nargs="?", type=Path, default=Path("."))
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--ci-only", action="store_true", help="Write CI and rules without Terraform infra/")
    parsed = parser.parse_args(rest)

    manifest = parsed.manifest.resolve()
    dest = parsed.dest.resolve()

    if cmd == "init-runtime":
        phase_init_runtime(manifest, dest, overwrite=parsed.overwrite)
        record_phase_state(dest, "init-runtime", manifest)
    elif cmd == "add-data":
        phase_add_data(manifest, dest)
        record_phase_state(dest, "add-data", manifest)
    elif cmd == "add-tests":
        phase_add_tests(manifest, dest)
        record_phase_state(dest, "add-tests", manifest)
    elif cmd == "sync-infra":
        phase_sync_infra(manifest, dest, ci_only=parsed.ci_only)
        record_phase_state(dest, "sync-infra", manifest)
    elif cmd == "all":
        phase_init_runtime(manifest, dest, overwrite=parsed.overwrite)
        record_phase_state(dest, "init-runtime", manifest)
        phase_add_data(manifest, dest)
        record_phase_state(dest, "add-data", manifest)
        phase_add_tests(manifest, dest)
        record_phase_state(dest, "add-tests", manifest)
        phase_sync_infra(manifest, dest, ci_only=parsed.ci_only)
        record_phase_state(dest, "sync-infra", manifest)
    else:
        print(f"unknown command: {cmd}\n{__doc__}", file=sys.stderr)
        return 2

    print(f"odlc {entered}: {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
