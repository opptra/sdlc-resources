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
        assert (dest / ".github" / "CODEOWNERS").is_file()
        agents = (dest / "AGENTS.md").read_text()
        assert "sdlc-rules-version: 1" in agents
        assert "feat: <ticket-id>" in agents
        assert (dest / ".cursor" / "rules" / "react.mdc").is_file()
        assert "**/frontend/**/*.{ts,tsx}" in (dest / ".cursor" / "rules" / "react.mdc").read_text()
        assert (dest / ".cursor" / "rules" / "database.mdc").is_file()
        assert "cloud-sql" in (dest / "components" / "console" / "infra" / "main.tf").read_text()
        assert "postgres:16" in (dest / "README.md").read_text()
        assert not (dest / ".cursor" / "rules" / "worker.mdc").exists()

        # Verify status --check passes on generated repo
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

        # Run phases one by one through sdlc.py
        for phase in ("check", "init-runtime", "add-data", "add-tests", "sync-infra"):
            cmd = [sys.executable, str(ROOT / "scripts" / "sdlc.py"), phase, str(manifest_path)]
            if phase != "check":
                cmd.append(str(dest))
            subprocess.run(cmd, check=True)

        comp_dir = dest / "components" / "automation"
        main_tf = (comp_dir / "infra" / "main.tf").read_text()

        # Shared image across jobs and webhook receiver, Firestore, bucket, queue, secrets, schedule, alerts
        assert 'module "service"' in main_tf
        assert "modules/cloud-run-job" in main_tf
        assert '"report-daily"' in main_tf
        assert '"belkin"' in main_tf
        assert 'module "firestore"' in main_tf
        assert 'module "bucket"' in main_tf
        assert 'module "queue"' in main_tf
        assert 'module "secrets"' in main_tf
        assert 'module "schedule"' in main_tf
        assert 'module "receiver"' in main_tf
        assert 'module "alerts"' in main_tf
        assert "cloud-sql" not in main_tf

        # Scheduler includes enabled report-daily (both crons) and excludes disabled belkin
        sched_section = main_tf.split('module "schedule"')[1].split('module "receiver"')[0]
        assert '"report-daily"' in sched_section
        assert '"report-daily-2"' in sched_section
        assert '"0 7,14 * * *"' in sched_section
        assert '"belkin"' not in sched_section

        # Data & test layers installed Firestore state + tests, not Alembic
        assert (comp_dir / "backend" / "app" / "firestore_state.py").is_file()
        assert (comp_dir / "backend" / "tests" / "test_firestore_state.py").is_file()
        assert (comp_dir / "backend" / "tests" / "test_receiver.py").is_file()
        assert not (comp_dir / "backend" / "app" / "db.py").exists()
        assert (comp_dir / "config" / "jobs.yaml").is_file()
        assert (comp_dir / "backend" / "app" / "jobs" / "report_daily.py").is_file()
        assert (comp_dir / "backend" / "app" / "jobs" / "belkin.py").is_file()

        # Rules include firestore and job, and README documents unmet recommendation
        assert (dest / ".cursor" / "rules" / "firestore.mdc").is_file()
        assert (dest / ".cursor" / "rules" / "job.mdc").is_file()
        readme = (dest / "README.md").read_text()
        assert "Platform gaps and recommendations" in readme
        assert "budget-alerts" in readme

        # status --json and --check pass
        res = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "sdlc.py"), "status", str(dest), "--json", "--check"],
            check=True,
            capture_output=True,
            text=True,
        )
        report = json.loads(res.stdout)
        assert report["aligned"] is True
        assert "firestore" in report["detected"]["capabilities_in_deps"]

        # Verify the generated job + receiver + firestore tests pass out of the box
        test_runner = (
            "import sys; from pathlib import Path; "
            "import test_run, test_firestore_state, test_receiver; "
            "test_run.test_run_returns_ok(); "
            "test_run.test_disabled_job_exits_zero_without_running(Path('.')); "
            "test_run.test_unhandled_error_exits_nonzero(Path('.')); "
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
