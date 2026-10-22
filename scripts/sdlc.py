#!/usr/bin/env python3
"""Opptra SDLC phase CLI for new and existing repositories.

Subcommands:
  check <service.yaml>                 Validate service.yaml against schema and rules
  status [repo_dir] [--json] [--check] Inspect an existing repo or verify alignment
  init-runtime <service.yaml> <dest>   Phase 2: Scaffold runtime and workload entrypoints
  add-data <service.yaml> <dest>       Phase 3: Install data/storage/queue/secret packages & helpers
  add-tests <service.yaml> <dest>      Phase 4: Configure test runners and capability test fixtures
  sync-infra <service.yaml> <dest>     Phase 5: Generate Terraform, GitHub workflows, rules, and README
  all <service.yaml> <dest>            Run all phases in order
"""

from __future__ import annotations

import argparse
import sys
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

    parser = argparse.ArgumentParser(prog=f"sdlc.py {cmd}")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("dest", nargs="?", type=Path, default=Path("."))
    parser.add_argument("--overwrite", action="store_true")
    parsed = parser.parse_args(rest)

    manifest = parsed.manifest.resolve()
    dest = parsed.dest.resolve()

    if cmd == "init-runtime":
        phase_init_runtime(manifest, dest, overwrite=parsed.overwrite)
    elif cmd == "add-data":
        phase_add_data(manifest, dest)
    elif cmd == "add-tests":
        phase_add_tests(manifest, dest)
    elif cmd == "sync-infra":
        phase_sync_infra(manifest, dest)
    elif cmd == "all":
        phase_init_runtime(manifest, dest, overwrite=parsed.overwrite)
        phase_add_data(manifest, dest)
        phase_add_tests(manifest, dest)
        phase_sync_infra(manifest, dest)
    else:
        print(f"unknown command: {cmd}\n{__doc__}", file=sys.stderr)
        return 2

    print(f"sdlc {cmd}: {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
