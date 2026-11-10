"""Offline integration coverage for handoff and reviewed Terraform promotion."""

import json
import shutil
import subprocess
import sys
import tempfile
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
