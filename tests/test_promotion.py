"""Offline integration coverage for handoff and reviewed Terraform promotion."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixture-service.yaml"


class PromotionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()

    def odlc(self, *args, check=True):
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "odlc.py"), *map(str, args)],
            check=check, capture_output=True, text=True,
        )

    @unittest.skipUnless(shutil.which("jq") and shutil.which("unzip"), "requires jq and unzip")
    def test_reviewed_dispatch_downloads_selected_artifact_by_id(self):
        import zipfile

        workflow = (ROOT / ".github/workflows/terraform-promotion.yml").read_text()
        step = workflow.split("      - name: Resolve reviewed image and plan", 1)[1]
        script = textwrap.dedent(step.split("        run: |\n", 1)[1].split("      - name:", 1)[0])
        runner = self.root
        image = "example/release@" + "sha256:" + "a" * 64
        (runner / "release.tfvars.json").write_text(json.dumps({"image": "example/release:tree"}))
        with zipfile.ZipFile(runner / "artifact.zip", "w") as archive:
            archive.writestr("receipt.json", json.dumps({"tree": "tree", "target": "bucket/app", "mode": "release"}))
            archive.writestr("image.json", json.dumps({"image": image}))
        gh = runner / "gh"
        gh.write_text("""#!/bin/bash
case "$2" in
  */artifacts/123) echo '{"name":"terraform-staging-component-42-1","workflow_run":{"id":42},"expired":false}' ;;
  */artifacts/124) echo '{"name":"terraform-staging-component-42-2","workflow_run":{"id":42},"expired":false}' ;;
  */runs/42/attempts/1) echo '{"path":".github/workflows/promotion.yml","event":"push","head_branch":"staging","head_sha":"abc","conclusion":"success"}' ;;
  */artifacts/123/zip) cat "$RUNNER_TEMP/artifact.zip" ;;
  *) exit 1 ;;
esac
""")
        gh.chmod(0o755)
        env = dict(os.environ, PATH=f"{runner}:{os.environ['PATH']}", RUNNER_TEMP=str(runner),
                   GITHUB_WORKFLOW_REF="org/app/.github/workflows/promotion.yml@refs/heads/staging",
                   GITHUB_REPOSITORY="org/app", GITHUB_EVENT_NAME="workflow_dispatch", GITHUB_SHA="abc",
                   BUILT_IMAGE="", REVIEWED_RUN="42", REVIEWED_ARTIFACTS="123", TARGET="staging",
                   ARTIFACT="terraform-staging-component", TREE="tree", BUCKET="bucket", PREFIX="app",
                   MODE="release", IMAGE_TAG="example/release:tree")
        valid = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)
        self.assertEqual(valid.returncode, 0, valid.stderr)
        self.assertEqual(json.loads((runner / "image.json").read_text())["image"], image)
        ambiguous = subprocess.run(["bash", "-c", script], env=env | {"REVIEWED_ARTIFACTS": "123 124"},
                                   capture_output=True, text=True)
        self.assertNotEqual(ambiguous.returncode, 0)
        self.assertIn("Select exactly one", ambiguous.stderr)

    def test_backend_selection_cannot_fall_back_to_other_environment(self):
        workflow = (ROOT / ".github/workflows/terraform-promotion.yml").read_text()
        backend = workflow.split("  backend:\n", 1)[1].split("\n  build:\n", 1)[0]
        script = textwrap.dedent(backend.split("        run: |\n", 1)[1])
        output = self.root / "outputs"
        defaults = dict(
            TARGET="prod", STAGING_BUCKET="stage", STAGING_PREFIX="stage-app",
            PRODUCTION_BUCKET="production", PRODUCTION_PREFIX="prod-app",
            GITHUB_OUTPUT=str(output),
        )

        def select(**overrides):
            output.unlink(missing_ok=True)
            return subprocess.run(
                ["bash", "-c", script], env={**os.environ, **defaults, **overrides},
                capture_output=True, text=True,
            )

        for missing in ("PRODUCTION_BUCKET", "PRODUCTION_PREFIX"):
            with self.subTest(missing=missing):
                result = select(**{missing: ""})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("production_bucket and production_prefix", result.stderr)
                self.assertFalse(output.exists())

        result = select(PRODUCTION_PREFIX="  ")
        self.assertNotEqual(result.returncode, 0)
        result = select()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output.read_text(), "bucket=production\nprefix=prod-app\n")
        result = select(TARGET="staging", PRODUCTION_BUCKET="")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output.read_text(), "bucket=stage\nprefix=stage-app\n")
        result = select(PRODUCTION_BUCKET="stage", PRODUCTION_PREFIX="stage-app")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("separate Terraform state", result.stderr)

    def test_handoff_preserves_deployment_files_and_blocks_bootstrap(self):
        repo = self.root / "app"
        self.odlc("all", FIXTURE, repo)
        manifest = repo / "service.yaml"
        manifest.write_text(manifest.read_text() + "\ninfra_management: app-owned\n")
        old_workflow = repo / ".github/workflows/deploy-staging.yml"
        old_workflow.write_text(old_workflow.read_text() + "# app changes\n")
        protected = {
            file: file.read_bytes()
            for file in repo.rglob("*")
            if file.is_file() and (
                {"infra", "workflows", "scripts"} & set(file.relative_to(repo).parts)
                or file.name in {"Makefile", "service.yaml"}
            )
        }
        agents = repo / "AGENTS.md"
        agents.write_text(agents.read_text().replace("sdlc-rules-version: 3", "sdlc-rules-version: 2")
                          + "\n## Product contract\n\nKeep me.\n")
        for command in ("sync", "sync-infra"):
            self.odlc(command, manifest, repo)
        for command in ("all", "init-runtime", "add-data", "add-tests", "sync"):
            self.assertNotEqual(self.odlc(command, FIXTURE, repo, check=False).returncode, 0)
        self.assertNotEqual(self.odlc("discover", repo, "--write-imports", FIXTURE, check=False).returncode, 0)
        self.assertEqual(protected, {file: file.read_bytes() for file in protected})
        self.assertIn("sdlc-rules-version: 3", agents.read_text())
        self.assertIn("Keep me.", agents.read_text())
        for rule in ("AGENTS.md", "CLAUDE.md", ".cursor/rules/always.mdc"):
            self.assertIn("docs/terraform-adoption.json", (repo / rule).read_text())
        report = json.loads(self.odlc("status", repo, "--json").stdout)
        self.assertEqual(report["infra_management"], "app-owned")
        self.assertEqual(report["terraform_roots"], ["components/console/infra", "components/nightly/infra"])

    def test_promotion_setup_preserves_custom_legacy_callers(self):
        repo = self.root / "app"
        self.odlc("all", FIXTURE, repo)
        manifest = repo / "service.yaml"
        manifest.write_text(manifest.read_text() + "\ninfra_management: app-owned\n")
        workflows = repo / ".github/workflows"
        old = workflows / "deploy-staging.yml"
        original = old.read_text()
        old.write_text(original + "# custom deployment\n")
        args = ("setup-promotion", manifest, repo, "--workflow-ref", "a" * 40,
                "--replace-bootstrap-workflows")
        blocked = self.odlc(*args, check=False)
        self.assertIn("customized", blocked.stderr)
        self.assertEqual(old.read_text(), original + "# custom deployment\n")
        self.assertFalse((workflows / "promotion.yml").exists())
        old.write_text(original)
        self.odlc(*args)
        self.assertFalse(old.exists())
        self.assertFalse((workflows / "deploy-production.yml").exists())
        self.assertFalse((workflows / "plan.yml").exists())
        caller = (workflows / "promotion.yml").read_text()
        self.assertIn("branches: [staging]", caller)
        self.assertIn("branches: [main, production]", caller)
        self.assertIn("types: [opened, reopened, synchronize, closed]", caller)
        self.assertEqual(caller.count("terraform-promotion.yml@" + "a" * 40), 2)
        self.assertIn('staging_bucket: "opptra-staging-tfstate"', caller)
        self.assertIn('production_bucket: "opptra-applications-tfstate"', caller)
        self.assertNotEqual(self.odlc(*args, check=False).returncode, 0)

    def test_iam_setup_wires_one_gate_for_all_components(self):
        repo = self.root / "app"
        self.odlc("all", FIXTURE, repo)
        manifest = repo / "service.yaml"
        manifest.write_text(manifest.read_text() + "\ninfra_management: app-owned\n")
        self.odlc("setup-promotion", manifest, repo, "--workflow-ref", "a" * 40,
                  "--replace-bootstrap-workflows", "--with-iam")
        caller = (repo / ".github/workflows/promotion.yml").read_text()
        self.assertEqual(caller.count("terraform-iam.yml@" + "a" * 40), 4)
        self.assertEqual(caller.count("needs: [ci, iam-ready]"), 2)
        self.assertIn("fingerprint: ${{ needs.iam-plan.outputs.fingerprint }}", caller)
        self.assertEqual(json.loads((repo / "infra/iam/production.json").read_text()), {})
        self.assertEqual(json.loads((repo / "infra/iam/staging.json").read_text()), {})
        self.assertTrue((repo / "scripts/bind-iam.sh").exists())
        self.assertNotIn("apply_iam:", caller)
        self.assertNotIn("iam_pr:", caller)
        self.assertIn("needs: [terraform-1, terraform-2]", caller)
        self.assertIn("needs.terraform-1.outputs.applied == 'true' && needs.terraform-2.outputs.applied == 'true'", caller)
        self.assertIn("phase: cleanup", caller)
        workflow = (ROOT / ".github/workflows/terraform-promotion.yml").read_text()
        self.assertIn('if [[ -n "$POST_APPLY" ]]', workflow.split("Record verified apply")[1])
        for phase in ("staging", "production"):
            help_text = subprocess.check_output(["bash", str(repo / f"scripts/bind-{phase}.sh"), "--help"],
                                                text=True)
            self.assertIn("--with-iam", help_text)
            self.assertIn("IAM_GRANT_ROLES", help_text)

    @unittest.skipUnless(shutil.which("jq"), "requires jq")
    def test_iam_workflow_reads_only_delegated_grant_data(self):
        workflow = (ROOT / ".github/workflows/terraform-iam.yml").read_text()
        step = workflow.split("      - name: Read declarations and prepare Terraform", 1)[1]
        script = textwrap.dedent(step.split("        run: |\n", 1)[1].split("      - uses:", 1)[0])
        gh = self.root / "gh"
        gh.write_text('#!/bin/bash\ncat "$GRANT_FIXTURE"\n')
        gh.chmod(0o755)
        declaration = self.root / "fixture.json"
        member = "serviceAccount:planner@example-project.iam.gserviceaccount.com"
        grant = {"member": member, "role": "roles/pubsub.viewer", "adopt": True}
        env = dict(os.environ, PATH=f"{self.root}:{os.environ['PATH']}", SOURCE_SHA="f" * 40,
                   GITHUB_REPOSITORY="org/app", TARGET="staging", PROJECT="example-project",
                   BUCKET="example-state", ROLES='["roles/pubsub.viewer"]', MEMBERS=json.dumps([member]),
                   GRANT_FIXTURE=str(declaration))
        for label, grants, expected in [
            ("empty", {}, 0),
            ("adopt", {"existing": grant}, 0),
            ("outside-scope", {"grant": grant | {"role": "roles/owner"}}, 1),
            ("unknown-member", {"grant": grant | {"member": "user:someone@example.com"}}, 1),
            ("duplicate", {"first": grant, "second": grant}, 1),
        ]:
            with self.subTest(label=label):
                temp = self.root / label
                temp.mkdir()
                declaration.write_text(json.dumps(grants))
                result = subprocess.run(["bash", "-c", script], env=env | {"RUNNER_TEMP": str(temp)},
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, expected, result.stderr)
                if expected == 0:
                    tfvars = json.loads((temp / "iam/terraform.tfvars.json").read_text())
                    self.assertEqual(tfvars, {"project": "example-project", "grants": grants})

    @unittest.skipUnless(shutil.which("jq"), "requires jq")
    def test_iam_apply_rechecks_the_preview_before_writing(self):
        workflow = (ROOT / ".github/workflows/terraform-iam.yml").read_text()
        step = workflow.split("      - name: Plan or apply reviewed grants", 1)[1]
        script = textwrap.dedent(step.split("        run: |\n", 1)[1])
        terraform = self.root / "terraform"
        terraform.write_text("""#!/bin/bash
case "$1" in
  init) exit 0 ;;
  state) echo '{"resources":[]}' ;;
  plan) exit 2 ;;
  show) cat "$FIXTURE_PLAN" ;;
  apply) touch applied ;;
  *) exit 1 ;;
esac
""")
        terraform.chmod(0o755)
        gh = self.root / "gh"
        gh.write_text('#!/bin/bash\nprintf "%s\\n" "$GITHUB_SHA"\n')
        gh.chmod(0o755)
        member = "serviceAccount:planner@example-project.iam.gserviceaccount.com"
        plan = self.root / "fixture.json"
        plan.write_text(json.dumps({
            "terraform_version": "1.10.5",
            "resource_changes": [{
                "mode": "managed",
                "type": "google_project_iam_member",
                "change": {"actions": ["create"], "before": None,
                           "after": {"project": "example-project", "member": member, "role": "roles/pubsub.viewer"}},
            }],
        }))
        output = self.root / "outputs"
        env = dict(os.environ, PATH=f"{self.root}:{os.environ['PATH']}", FIXTURE_PLAN=str(plan),
                   TARGET="staging", PROJECT="example-project", BUCKET="example-state",
                   PHASE="additions",
                   ROLES='["roles/pubsub.viewer"]', MEMBERS=json.dumps([member]), APPLY="false",
                   SOURCE_SHA="a" * 40, GITHUB_SHA="a" * 40, GITHUB_REPOSITORY="org/app",
                   GITHUB_OUTPUT=str(output), GITHUB_STEP_SUMMARY=str(self.root / "summary"))

        def run(**overrides):
            return subprocess.run(["bash", "-c", script], env=env | overrides, cwd=self.root,
                                  capture_output=True, text=True)

        (self.root / "terraform.tfvars.json").write_text(json.dumps({"project": "example-project", "grants": {}}))
        preview = run()
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertIn("pending=true", output.read_text())
        fingerprint = output.read_text().splitlines()[0].split("=", 1)[1]
        stale = run(APPLY="true", EXPECTED=fingerprint, SOURCE_SHA="b" * 40)
        self.assertIn("IAM plan changed", stale.stderr)
        self.assertFalse((self.root / "applied").exists())
        applied = run(APPLY="true", EXPECTED=fingerprint)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertTrue((self.root / "applied").exists())

    @unittest.skipUnless(shutil.which("jq"), "requires jq")
    def test_iam_additions_keep_old_access_and_cleanup_uses_desired_grants(self):
        workflow = (ROOT / ".github/workflows/terraform-iam.yml").read_text()
        step = workflow.split("      - name: Plan or apply reviewed grants", 1)[1]
        script = textwrap.dedent(step.split("        run: |\n", 1)[1]).split("lock=(-lock=false)", 1)[0]
        old = {"member": "serviceAccount:app@example.iam.gserviceaccount.com", "role": "roles/pubsub.viewer"}
        new = old | {"role": "roles/pubsub.publisher"}
        state = self.root / "state.json"
        state.write_text(json.dumps({"resources": [{"type": "google_project_iam_member", "name": "grant",
            "instances": [{"index_key": "reader", "attributes": old}]}]}))
        terraform = self.root / "terraform"
        terraform.write_text('#!/bin/bash\nif [[ "$1" == init ]]; then exit 0; fi\ncat "$STATE_FIXTURE"\n')
        terraform.chmod(0o755)
        tfvars = self.root / "terraform.tfvars.json"
        env = dict(os.environ, PATH=f"{self.root}:{os.environ['PATH']}", STATE_FIXTURE=str(state),
                   BUCKET="state", PHASE="additions", GITHUB_STEP_SUMMARY=str(self.root / "summary"))
        def run(grants, phase):
            tfvars.write_text(json.dumps({"project": "example", "grants": grants}))
            return subprocess.run(["bash", "-c", script], cwd=self.root, env=env | {"PHASE": phase},
                                  capture_output=True, text=True)
        added = run({"publisher": new}, "additions")
        self.assertEqual(added.returncode, 0, added.stderr)
        self.assertEqual(json.loads(tfvars.read_text())["grants"], {"reader": old, "publisher": new})
        cleanup = run({"publisher": new}, "cleanup")
        self.assertEqual(cleanup.returncode, 0, cleanup.stderr)
        self.assertEqual(json.loads(tfvars.read_text())["grants"], {"publisher": new})
        renamed = run({"new-reader-name": old}, "additions")
        self.assertNotEqual(renamed.returncode, 0)
        self.assertIn("key rename", renamed.stderr)
        replaced = run({"reader": new}, "additions")
        self.assertNotEqual(replaced.returncode, 0)
        self.assertIn("Use a new key", replaced.stderr)

    @unittest.skipUnless(shutil.which("jq"), "requires jq")
    def test_production_iam_write_rejects_an_open_pr(self):
        workflow = (ROOT / ".github/workflows/terraform-iam.yml").read_text()
        step = workflow.split("      - name: Resolve trusted source", 1)[1]
        script = textwrap.dedent(step.split("        run: |\n", 1)[1].split("      - name:", 1)[0])
        event = self.root / "event.json"
        event.write_text('{"action":"opened"}')
        env = dict(os.environ, GITHUB_EVENT_NAME="pull_request", TARGET="production",
                   GITHUB_BASE_REF="production", GITHUB_HEAD_REF="main", GITHUB_REF="refs/pull/1/merge",
                   GITHUB_SHA="a" * 40, GITHUB_EVENT_PATH=str(event), APPLY="true", EXPECTED="f" * 64,
                   MERGED="false", MERGE_SHA="", GITHUB_OUTPUT=str(self.root / "out"),
                   GITHUB_STEP_SUMMARY=str(self.root / "summary"))
        denied = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)
        self.assertNotEqual(denied.returncode, 0)
        self.assertIn("Production IAM writes require", denied.stderr)
        preview = subprocess.run(["bash", "-c", script], env=env | {"APPLY": "false"},
                                 capture_output=True, text=True)
        self.assertEqual(preview.returncode, 0, preview.stderr)

    def test_adoption_gates_handoff_but_not_routine_changes(self):
        repo = self.root / "app"
        self.odlc("all", FIXTURE, repo)
        manifest = repo / "service.yaml"
        bootstrap = manifest.read_text()
        manifest.write_text(bootstrap + "\ninfra_management: adoption\n")
        self.odlc("setup-promotion", manifest, repo, "--workflow-ref", "a" * 40,
                  "--replace-bootstrap-workflows")
        caller = (repo / ".github/workflows/promotion.yml").read_text()
        self.assertIn("needs.adoption.outputs.production == 'true'", caller)
        self.assertIn('staging_mode: "reviewed"', caller)
        self.assertIn("workflow_dispatch:", caller)

        def git(*args):
            return subprocess.run(
                ["git", "-c", "user.name=SDLC test", "-c", "user.email=test@example.invalid", *args],
                cwd=repo, check=True, capture_output=True, text=True,
            ).stdout.strip()

        def check(*args):
            return subprocess.run(
                [sys.executable, str(ROOT / "scripts/odlc.py"), "adoption-check",
                 "--repo", "opptra/example", *args],
                cwd=repo, env=env, capture_output=True, text=True,
            )

        mock = self.root / "gh"
        mock.write_text(
            '#!/bin/sh\ncase "$2" in */jobs*) cat "$ADOPTION_JOBS";; *) cat "$ADOPTION_RUN";; esac\n'
        )
        mock.chmod(0o755)
        run = self.root / "run.json"
        jobs = self.root / "jobs.json"
        env = dict(os.environ, PATH=f"{self.root}{os.pathsep}{os.environ['PATH']}",
                   ADOPTION_RUN=str(run), ADOPTION_JOBS=str(jobs))
        git("init")
        git("add", ".")
        git("commit", "-m", "Rehearsal")
        sha = git("rev-parse", "HEAD")
        self.assertEqual(check().stdout.strip(), "production=false")
        manifest.write_text(bootstrap + "\ninfra_management: app-owned\n")

        report = repo / "docs/terraform-adoption.json"
        report.parent.mkdir(exist_ok=True)
        rows = [
            dict(category=category, item=category, live="Live inventory",
                 legacy="Deploy script", proposed="Workflow or Terraform",
                 status="verified", disposition="import", owner="App",
                 verification="Staging run evidence")
            for category in ("workloads", "triggers", "runtime", "identity", "secrets", "data", "release")
        ]

        def write_report(items):
            report.write_text(json.dumps(dict(review="Migration PR", items=items,
                                              staging=dict(run_id=42, commit=sha))))

        write_report(rows[:-1])
        self.assertIn("Missing parity categories: release", check().stderr)
        rows[1]["status"] = "unverified"
        write_report(rows)
        self.assertIn("resolve missing or unverified", check().stderr)
        rows[1]["status"] = "verified"
        write_report(rows)
        run.write_text(json.dumps(dict(event="workflow_dispatch", head_branch="staging", head_sha=sha,
                                       conclusion="success", path=".github/workflows/promotion.yml",
                                       run_attempt=1)))
        steps = [dict(name="Apply reviewed plan", conclusion="success")]
        jobs.write_text(json.dumps(dict(jobs=[dict(steps=steps)])))
        self.assertIn("must execute the deployment", check().stderr)
        steps.append(dict(name="Completed staging release", conclusion="success"))
        jobs.write_text(json.dumps(dict(jobs=[dict(steps=steps)])))
        self.assertIn("must execute the deployment", check().stderr)
        jobs.write_text(json.dumps(dict(jobs=[dict(steps=steps), dict(steps=steps)])))
        result = check("--base", sha)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "production=true")

        git("add", ".")
        git("commit", "-m", "Handoff")
        handoff = git("rev-parse", "HEAD")
        (repo / ".github/workflows/promotion.yml").write_text(caller + "# Later release edit\n")
        self.assertIn("Rehearse the updated tree", check("--base", sha).stderr)
        report.unlink()
        self.assertEqual(check("--base", handoff).stdout.strip(), "production=true")

    @unittest.skipUnless(shutil.which("terraform"), "Terraform CLI required")
    def test_real_plans_use_separate_state_and_require_review(self):
        def terraform(directory, *args):
            return subprocess.run(
                ["terraform", *args], cwd=directory, check=True, capture_output=True, text=True,
            ).stdout

        def plan(directory, value, name):
            terraform(directory, "plan", "-input=false", f"-var=release={value}", f"-out={name}.tfplan")
            path = directory / f"{name}.json"
            path.write_text(terraform(directory, "show", "-json", f"{name}.tfplan"))
            return path

        def verify(path, out, environment, *args):
            return subprocess.run(
                [sys.executable, str(ROOT / "scripts/promotion_receipt.py"), str(path),
                 "--environment", environment, "--tree", "reviewed-source", "--target", environment,
                 "--mode", "release", "--out", str(out), *map(str, args)],
                capture_output=True, text=True,
            )

        config = '''
variable "release" {
  type = string
}
resource "terraform_data" "app" {
  input = var.release
}
'''
        staging = self.root / "staging"
        production = self.root / "production"
        for directory in (staging, production):
            directory.mkdir()
            (directory / "main.tf").write_text(config)
            terraform(directory, "init", "-input=false")
            terraform(directory, "validate")
        stage_plan = plan(staging, "candidate", "stage")
        self.assertEqual(verify(stage_plan, staging / "receipt.json", "staging").returncode, 0)
        terraform(staging, "apply", "-input=false", "stage.tfplan")
        self.assertFalse((production / "terraform.tfstate").exists())

        reviewed = plan(production, "candidate", "reviewed")
        receipt_path = production / "reviewed-receipt.json"
        self.assertEqual(verify(reviewed, receipt_path, "prod").returncode, 0)
        self.assertFalse((production / "terraform.tfstate").exists())
        final = plan(production, "candidate", "final")
        result = verify(final, production / "final-receipt.json", "prod", "--expected", receipt_path)
        self.assertEqual(result.returncode, 0, result.stderr)
        different = plan(production, "unreviewed-change", "different")
        result = verify(different, production / "final-receipt.json", "prod", "--expected", receipt_path)
        self.assertIn("differs from the reviewed PR", result.stderr)
        self.assertNotEqual(result.returncode, 0)
        terraform(production, "apply", "-input=false", "final.tfplan")

        (production / "main.tf").write_text('variable "release" { type = string }\n')
        destructive = plan(production, "candidate", "destructive")
        self.assertIn("removes or replaces", verify(destructive, receipt_path, "prod").stderr)

    @unittest.skipUnless(shutil.which("terraform"), "Terraform CLI required")
    def test_adoption_plan_imports_without_creating(self):
        repo = self.root
        (repo / "main.tf").write_text('''
resource "terraform_data" "existing" {}
import {
  to = terraform_data.existing
  id = "legacy-id"
}
''')
        def terraform(*args):
            return subprocess.run(
                ["terraform", *args], cwd=repo, check=True, capture_output=True, text=True,
            ).stdout
        terraform("init", "-input=false")
        terraform("plan", "-input=false", "-out=adopt.tfplan")
        path = repo / "plan.json"
        path.write_text(terraform("show", "-json", "adopt.tfplan"))
        plan = json.loads(path.read_text())
        self.assertEqual(plan["resource_changes"][0]["change"]["importing"]["id"], "legacy-id")
        subprocess.run(
            [sys.executable, str(ROOT / "scripts/promotion_receipt.py"), str(path),
             "--environment", "prod", "--tree", "reviewed-source", "--target", "production",
             "--mode", "adopt", "--out", str(repo / "receipt.json")],
            check=True, capture_output=True, text=True,
        )
        terraform("apply", "-input=false", "adopt.tfplan")
        self.assertIn("legacy-id", terraform("state", "show", "terraform_data.existing"))


if __name__ == "__main__":
    unittest.main()
