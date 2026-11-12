#!/usr/bin/env python3
"""Compare the material changes in Terraform plans without publishing plan data."""

import argparse
import hashlib
import json
from pathlib import Path


def receipt(plan: dict, tree: str, target: str, mode: str, environment: str = "prod") -> dict:
    if plan.get("errored") or plan.get("complete") is False:
        raise ValueError("Terraform did not produce a complete plan")

    changes = plan.get("resource_changes", [])
    drift = plan.get("resource_drift", [])
    for entry in changes:
        change = entry["change"]
        actions = change["actions"]
        persistent = entry["type"] in {
            "google_bigquery_dataset", "google_bigquery_table", "google_firestore_database",
            "google_secret_manager_secret", "google_sql_database", "google_sql_database_instance",
            "google_storage_bucket",
        }
        if ("delete" in actions or "forget" in actions) and (environment == "prod" or persistent):
            raise ValueError(f"Plan removes or replaces {entry['address']}: {actions}")
        if mode == "adopt" and actions not in (["no-op"], ["read"]):
            raise ValueError(f"Adoption plan changes {entry['address']}: {actions}")

    material = {
        "terraform_version": plan["terraform_version"],
        "resources": sorted(changes, key=lambda entry: entry["address"]),
        "drift": sorted(drift, key=lambda entry: entry["address"]),
        "outputs": plan.get("output_changes", {}),
        "variables": plan.get("variables", {}),
    }
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    return {
        "version": 1,
        "tree": tree,
        "target": target,
        "mode": mode,
        "plan": hashlib.sha256(canonical).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--tree", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--environment", choices=("staging", "prod"), required=True)
    parser.add_argument("--mode", choices=("release", "adopt"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expected", type=Path)
    args = parser.parse_args()
    try:
        result = receipt(json.loads(args.plan.read_text()), args.tree, args.target, args.mode, args.environment)
        if args.expected and result != json.loads(args.expected.read_text()):
            raise ValueError("Terraform plan differs from the reviewed PR or rehearsal. Generate and review a fresh plan before applying.")
    except (KeyError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")
    args.out.write_text(json.dumps(result) + "\n")


if __name__ == "__main__":
    main()
