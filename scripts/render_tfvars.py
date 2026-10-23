#!/usr/bin/env python3
"""Write the Terraform variables for one plan or apply.

The workflow passes the commit SHA. This script turns service.yaml plus that
SHA into infra/ci.auto.tfvars.json. The file is generated on the runner and
is not committed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from yaml_subset import parse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--environment", required=True, choices=("staging", "prod"))
    parser.add_argument("--staging-project", default="opptra-staging")
    parser.add_argument("--sha", required=True)
    parser.add_argument("--artifact-repo", default="apps")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args(argv)

    manifest = parse(args.manifest.read_text())
    required = ["name", "archetype", "prod_project", "region", "auth"]
    missing = [key for key in required if not manifest.get(key)]
    if missing:
        raise SystemExit(f"{args.manifest} missing: {', '.join(missing)}")
    if manifest["archetype"] not in {
        "cloud-run-service",
        "cloud-run-job",
        "scheduled-jobs",
        "vm-worker",
    }:
        raise SystemExit(
            "this workflow applies cloud-run-service, cloud-run-job, scheduled-jobs, or vm-worker, "
            f"got {manifest['archetype']}"
        )
    if manifest["auth"] not in {"app-login", "iap", "public", "shared-secret", "none"}:
        raise SystemExit(f"unsupported auth {manifest['auth']}")
    if not args.sha or args.sha.startswith("latest"):
        raise SystemExit("sha must be the git commit, not a floating tag")

    project = args.staging_project if args.environment == "staging" else str(manifest["prod_project"])
    app_name = str(manifest.get("app_name") or manifest["name"])
    prefix = str(manifest.get("prefix") or app_name)
    comp_name = str(manifest["name"])
    if comp_name.startswith(f"{prefix}-") or comp_name.startswith(f"{app_name}-") or comp_name in {prefix, app_name}:
        resource_name = comp_name
    else:
        resource_name = f"{prefix}-{comp_name}"
    resource_name = resource_name[:48].rstrip("-")

    image = (
        f"{manifest['region']}-docker.pkg.dev/{project}/{args.artifact_repo}/"
        f"{resource_name}:{args.sha}"
    )
    payload: dict = {
        "project_id": project,
        "region": str(manifest["region"]),
        "name": resource_name,
        "environment": args.environment,
        "image": image,
    }
    if manifest["archetype"] == "cloud-run-service":
        payload["auth"] = str(manifest["auth"])

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n")

    if args.github_output:
        with args.github_output.open("a") as handle:
            for key, value in payload.items():
                if isinstance(value, (str, int, bool)):
                    print(f"{key}={value}", file=handle)
            if "auth" not in payload:
                print(f"auth={manifest['auth']}", file=handle)
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
