#!/usr/bin/env python3
"""Write the Terraform variables for one plan or apply.

The workflow passes the commit SHA. This script turns service.yaml plus that
SHA into infra/ci.auto.tfvars.json. The file is generated on the runner and
is not committed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_manifest(path: Path) -> dict[str, str]:
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--environment", required=True, choices=("staging", "prod"))
    parser.add_argument("--staging-project", default="opptra-staging")
    parser.add_argument("--sha", required=True)
    parser.add_argument("--artifact-repo", default="apps")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()

    manifest = parse_manifest(args.manifest)
    required = ["name", "archetype", "prod_project", "region", "auth"]
    missing = [key for key in required if not manifest.get(key)]
    if missing:
        raise SystemExit(f"{args.manifest} missing: {', '.join(missing)}")
    if manifest["archetype"] != "cloud-run-service":
        raise SystemExit(
            "this workflow applies archetype cloud-run-service, "
            f"got {manifest['archetype']}"
        )
    if manifest["auth"] not in {"app-login", "iap", "public"}:
        raise SystemExit(f"unsupported auth {manifest['auth']}")
    if not args.sha or args.sha.startswith("latest"):
        raise SystemExit("sha must be the git commit, not a floating tag")

    project = args.staging_project if args.environment == "staging" else manifest["prod_project"]
    image = (
        f"{manifest['region']}-docker.pkg.dev/{project}/{args.artifact_repo}/"
        f"{manifest['name']}:{args.sha}"
    )
    payload = {
        "project_id": project,
        "region": manifest["region"],
        "name": manifest["name"],
        "environment": args.environment,
        "auth": manifest["auth"],
        "image": image,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n")

    if args.github_output:
        with args.github_output.open("a") as handle:
            for key, value in payload.items():
                print(f"{key}={value}", file=handle)
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
