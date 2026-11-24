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


def setup(
    manifest_path: Path, dest: Path, ref: str, replace_bootstrap: bool, with_iam: bool = False,
) -> None:
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

    lines = ["name: Terraform promotion", "on:"]
    if with_iam:
        lines.extend([
            "  pull_request:",
            "    branches: [main, staging, production]",
            "    types: [opened, reopened, synchronize, closed]",
            "concurrency:",
            "  group: ${{ github.event.action == 'closed' && github.event.pull_request.merged && format('promotion-{0}', github.base_ref) || format('promotion-preview-{0}', github.run_id) }}",
            "  cancel-in-progress: false",
        ])
    else:
        lines.extend([
            "  workflow_dispatch:",
            "    inputs:",
            "      reviewed_run:",
            "        description: Reviewed plan run ID to apply. Leave blank to re-plan a production release.",
            "        type: string",
            "      reviewed_artifacts:",
            "        description: Space-separated Terraform artifact IDs for the reviewed run.",
            "        type: string",
            "  push:",
            "    branches: [staging]",
            "  pull_request:",
            "    branches: [main, production]",
            "    types: [opened, reopened, synchronize, closed]",
        ])
    lines.extend([
        "permissions:",
        "  contents: read",
        "  actions: read",
        "  pull-requests: read",
        "  id-token: write",
        "jobs:",
    ])
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
    if with_iam:
        iam_workflow = f"{mapping['repo']}/.github/workflows/terraform-iam.yml@{ref}"
        lines.extend([
            "  iam-plan:",
            "    if: >-",
            "      github.event_name == 'pull_request' &&",
            "      github.event.pull_request.head.repo.full_name == github.repository &&",
            "      (github.base_ref == 'staging' || (github.base_ref == 'production' && github.head_ref == 'main')) &&",
            "      (github.event.action != 'closed' || github.event.pull_request.merged)",
            f"    uses: {iam_workflow}",
        ])
        for index, args in enumerate(jobs, start=1):
            lines.extend([
                f"  preflight-{index}:",
                "    needs: [iam-plan" + (", adoption" if adopting else "") + "]",
                "    if: github.event.action == 'closed' && github.event.pull_request.merged"
                + (" && (github.base_ref != 'production' || needs.adoption.outputs.production == 'true')" if adopting else ""),
                f"    uses: {mapping['repo']}/.github/workflows/terraform-promotion.yml@{ref}",
                "    with:",
                "      protected_promotions: true",
                "      preflight: true",
            ])
            lines.extend(f"      {name}: {json.dumps(value)}" for name, value in args.items())
        preflights = ", ".join(f"preflight-{index}" for index in range(1, len(jobs) + 1))
        lines.extend([
            "  iam-apply:",
            f"    needs: [iam-plan, {preflights}]",
            "    if: github.event.action == 'closed' && github.event.pull_request.merged",
            f"    uses: {iam_workflow}",
            "    with:",
            "      apply: true",
            "      fingerprint: ${{ needs.iam-plan.outputs.fingerprint }}",
            "  iam-ready:",
            "    needs: [iam-plan, iam-apply]",
            "    if: always() && !cancelled() && needs.iam-plan.result != 'skipped'",
            "    runs-on: ubuntu-latest",
            "    permissions: {}",
            "    env:",
            "      PLAN_RESULT: ${{ needs.iam-plan.result }}",
            "      APPLY_RESULT: ${{ needs.iam-apply.result }}",
            "      PREVIEW: ${{ github.event.action != 'closed' }}",
            "    steps:",
            "      - run: |",
            "          test \"$PLAN_RESULT\" = success",
            "          [[ \"$PREVIEW\" == true || \"$APPLY_RESULT\" == success ]]",
        ])
    dependencies = ["ci"]
    if adopting:
        dependencies.append("adoption")
    if with_iam:
        dependencies.append("iam-ready")
    for index, args in enumerate(jobs, start=1):
        lines.extend([
            f"  terraform-{index}:",
            f"    needs: [{', '.join(dependencies)}]" if len(dependencies) > 1 else "    needs: ci",
            "    if: >-",
            "      ${{ always() && !cancelled() && (needs.ci.result == 'success' ||",
            "        (github.event.action == 'closed' && needs.ci.result == 'skipped'))",
        ])
        if with_iam:
            lines.append(
                "        && ((github.event_name == 'pull_request' && github.base_ref == 'main' &&"
                " needs.iam-ready.result == 'skipped') || needs.iam-ready.result == 'success')"
            )
        if adopting:
            lines.extend([
                "        && ((github.base_ref == 'staging' || github.ref == 'refs/heads/staging') || (needs.adoption.result == 'success' &&",
                "          ((github.base_ref != 'production' && github.ref != 'refs/heads/production') || needs.adoption.outputs.production == 'true')))",
            ])
        lines[-1] += " }}"
        lines.append(f"    uses: {mapping['repo']}/.github/workflows/terraform-promotion.yml@{ref}")
        lines.append("    with:")
        if with_iam:
            lines.append("      protected_promotions: true")
        else:
            lines.append("      reviewed_run: ${{ inputs.reviewed_run || '' }}")
            lines.append("      reviewed_artifacts: ${{ inputs.reviewed_artifacts || '' }}")
            if adopting:
                lines.append('      staging_mode: "reviewed"')
        lines.extend(f"      {name}: {json.dumps(value)}" for name, value in args.items())

    if with_iam:
        component_jobs = [f"terraform-{index}" for index in range(1, len(jobs) + 1)]
        dependencies = ", ".join(component_jobs)
        lines.extend([
            "  promotion-review:",
            "    name: Terraform promotion review",
            f"    needs: [ci, iam-plan, {dependencies}]",
            "    if: always() && !cancelled() && github.event.action != 'closed' && (github.base_ref == 'staging' || github.base_ref == 'production')",
            "    permissions: {}",
            "    runs-on: ubuntu-latest",
            "    env:",
            "      PASSED: ${{ !contains(needs.*.result, 'failure') && !contains(needs.*.result, 'cancelled') && !contains(needs.*.result, 'skipped') }}",
            "    steps:",
            '      - run: test "$PASSED" = true',
        ])
        applied = " && ".join(f"needs.{job}.outputs.applied == 'true'" for job in component_jobs)
        lines.extend([
            "  iam-cleanup-plan:",
            f"    needs: [{dependencies}]",
            f"    if: {applied}",
            f"    uses: {iam_workflow}",
            "    with:",
            "      phase: cleanup",
            "  iam-cleanup-apply:",
            "    needs: iam-cleanup-plan",
            "    if: needs.iam-cleanup-plan.outputs.pending == 'true'",
            f"    uses: {iam_workflow}",
            "    with:",
            "      phase: cleanup",
            "      apply: true",
            "      fingerprint: ${{ needs.iam-cleanup-plan.outputs.fingerprint }}",
        ])

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
    if with_iam:
        iam_root = dest / "infra" / "iam"
        iam_root.mkdir(parents=True, exist_ok=True)
        for source in (ROOT / "skeletons" / "iam").glob("*.json"):
            target = iam_root / source.name
            if not target.exists():
                shutil.copy2(source, target)
        helper = scripts / "bind-iam.sh"
        if not helper.exists():
            shutil.copy2(ROOT / "scripts" / helper.name, helper)
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
        if with_iam and old in contents:
            staging_instructions = (
                "Push the feature or fix branch directly to `staging`. Do not merge `main` into `staging`.\n\n"
                "```bash\ngit push origin HEAD:staging\n"
                "# Or if staging was previously pushed from another branch:\n"
                "git push --force-with-lease origin HEAD:staging\n```"
            )
            contents = contents.replace(staging_instructions,
                "Open a candidate pull request into `staging`.")
            contents = contents.replace(old,
                "After the plan checks pass, include the IAM artifact and each Terraform artifact "
                "from the run in the peer approval. Merge the reviewed pull request to deploy. "
                "If the plan changes, open a fresh promotion pull request.")
            readme.write_text(contents)
        elif old in contents:
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
    parser.add_argument("--replace-bootstrap-workflows", action="store_true",
                        help="Replace unchanged generated plan and deploy callers")
    parser.add_argument("--with-iam", action="store_true",
                        help="Generate protected staging and production promotion PRs with reviewed deployment IAM")
    args = parser.parse_args(argv)
    try:
        setup(args.manifest.resolve(), args.dest.resolve(), args.workflow_ref, args.replace_bootstrap_workflows, args.with_iam)
    except ValueError as exc:
        parser.exit(1, f"{exc}\n")
    return 0
