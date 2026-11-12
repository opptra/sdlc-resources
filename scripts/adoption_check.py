"""Validate the parity report and staging run for a legacy Terraform handoff."""

import argparse
import json
from pathlib import Path
import re
import subprocess

from yaml_subset import parse


REPORT = "docs/terraform-adoption.json"
CATEGORIES = {
    "workloads", "triggers", "runtime", "identity", "secrets", "data", "release",
}
DISPOSITIONS = {"create", "import", "reference", "retain-external", "retire"}


def manifest_at(revision: str) -> dict:
    result = subprocess.run(
        ["git", "show", f"{revision}:service.yaml"], text=True, capture_output=True,
    )
    return parse(result.stdout) if result.returncode == 0 else {}


def text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_report(report: dict) -> None:
    if not text(report.get("review")):
        raise ValueError("Record the parity review link or reference.")
    rows = report.get("items")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("Provide parity items for every required category.")
    seen = set()
    for row in rows:
        category = row.get("category")
        name = row.get("item")
        if category not in CATEGORIES or not text(name):
            raise ValueError(f"Unknown category or missing item name: {category}")
        seen.add(category)
        for field in ("live", "legacy", "proposed"):
            if not text(row.get(field)):
                raise ValueError(f"{name}: record {field} evidence or explain its verified absence.")
        if row.get("status") == "not-applicable":
            if not text(row.get("reason")):
                raise ValueError(f"{name}: explain why this category does not apply.")
            continue
        if row.get("status") not in ("verified", "intentional-difference"):
            raise ValueError(f"{name}: resolve missing or unverified coverage.")
        if row.get("disposition") not in DISPOSITIONS:
            raise ValueError(f"{name}: record its disposition.")
        for field in ("owner", "verification"):
            if not text(row.get(field)):
                raise ValueError(f"{name}: record {field}.")
        if (row["status"] == "intentional-difference" or row["disposition"] == "retire") and not text(row.get("reason")):
            raise ValueError(f"{name}: explain the difference or retirement for review.")
    if seen != CATEGORIES:
        raise ValueError(f"Missing parity categories: {', '.join(sorted(CATEGORIES - seen))}")


def validate_staging(report: dict, manifest: dict, repo: str) -> None:
    staging = report.get("staging", {})
    if not isinstance(staging, dict):
        raise ValueError("Record the staging rehearsal run and commit.")
    sha = staging.get("commit")
    run_id = staging.get("run_id")
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha) or type(run_id) is not int or run_id < 1:
        raise ValueError("Record the staging rehearsal run ID and full commit SHA.")

    rehearsed = manifest_at(sha)
    if rehearsed.pop("infra_management", None) != "adoption" or rehearsed != {
        key: value for key, value in manifest.items() if key != "infra_management"
    }:
        raise ValueError("The rehearsal must use the same manifest with infra_management: adoption.")
    # Only the ownership switch and the report may differ from the rehearsed tree.
    diff = subprocess.run(
        ["git", "diff", "--exit-code", sha, "--", ".", ":(exclude)service.yaml", f":(exclude){REPORT}"],
        stdout=subprocess.DEVNULL, check=False,
    )
    if diff.returncode:
        raise ValueError("The proposed tree differs from the staged rehearsal. Rehearse the updated tree.")

    def github(path: str) -> dict:
        result = subprocess.run(
            ["gh", "api", f"repos/{repo}/actions/runs/{run_id}{path}"],
            text=True, capture_output=True,
        )
        if result.returncode:
            raise ValueError("Could not verify the staging run. Check GitHub Actions read access.")
        return json.loads(result.stdout)

    run = github("")
    expected = {
        "head_branch": "staging", "head_sha": sha,
        "conclusion": "success", "path": ".github/workflows/promotion.yml",
    }
    if run.get("event") not in ("push", "workflow_dispatch") or any(
        run.get(key) != value for key, value in expected.items()
    ):
        raise ValueError("Use a successful staging apply run of promotion.yml for the recorded commit.")
    jobs = github(f"/attempts/{run['run_attempt']}/jobs?per_page=100")
    applies = [
        step for job in jobs["jobs"] for step in job.get("steps", [])
        if step["name"] == "Completed staging release"
    ]
    deploy_jobs = [
        job for job in jobs["jobs"]
        if any(step["name"] == "Apply reviewed plan" for step in job.get("steps", []))
    ]
    caller = Path(expected["path"]).read_text()
    expected_jobs = len(re.findall(r"^  terraform-\d+:$", caller, re.MULTILINE))
    if not expected_jobs or len(deploy_jobs) != expected_jobs or len(applies) != expected_jobs or any(
        step["conclusion"] != "success" for step in applies
    ):
        raise ValueError("The staging rehearsal must execute the deployment and checks, not just plan.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="GitHub owner/repository")
    parser.add_argument("--base", help="PR base commit. Skip repeat validation after handoff.")
    args = parser.parse_args(argv)
    try:
        manifest = parse(Path("service.yaml").read_text())
        mode = manifest.get("infra_management")
        if mode not in ("adoption", "app-owned"):
            raise ValueError("Keep the migration in adoption until handoff.")
        if mode == "app-owned" and (
            not args.base or manifest_at(args.base).get("infra_management") != "app-owned"
        ):
            report = json.loads(Path(REPORT).read_text())
            if not isinstance(report, dict):
                raise ValueError("The parity report must be a JSON object.")
            validate_report(report)
            validate_staging(report, manifest, args.repo)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Adoption check: {exc}\n")
    print(f"production={'true' if mode == 'app-owned' else 'false'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
