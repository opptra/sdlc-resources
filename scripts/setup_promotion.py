"""Write the promotion caller and its helper scripts for an SDLC Terraform app."""

import argparse
import json
import re
import shutil
import tempfile
from pathlib import Path

from check_manifest import check, normalize
from generate import ROOT, component_dir_for, load, write_workflows
from render_tfvars import deployment_name
from yaml_subset import dump


OLD_CALLERS = ("plan.yml", "deploy-staging.yml", "deploy-production.yml")


def setup(manifest_path: Path, dest: Path, ref: str, replace_bootstrap: bool) -> None:
    raw = load(manifest_path)
    errors = check(raw)
    if errors:
        raise ValueError("\n".join(errors))
    ownership = raw.get("infra_management")
    if ownership not in ("adoption", "app-owned") or manifest_path != dest / "service.yaml":
        raise ValueError("Set infra_management to adoption or app-owned in the target repository's service.yaml.")
    adopting = ownership == "adoption"
    app = normalize(raw)
    mapping = load(ROOT / "mapping.yaml")
    components = app["components"]
    if any(comp["archetype"] == "vm-worker" for comp in components):
        raise ValueError("This promotion workflow supports Cloud Run services and jobs. Keep the VM worker release path.")

    workflows = dest / ".github" / "workflows"
    caller = workflows / "promotion.yml"
    if caller.exists():
        raise ValueError("Promotion already exists. Edit the checked-in caller directly.")
    ref_pattern = r"[0-9a-f]{40}"
    if not re.fullmatch(ref_pattern, ref):
        raise ValueError("--workflow-ref must be the full published sdlc-resources commit SHA")

    jobs = []
    root_deployment = None
    for component in components:
        if component["archetype"] == "config-only":
            continue
        folder = component_dir_for(dest, component)
        manifest = folder / "service.yaml"
        if not manifest.is_file() or not (folder / "infra").is_dir():
            raise ValueError(f"Missing bootstrap manifest or Terraform in {folder}")
        if folder == dest:
            if root_deployment is not None:
                raise ValueError("Each Terraform component needs its own directory")
            manifest = dest / "service.deploy.yaml"
            if manifest.exists():
                deployment = load(manifest)
            else:
                deployment = {
                    "name": component["name"],
                    "app_name": app["name"],
                    "prefix": app["prefix"],
                    "archetype": component["archetype"],
                    "prod_project": app["prod_project"],
                    "region": component["region"],
                    "auth": component["auth"],
                }
                if component.get("legacy_service_name"):
                    deployment["legacy_service_name"] = component["legacy_service_name"]
            root_deployment = deployment
        else:
            deployment = load(manifest)
        args = {
            "component": folder.relative_to(dest).as_posix(),
            "manifest": manifest.relative_to(dest).as_posix(),
            "staging_bucket": "opptra-staging-tfstate",
            "staging_prefix": deployment_name(deployment, "staging"),
            "production_bucket": f"{deployment['prod_project']}-tfstate",
            "production_prefix": deployment_name(deployment, "prod"),
        }
        if component.get("docker_context"):
            args["docker_context"] = component["docker_context"]
            args["dockerfile"] = component["dockerfile"]
        jobs.append(args)
    if not jobs:
        raise ValueError("This repository has no Terraform workloads")
    state_locations = [pair for args in jobs for pair in (
        (args["staging_bucket"], args["staging_prefix"]),
        (args["production_bucket"], args["production_prefix"]),
    )]
    if len(set(state_locations)) != len(state_locations):
        raise ValueError("Terraform components and environments need distinct state locations")

    existing = [workflows / name for name in OLD_CALLERS if (workflows / name).exists()]
    if existing:
        if not replace_bootstrap:
            raise ValueError("Retire the old plan and deploy callers in the same PR before setting up promotion.")
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            write_workflows(mapping, components, tmp)
            for path in existing:
                generated = tmp / ".github" / "workflows" / path.name
                if not generated.is_file() or generated.read_bytes() != path.read_bytes():
                    raise ValueError(f"{path} is customized. Review and retire it explicitly before setup.")

    ci = workflows / "ci.yml"
    if not ci.is_file() or not re.search(r"(?m)^  workflow_call:", ci.read_text()):
        raise ValueError("Expose .github/workflows/ci.yml with on.workflow_call before setup.")

    lines = [
        "name: Terraform promotion",
        "on:",
        "  workflow_dispatch:",
        "    inputs:",
        "      reviewed_run:",
        "        description: Reviewed plan run ID to apply. Leave blank to re-plan a production release.",
        "        type: string",
        "  push:",
        "    branches: [staging]",
        "  pull_request:",
        "    branches: [main, production]",
        "    types: [opened, reopened, synchronize, closed]",
        "permissions:",
        "  contents: read",
        "  actions: read",
        "  pull-requests: read",
        "  id-token: write",
        "jobs:",
    ]
    lines.extend([
        "  ci:",
        "    if: github.event_name == 'push' || github.event.action != 'closed'",
        "    uses: ./.github/workflows/ci.yml",
    ])
    if adopting:
        lines.extend([
            "  adoption:",
            "    if: github.event_name == 'pull_request' || (github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/production')",
            "    runs-on: ubuntu-latest",
            "    permissions:",
            "      contents: read",
            "      actions: read",
            "    outputs:",
            "      production: ${{ steps.check.outputs.production }}",
            "    steps:",
            "      - uses: actions/checkout@v4",
            "        with:",
            "          fetch-depth: 0",
            "          ref: ${{ github.event.action == 'closed' && github.event.pull_request.merge_commit_sha || github.sha }}",
            "      - id: check",
            "        env:",
            "          GH_TOKEN: ${{ github.token }}",
            "          BASE: ${{ github.event.pull_request.base.sha || github.sha }}",
            '        run: python3 scripts/adoption_check.py --repo "$GITHUB_REPOSITORY" --base "$BASE" >> "$GITHUB_OUTPUT"',
        ])
    for index, args in enumerate(jobs, start=1):
        lines.extend([
            f"  terraform-{index}:",
            "    needs: [ci, adoption]" if adopting else "    needs: ci",
            "    if: >-",
            "      ${{ always() && !cancelled() && (needs.ci.result == 'success' ||",
            "        (github.event.action == 'closed' && needs.ci.result == 'skipped'))",
        ])
        if adopting:
            lines.extend([
                "        && (github.ref == 'refs/heads/staging' || (needs.adoption.result == 'success' &&",
                "          ((github.base_ref != 'production' && github.ref != 'refs/heads/production') || needs.adoption.outputs.production == 'true')))",
            ])
        lines[-1] += " }}"
        lines.append(f"    uses: {mapping['repo']}/.github/workflows/terraform-promotion.yml@{ref}")
        lines.append("    with:")
        lines.append("      reviewed_run: ${{ inputs.reviewed_run || '' }}")
        if adopting:
            lines.append('      staging_mode: "reviewed"')
        lines.extend(f"      {name}: {json.dumps(value)}" for name, value in args.items())

    workflows.mkdir(parents=True, exist_ok=True)
    scripts = dest / "scripts"
    scripts.mkdir(exist_ok=True)
    helpers = ["promotion_receipt.py", "render_tfvars.py", "yaml_subset.py"]
    if adopting:
        helpers.append("adoption_check.py")
    for name in helpers:
        path = scripts / name
        if not path.exists():
            shutil.copy2(ROOT / "scripts" / name, path)
    if root_deployment is not None and not (dest / "service.deploy.yaml").exists():
        (dest / "service.deploy.yaml").write_text(dump(root_deployment))
    caller.write_text("\n".join(lines) + "\n")
    for path in existing:
        path.unlink()
    readme = dest / "README.md"
    if readme.is_file():
        old = (
            "To deploy the current `staging` or `production` commit again without a new push, "
            "start `deploy-staging` or `deploy-production` from the Actions page and choose that branch. "
            "The jobs run only on the matching branch and load the current shared workflows."
        )
        contents = readme.read_text()
        if old in contents:
            readme.write_text(contents.replace(
                old,
                "Review the Terraform plan in the production PR's Actions check. Merging that PR "
                "applies the reviewed changes through `.github/workflows/promotion.yml`.",
                1,
            ))
    print(f"Created {caller}. Verify state locations and configure the GitHub environments before enabling deployment.")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("dest", type=Path, nargs="?", default=Path("."))
    parser.add_argument("--workflow-ref", required=True)
    parser.add_argument("--replace-bootstrap-workflows", action="store_true")
    args = parser.parse_args(argv)
    try:
        setup(args.manifest.resolve(), args.dest.resolve(), args.workflow_ref, args.replace_bootstrap_workflows)
    except ValueError as exc:
        parser.exit(1, f"{exc}\n")
    return 0
