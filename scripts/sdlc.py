#!/usr/bin/env python3
"""Opptra SDLC phase CLI for new and existing repositories.

Subcommands:
  check <service.yaml>                        Validate service.yaml against schema and rules
  status [repo_dir] [--json|--table|--check]  Inspect repo & render 14-point scorecard
  doctor [repo_dir]                           Alias for `status --table`
  init-runtime <service.yaml> [dest]          Phase 2: Scaffold runtime, openspec/, and entrypoints
  add-data <service.yaml> [dest]              Phase 3: Install data/storage/queue/secret packages & helpers
  add-tests <service.yaml> [dest]             Phase 4: Configure test runners and capability test fixtures
  sync-infra <service.yaml> [dest] [--ci-only] Phase 5: Generate Terraform, workflows, rules, and README
  all <service.yaml> [dest]                   Run all phases in order and record state
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_manifest
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
    script = dest / "scripts" / "bind-repo.sh"
    if script.is_file():
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
    state["updated_at"] = int(time.time())
    state_file.write_text(dump(state))


def main(argv: list[str] | None = None) -> int:
    args_list = argv if argv is not None else sys.argv[1:]
    if not args_list:
        print(__doc__, file=sys.stderr)
        return 2

    cmd = args_list[0]
    rest = args_list[1:]

    if cmd == "check":
        return check_manifest.main(["check_manifest.py", *rest])
    if cmd == "status":
        return status_mod.main(rest)
    if cmd == "doctor":
        return status_mod.main([*rest, "--table"])
    if cmd == "set-github-repo":
        if len(rest) < 1:
            print("usage: sdlc.py set-github-repo <github-url> [dest]", file=sys.stderr)
            return 2
        dest = Path(rest[1]).resolve() if len(rest) > 1 else Path(".").resolve()
        set_github_repo(dest, rest[0])
        return 0

    parser = argparse.ArgumentParser(prog=f"sdlc.py {cmd}")
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

    print(f"sdlc {cmd}: {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
