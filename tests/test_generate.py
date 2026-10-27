import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).resolve().parent / "fixture-service.yaml"


def test_manifest_ok() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_manifest.py"), str(FIXTURE)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_apps_script_is_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "service.yaml"
        path.write_text(
            "name: bad-app\n"
            "purpose: Try to use Apps Script.\n"
            "prod_project: opptra-applications\n"
            "region: asia-south1\n"
            "components:\n"
            "  - name: sheet\n"
            "    archetype: apps-script\n"
            "    auth: none\n"
            "    parts: [config]\n"
        )
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "check_manifest.py"), str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "Apps Script" in result.stderr


def test_generate_selects_capabilities() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "app"
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "generate.py"), str(FIXTURE), str(dest)],
            check=True,
        )
        ci = (dest / ".github" / "workflows" / "ci.yml").read_text()
        assert "opptra/sdlc-resources/.github/workflows/python-ci.yml@main" in ci
        assert "frontend-ci.yml" in ci
        assert "config-ci.yml" not in ci
        assert "push:" not in ci
        readme = (dest / "README.md").read_text()
        assert "Example console and nightly job" in readme
        assert "uv run uvicorn" in readme
        assert "npm run dev" in readme
        assert "git push" in readme
        deploy_staging = (dest / ".github" / "workflows" / "deploy-staging.yml").read_text()
        assert "branches: [staging]" in deploy_staging
        assert "deploy-cloud-run.yml" in deploy_staging
        assert "deploy-job.yml" in deploy_staging
        production = (dest / ".github" / "workflows" / "deploy-production.yml").read_text()
        assert "branches: [production]" in production
        assert "opptra/sdlc-resources/.github/workflows/deploy-job.yml@main" in production
        assert (dest / "components" / "console" / "backend" / "tests" / "test_health.py").is_file()
        assert (dest / "components" / "console" / "backend" / "app" / "db.py").is_file()
        assert (dest / "components" / "console" / "frontend" / "package.json").is_file()
        assert (dest / "components" / "nightly" / "backend" / "tests" / "test_run.py").is_file()
        assert (dest / "CLAUDE.md").is_file()
        assert (dest / ".gitignore").is_file()
        assert (dest / "openspec").is_dir()
        assert (dest / ".github" / "CODEOWNERS").is_file()
        staging = (dest / "scripts" / "bind-staging.sh").read_text()
        production = (dest / "scripts" / "bind-production.sh").read_text()
        assert 'REPO="${1:-opptra/example-app}"' in staging
        assert "opptra-sdlc-ci" in staging
        assert "does not protect branches" in staging
        assert "PROD_PROJECT" not in staging
        assert 'REPO="${1:-opptra/example-app}"' in production
        assert 'PROD_PROJECT="${2:-opptra-applications}"' in production
        assert "opptra-sdlc-ci" in production
        assert "does not protect branches" in production
        assert not (dest / "scripts" / "bind-repo.sh").exists()
        agents = (dest / "AGENTS.md").read_text()
        assert "sdlc-rules-version: 2" in agents
        assert "feat: <ticket-id>" in agents
        assert "infra: <ticket-id>" in agents
        assert ".sdlc/state.yaml" not in agents
        assert "Do not log secret values" in agents
        assert (dest / ".cursor" / "rules" / "react.mdc").is_file()
        assert "frontend/**/*.{ts,tsx}" in (dest / ".cursor" / "rules" / "react.mdc").read_text()
        assert (dest / ".cursor" / "rules" / "database.mdc").is_file()
        assert "cloud-sql" in (dest / "components" / "console" / "infra" / "main.tf").read_text()
        assert "postgres:16" in (dest / "README.md").read_text()
        assert not (dest / ".cursor" / "rules" / "worker.mdc").exists()

        status_res = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "sdlc.py"), "status", str(dest), "--check"],
            check=False,
            capture_output=True,
            text=True,
        )
        assert status_res.returncode == 0, status_res.stderr


def test_scheduled_jobs_firestore_webhook_and_unmet() -> None:
    manifest_yaml = """name: cx-automation
purpose: Run the customer-support automations in asia-south1.
prod_project: opptra-applications
region: asia-south1
components:
  - name: automation
    archetype: scheduled-jobs
    auth: none
    database: firestore
    bucket: private
    queue: cx-tickets
    alerts: true
    parts: [job]
    secrets: [freshdesk_opptra, smtp, webhook_secret]
    receiver:
      name: cx-webhook
      auth: shared-secret
      queue: cx-tickets
      secrets: [webhook_secret]
    jobs:
      - name: report-daily
        command: python -m app.jobs.report_daily
        enabled: true
        timezone: Asia/Kolkata
        schedules: ["0 7,14 * * *", "30 13 * * *"]
        timeout_seconds: 1800
        memory: 1Gi
        secrets: [freshdesk_opptra, smtp]
      - name: belkin
        command: python -m app.jobs.belkin
        enabled: false
        schedules: []
        secrets: [freshdesk_opptra]
unmet:
  - name: budget-alerts
    need: Notify billing owners at $10, $20, and $30 monthly spend.
    suggestion: Configure billing budgets once at the GCP project level in gcp-bootstrap.md.
"""
    with tempfile.TemporaryDirectory() as tmp:
        manifest_path = Path(tmp) / "service.yaml"
        manifest_path.write_text(manifest_yaml)
        dest = Path(tmp) / "cx"

        for phase in ("check", "init-runtime", "add-data", "add-tests", "sync-infra"):
            cmd = [sys.executable, str(ROOT / "scripts" / "sdlc.py"), phase, str(manifest_path)]
            if phase != "check":
                cmd.append(str(dest))
            subprocess.run(cmd, check=True)

        state_text = (dest / ".sdlc" / "state.yaml").read_text()
        assert "generator_sha:" in state_text
        head = subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True
        ).strip()
        assert head in state_text
        comp_dir = dest / "components" / "automation"
        main_tf = (comp_dir / "infra" / "main.tf").read_text()

        assert 'module "service"' in main_tf
        assert "modules/cloud-run-job" in main_tf
        assert '"cx-automation-report-daily"' in main_tf
        assert '"cx-automation-belkin"' in main_tf
        assert 'module "firestore"' in main_tf
        assert 'module "bucket"' in main_tf
        assert 'module "queue"' in main_tf
        assert 'module "secrets"' in main_tf
        assert '"cx-automation-freshdesk_opptra"' in main_tf
        assert 'module.secrets.by_id["cx-automation-freshdesk_opptra"]' in main_tf
        assert 'module.secrets.by_id["cx-automation-webhook_secret"]' in main_tf
        secrets_section = main_tf.split('module "secrets"')[1].split('module "schedule"')[0]
        assert "runtime_service_account" not in secrets_section
        assert 'module "schedule"' in main_tf
        assert 'module "receiver"' in main_tf
        assert 'module "alerts"' in main_tf
        assert "cloud-sql" not in main_tf

        sched_section = main_tf.split('module "schedule"')[1].split('module "receiver"')[0]
        assert '"cx-automation-report-daily"' in sched_section
        assert '"cx-automation-report-daily-2"' in sched_section
        assert '"0 7,14 * * *"' in sched_section
        assert "belkin" not in sched_section

        assert (comp_dir / "backend" / "app" / "firestore_state.py").is_file()
        assert (comp_dir / "backend" / "tests" / "test_firestore_state.py").is_file()
        assert (comp_dir / "backend" / "tests" / "test_receiver.py").is_file()
        assert not (comp_dir / "backend" / "app" / "db.py").exists()
        assert (comp_dir / "config" / "jobs.yaml").is_file()
        assert (comp_dir / "backend" / "app" / "jobs" / "report_daily.py").is_file()
        assert (comp_dir / "backend" / "app" / "jobs" / "belkin.py").is_file()

        assert (dest / ".cursor" / "rules" / "firestore.mdc").is_file()
        assert (dest / ".cursor" / "rules" / "job.mdc").is_file()
        assert (dest / ".env.example").is_file()
        assert "FRESHDESK_OPPTRA=replace-me" in (dest / ".env.example").read_text()
        copied_check = dest / "scripts" / "check_secret_versions.py"
        assert copied_check.is_file()
        assert copied_check.read_text() == (ROOT / "scripts" / "check_secret_versions.py").read_text()
        assert (dest / "scripts" / "render_tfvars.py").is_file()
        assert (dest / "scripts" / "yaml_subset.py").is_file()
        assert (dest / "Makefile").is_file()
        assert "ci:" in (dest / "Makefile").read_text()
        assert (dest / ".githooks" / "pre-commit").is_file()
        assert (dest / ".githooks" / "pre-push").is_file()
        assert (comp_dir / "backend" / "app" / "config.py").is_file()
        readme = (dest / "README.md").read_text()
        assert "Platform gaps and recommendations" in readme
        assert "budget-alerts" in readme
        assert "make setup" in readme

        res = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "sdlc.py"), "status", str(dest), "--json", "--check"],
            check=True,
            capture_output=True,
            text=True,
        )
        report = json.loads(res.stdout)
        assert report["aligned"] is True
        assert len(report["sections_14"]) == 17
        assert len(report["rule_pillars_5"]) == 10
        assert "firestore" in report["detected"]["capabilities_in_deps"]

        table_res = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "sdlc.py"), "doctor", str(dest)],
            check=True,
            capture_output=True,
            text=True,
        )
        assert "Table A: 17-Point SDLC Scorecard" in table_res.stdout
        assert "Table B: Section 5 Breakdown" in table_res.stdout

        test_runner = (
            "import sys; from pathlib import Path; "
            "import test_run, test_firestore_state, test_receiver; "
            "test_run.test_run_returns_ok(); "
            "test_run.test_disabled_job_exits_zero_without_running(Path('.')); "
            "test_unhandled = test_run.test_unhandled_error_exits_nonzero(Path('.')); "
            "test_firestore_state.test_lease_prevents_overlapping_run(); "
            "test_firestore_state.test_processed_idempotency(); "
            "test_receiver.test_webhook_rejects_bad_secret(); "
            "test_receiver.test_webhook_enqueues_valid_ticket()"
        )
        py_res = subprocess.run(
            [sys.executable, "-c", test_runner],
            cwd=str(comp_dir),
            env={"PYTHONPATH": f"{comp_dir / 'backend'}:{comp_dir / 'backend' / 'tests'}"},
            check=False,
            capture_output=True,
            text=True,
        )
        assert py_res.returncode == 0, py_res.stdout + py_res.stderr


def test_align_multi_region_custom_paths_and_product_contract() -> None:
    manifest_yaml = """name: performance-marketing
purpose: Alerting console for marketplace advertising.
prod_project: opptra-applications
region: asia-south1
components:
  - name: pm-dashboard
    archetype: cloud-run-service
    region: asia-southeast1
    path: .
    frontend_path: apps/web
    auth: iap
    database: bigquery
    parts: [ui, api]
  - name: noon-pipeline
    archetype: scheduled-jobs
    path: .
    auth: none
    database: bigquery
    parts: [job]
    jobs:
      - name: noon-hourly
        command: python scripts/noon/run_job.py
        schedules: ["5 * * * *"]
  - name: blinkit-pipeline
    archetype: cloud-run-job
    path: .
    auth: none
    database: bigquery
    parts: [job]
"""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "pm"
        (repo / "apps" / "web").mkdir(parents=True)
        (repo / "apps" / "web" / "package.json").write_text('{"name": "web"}\n')
        (repo / "AGENTS.md").write_text("## Product contract\n\n- NULL is not zero.\n")
        manifest_path = repo / "service.yaml"
        manifest_path.write_text(manifest_yaml)

        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "sdlc.py"),
                "sync-infra",
                str(manifest_path),
                str(repo),
                "--ci-only",
            ],
            check=True,
        )

        # Product contract preserved below managed rules block
        agents_text = (repo / "AGENTS.md").read_text()
        assert "<!-- sdlc-rules-start -->" in agents_text
        assert "<!-- sdlc-rules-end -->" in agents_text
        assert "## Product contract\n\n- NULL is not zero." in agents_text
        assert (repo / ".cursor" / "rules" / "bigquery.mdc").is_file()

        # CI jobs deduplicated to existing repo paths (. and apps/web), not 3 nonexistent components/* dirs
        ci_text = (repo / ".github" / "workflows" / "ci.yml").read_text()
        assert "working_directory: apps/web" in ci_text
        assert "components/noon-pipeline" not in ci_text
        assert "components/blinkit-pipeline" not in ci_text

        # status --check passes with zero ci_path_errors
        res = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "sdlc.py"), "status", str(repo), "--check"],
            check=False,
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0, res.stderr

        # Test discover-infra and --write-imports
        (repo / "deploy" / "dashboard").mkdir(parents=True)
        (repo / "deploy" / "dashboard" / "deploy.sh").write_text(
            "gcloud run deploy pm-dashboard --region asia-southeast1 "
            "--no-allow-unauthenticated --set-secrets=TOKEN=dashboard-token:latest\n"
        )
        disc_res = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "sdlc.py"), "discover-infra", str(repo), "--table"],
            check=True,
            capture_output=True,
            text=True,
        )
        assert "Terraform Adoption Scorecard" in disc_res.stdout
        assert "pm-dashboard" in disc_res.stdout

        imp_res = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "sdlc.py"),
                "discover-infra",
                str(repo),
                "--write-imports",
                str(manifest_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        assert (repo / "infra" / "imports.tf.example").is_file()
        assert "module.service.google_cloud_run_v2_service.app" in (
            repo / "infra" / "imports.tf.example"
        ).read_text()
        del imp_res


def test_removed_capability_rule_file_is_deleted() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp)
        script = str(ROOT / "scripts" / "build_rules.py")
        subprocess.run(
            [sys.executable, script, "--dest", str(dest), "--rules", "always", "firestore"],
            check=True,
        )
        rules = dest / ".cursor" / "rules"
        assert (rules / "firestore.mdc").is_file()
        (rules / "local.mdc").write_text("keep\n")
        subprocess.run(
            [sys.executable, script, "--dest", str(dest), "--rules", "always"],
            check=True,
        )
        assert not (rules / "firestore.mdc").exists()
        assert (rules / "always.mdc").is_file()
        assert (rules / "local.mdc").read_text() == "keep\n"
