#!/usr/bin/env python3
"""Create the project's one Firestore database when an app needs it and it is missing.

The Firestore module only grants the runtime account access. Terraform
succeeds when ``(default)`` was never created, and every app in the project
shares that one database. This step creates it in the app region when it is
absent. It does not create a second named database, and it does not record
the database in an app's Terraform state. A database in the wrong mode or
region stops the deploy, because those cannot be changed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

Describer = Callable[[str], dict | None]
Creator = Callable[[str, str], str | None]


def uses_firestore(main_tf: str) -> bool:
    """Return whether this apply includes the Firestore access module."""
    return 'module "firestore"' in main_tf


def gcloud_describe(project: str) -> dict | None:
    """Return the ``(default)`` database, or None when the project has none."""
    result = subprocess.run(
        [
            "gcloud",
            "firestore",
            "databases",
            "describe",
            "--database=(default)",
            f"--project={project}",
            "--format=json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        if "NOT_FOUND" in detail or "does not exist" in detail.lower():
            return None
        print(detail, file=sys.stderr)
        return None
    payload = json.loads(result.stdout or "{}")
    return payload if isinstance(payload, dict) else None


def gcloud_create(project: str, region: str) -> str | None:
    """Create the Native ``(default)`` database. Return an error, or None on success.

    Point-in-time recovery and backups are left off. Those are billed from the
    first byte and are outside the free quota.
    """
    result = subprocess.run(
        [
            "gcloud",
            "firestore",
            "databases",
            "create",
            "--database=(default)",
            f"--location={region}",
            "--type=firestore-native",
            f"--project={project}",
            "--quiet",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return None
    detail = (result.stderr or result.stdout).strip()
    return (
        "Could not create the (default) Firestore database.\n"
        f"{detail}\n"
        "The deployer needs roles/datastore.owner. Run scripts/bind-staging.sh, then re-run this workflow."
    )


def firestore_problem(region: str, database: dict) -> str | None:
    """Return the message that stops the deploy, or None when the database is usable."""
    location = str(database.get("locationId") or "")
    database_type = str(database.get("type") or "")
    if database_type and database_type != "FIRESTORE_NATIVE":
        return (
            f"The (default) database is {database_type}. This app needs Native mode.\n"
            "Then re-run this workflow."
        )
    if location and region and location != region:
        return (
            f"The (default) database is in {location}, and this app deploys to {region}.\n"
            "A Firestore database location cannot be changed after it is created.\n"
            "Then re-run this workflow only if the app region is changed to match."
        )
    return None


def main(
    argv: list[str] | None = None,
    describer: Describer | None = None,
    creator: Creator | None = None,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--main-tf", type=Path, required=True)
    args = parser.parse_args(argv)
    if not uses_firestore(args.main_tf.read_text()):
        print("This apply does not use Firestore.")
        return 0
    lookup = describer or gcloud_describe
    database = lookup(args.project)
    if database is None:
        create = creator or gcloud_create
        error = create(args.project, args.region)
        if error:
            print(error, file=sys.stderr)
            return 1
        print(f"Created Firestore (default) in {args.region}.")
        return 0
    problem = firestore_problem(args.region, database)
    if problem is None:
        print(f"Firestore (default) is ready in {args.region}.")
        return 0
    print(problem, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
