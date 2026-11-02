#!/usr/bin/env python3
"""Stop a deploy when a mounted secret has no version.

Cloud Run opens ``versions/latest`` while saving the revision. The workflow
creates the secret shells first. This check then lists every mounted id that
still has no version and exits non-zero. Add a version in Secret Manager and
re-run the same workflow. The value is not printed and is not committed.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

# module.secrets.by_id["id"] and one(module.secrets[*].by_id)["id"]
MOUNTED_SECRET = re.compile(r'(?:module\.secrets\.by_id|by_id\))\["([^"]+)"\]')
MOUNTED_BLOCK = re.compile(r"mounted_secret_ids\s*=\s*\[(.*?)\n\s*\]", re.DOTALL)
DIRECT_SECRET = re.compile(r'^\s*"([^"]+)"\s*,?\s*$', re.M)

VersionLister = Callable[[str, str], bool]


def mounted_secret_ids(main_tf: str) -> list[str]:
    """Return the secret ids a workload mounts, in first-seen order.

    Includes both ``module.secrets.by_id["..."]`` references (app-owned shells)
    and direct string IDs in ``mounted_secret_ids`` (pre-existing shared secrets).
    """
    seen: list[str] = []
    for block_m in MOUNTED_BLOCK.finditer(main_tf):
        block = block_m.group(1)
        for line in block.splitlines():
            m_mod = MOUNTED_SECRET.search(line)
            if m_mod:
                sid = m_mod.group(1)
                if sid not in seen:
                    seen.append(sid)
                continue
            m_dir = DIRECT_SECRET.match(line)
            if m_dir:
                sid = m_dir.group(1)
                if sid not in seen:
                    seen.append(sid)
    for match in MOUNTED_SECRET.finditer(main_tf):
        secret_id = match.group(1)
        if secret_id not in seen:
            seen.append(secret_id)
    return seen


def gcloud_has_version(project: str, secret_id: str) -> bool:
    """Return whether Secret Manager has at least one version of this secret."""
    result = subprocess.run(
        [
            "gcloud",
            "secrets",
            "versions",
            "list",
            secret_id,
            f"--project={project}",
            "--format=value(name)",
            "--limit=1",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        print(f"{secret_id}: {detail}", file=sys.stderr)
        return False
    return bool(result.stdout.strip())


def missing_versions(project: str, secret_ids: list[str], versions_lister: VersionLister) -> list[str]:
    """Return mounted secret ids that have no version."""
    return [secret_id for secret_id in secret_ids if not versions_lister(project, secret_id)]


def format_failure(missing: list[str]) -> str:
    """Tell the deployer which ids to fill, and to re-run this workflow."""
    lines = [
        "These secrets have no version. Cloud Run cannot mount latest until a version exists.",
        "Add a version in Secret Manager, then re-run this workflow. Do not change Terraform.",
        "",
    ]
    lines.extend(f"  {secret_id}" for secret_id in missing)
    return "\n".join(lines)


def main(argv: list[str] | None = None, versions_lister: VersionLister | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--main-tf", type=Path, required=True)
    args = parser.parse_args(argv)
    secret_ids = mounted_secret_ids(args.main_tf.read_text())
    if not secret_ids:
        print("No mounted secrets.")
        return 0
    lister = versions_lister or gcloud_has_version
    missing = missing_versions(args.project, secret_ids, lister)
    if not missing:
        print(f"{len(secret_ids)} mounted secret(s) have a version.")
        return 0
    print(format_failure(missing), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
