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
        assert "git push origin HEAD:staging" in readme
        assert "git merge main" not in readme
        assert ".devcontainer/devcontainer.json" in readme
        devcontainer = json.loads((dest / ".devcontainer" / "devcontainer.json").read_text())
        assert "@fission-ai/openspec@1.15.0" in devcontainer["postCreateCommand"]
        deploy_staging = (dest / ".github" / "workflows" / "deploy-staging.yml").read_text()
        assert "branches: [staging]" in deploy_staging
        assert "workflow_dispatch:" in deploy_staging
        assert "github.ref == 'refs/heads/staging'" in deploy_staging
        assert "deploy-cloud-run.yml" in deploy_staging
        assert "deploy-job.yml" in deploy_staging
        assert "docker_context:" not in deploy_staging
        production = (dest / ".github" / "workflows" / "deploy-production.yml").read_text()
        assert "branches: [production]" in production
        assert "workflow_dispatch:" in production
        assert "github.ref == 'refs/heads/production'" in production
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
        assert "Do not ask the user to name a skill or to run a script." in agents
        assert (dest / ".cursor" / "rules" / "react.mdc").is_file()
        react_rule = (dest / ".cursor" / "rules" / "react.mdc").read_text()
        assert "frontend/**/*.{ts,tsx,css}" in react_rule
        assert "opptra.github.io/opptra-design-system" in react_rule
        assert (dest / "components" / "console" / "frontend" / "src" / "tokens.css").is_file()
        assert (dest / ".cursor" / "rules" / "database.mdc").is_file()
        assert "cloud-sql" in (dest / "components" / "console" / "infra" / "main.tf").read_text()
        assert "postgres:16" in (dest / "README.md").read_text()
        assert not (dest / ".cursor" / "rules" / "worker.mdc").exists()

        status_res = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "odlc.py"), "status", str(dest), "--check"],
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
    env:
      MAIL_TO: ops@opptra.com,finance@opptra.com
      FRESHDESK_DOMAIN: https://opptra.freshdesk.com
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
            cmd = [sys.executable, str(ROOT / "scripts" / "odlc.py"), phase, str(manifest_path)]
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
        example = (dest / ".env.example").read_text()
        assert "MAIL_TO=ops@opptra.com,finance@opptra.com" in example
        assert "FRESHDESK_DOMAIN=https://opptra.freshdesk.com" in example
        assert 'MAIL_TO = "ops@opptra.com,finance@opptra.com"' in main_tf
        assert 'FRESHDESK_DOMAIN = "https://opptra.freshdesk.com"' in main_tf
        component_manifest = (comp_dir / "service.yaml").read_text()
        assert "MAIL_TO:" in component_manifest
        assert "ops@opptra.com,finance@opptra.com" in component_manifest
        copied_check = dest / "scripts" / "check_secret_versions.py"
        assert copied_check.is_file()
        assert copied_check.read_text() == (ROOT / "scripts" / "check_secret_versions.py").read_text()
        assert (dest / "scripts" / "render_tfvars.py").is_file()
        assert (dest / "scripts" / "yaml_subset.py").is_file()
        copied_summary = dest / "scripts" / "summarize_plan.py"
        assert copied_summary.is_file()
        assert copied_summary.read_text() == (ROOT / "scripts" / "summarize_plan.py").read_text()
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
            [sys.executable, str(ROOT / "scripts" / "odlc.py"), "status", str(dest), "--json", "--check"],
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
            [sys.executable, str(ROOT / "scripts" / "odlc.py"), "doctor", str(dest)],
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
                str(ROOT / "scripts" / "odlc.py"),
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
        assert "docker build" not in (repo / "Makefile").read_text()

        # status --check passes with zero ci_path_errors
        res = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "odlc.py"), "status", str(repo), "--check"],
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
            [sys.executable, str(ROOT / "scripts" / "odlc.py"), "discover-infra", str(repo), "--table"],
            check=True,
            capture_output=True,
            text=True,
        )
        assert "Terraform Adoption Scorecard" in disc_res.stdout
        assert "pm-dashboard" in disc_res.stdout

        imp_res = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "odlc.py"),
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


def test_non_destructive_init_runtime_and_infra_preserves_imports_and_plans() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "app"
        comp_dir = dest / "components" / "console"
        comp_dir.mkdir(parents=True)
        (comp_dir / "MIGRATION_PLAN.md").write_text("# Keep this plan\n")

        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "odlc.py"),
                "init-runtime",
                str(FIXTURE),
                str(dest),
                "--overwrite",
            ],
            check=True,
        )
        assert (comp_dir / "MIGRATION_PLAN.md").read_text() == "# Keep this plan\n"

        infra_dir = comp_dir / "infra"
        infra_dir.mkdir(parents=True, exist_ok=True)
        (infra_dir / "imports.tf").write_text("# user confirmed imports\n")
        (infra_dir / "imports.tf.example").write_text("# generated import examples\n")

        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "odlc.py"),
                "sync-infra",
                str(FIXTURE),
                str(dest),
            ],
            check=True,
        )
        assert (infra_dir / "imports.tf").read_text() == "# user confirmed imports\n"
        assert (infra_dir / "imports.tf.example").read_text() == "# generated import examples\n"
        assert (infra_dir / "main.tf").is_file()


def test_brownfield_secret_map_legacy_service_and_propose_manifest() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "legacy-analytics"
        repo.mkdir(parents=True)
        (repo / "Dockerfile").write_text(
            'FROM python:3.12-slim\nCMD ["uvicorn", "app.main:app", "--port", "8080"]\n'
        )
        (repo / ".env.example").write_text(
            "BATCH_LIMIT=100\nSLACK_WEBHOOK_TOKEN=replace-me\n"
        )
        (repo / "cloudbuild.yaml").write_text(
            "substitutions:\n"
            "  _REGION: asia-southeast1\n"
            "  _PROJECT_ID: opptra-analytics-prod\n"
            "steps:\n"
            "  - name: gcr.io/google.com/cloudsdktool/cloud-sdk\n"
            "    args:\n"
            "      - gcloud\n"
            "      - run\n"
            "      - deploy\n"
            "      - analytics-portal\n"
            "      - --region=${_REGION}\n"
            "      - --set-secrets=DASHBOARD_TOKEN=legacy-dashboard-token:latest\n"
        )

        prop_res = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "odlc.py"),
                "discover-infra",
                str(repo),
                "--propose-manifest",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        manifest_path = repo / "service.yaml"
        manifest_path.write_text(prop_res.stdout)

        check_res = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "odlc.py"), "check", str(manifest_path)],
            check=False,
            capture_output=True,
            text=True,
        )
        assert check_res.returncode == 0, check_res.stderr

        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "odlc.py"),
                "sync-infra",
                str(manifest_path),
                str(repo),
            ],
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "odlc.py"),
                "discover-infra",
                str(repo),
                "--write-imports",
                str(manifest_path),
            ],
            check=True,
        )

        main_tf = (repo / "infra" / "main.tf").read_text()
        imports_tf = (repo / "infra" / "imports.tf.example").read_text()
        assert '"legacy-dashboard-token"' in main_tf
        assert 'module.secrets.by_id["legacy-dashboard-token"]' in main_tf
        assert "projects/opptra-analytics-prod/secrets/legacy-dashboard-token" in imports_tf
        assert "projects/opptra-analytics-prod/locations/asia-southeast1/services/analytics-portal" in imports_tf

        status_res = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "odlc.py"), "status", str(repo), "--json", "--check"],
            check=True,
            capture_output=True,
            text=True,
        )
        report = json.loads(status_res.stdout)
        assert report["aligned"] is True
        sec_16 = [s for s in report["sections_14"] if s["id"] == 16][0]
        assert sec_16["status"] == "Up to the mark"


def test_yaml_subset_multiline_and_floats() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from yaml_subset import parse

    doc = parse(
        "name: demo\n"
        "threshold: 0.85\n"
        "purpose: |\n"
        "  Line one of purpose.\n"
        "  Line two of purpose.\n"
    )
    assert doc["name"] == "demo"
    assert doc["threshold"] == 0.85
    assert doc["purpose"] == "Line one of purpose.\nLine two of purpose.\n"


def test_runtime_sdk_secret_underscores_secret_map_logging_extra_and_redaction(monkeypatch) -> None:
    common_dir = ROOT / "skeletons" / "_common" / "backend"
    sys.path.insert(0, str(common_dir))
    from app.config import resolve_secret_name
    from app.logging import (
        JsonFormatter,
        register_secret_for_redaction,
        set_trace_id,
    )
    import logging

    monkeypatch.setenv("RESOURCE_PREFIX", "cx")
    # Underscores are preserved to match Terraform secret_resource_id
    assert (
        resolve_secret_name("FRESHDESK_CUSTOMERCARE_API_KEY")
        == "cx-FRESHDESK_CUSTOMERCARE_API_KEY"
    )
    # Brownfield secret_map override is respected
    monkeypatch.setenv("SECRET_MAP_DASHBOARD_TOKEN", "legacy-dashboard-token")
    assert resolve_secret_name("DASHBOARD_TOKEN") == "legacy-dashboard-token"

    # Structured JSON logging preserves extra fields, trace_id, and redacts secrets/tokens
    set_trace_id("trace-xyz-123")
    register_secret_for_redaction("super-sensitive-secret-value")
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="job",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Failed calling upstream with Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9 and key=super-sensitive-secret-value",
        args=(),
        exc_info=None,
    )
    record.job = "report-daily"
    record.run_id = "run987654"
    rendered = json.loads(formatter.format(record))
    assert rendered["job"] == "report-daily"
    assert rendered["run_id"] == "run987654"
    assert rendered["trace_id"] == "trace-xyz-123"
    assert "timestamp" in rendered
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in rendered["message"]
    assert "super-sensitive-secret-value" not in rendered["message"]
    assert "[REDACTED]" in rendered["message"]


def test_bigquery_module_extra_roles_custom_keep_tf_and_sdlc_next() -> None:
    manifest_yaml = """name: ads-intelligence
prefix: ads
purpose: BigQuery and Vertex AI intelligence service.
prod_project: opptra-applications
region: asia-south1
components:
  - name: api
    archetype: cloud-run-service
    path: .
    auth: iap
    database: bigquery
    bigquery_datasets: [ads_raw, ads_mart]
    extra_roles: [roles/aiplatform.user]
    custom_terraform: true
    parts: [api]
    secrets: [GEMINI_API_KEY]
"""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "ads-intelligence"
        repo.mkdir(parents=True)
        (repo / "deploy.sh").write_text(
            "gcloud pubsub topics create ads-events\n"
            "gcloud projects add-iam-policy-binding opptra-applications --role=roles/aiplatform.user\n"
        )
        manifest_path = repo / "service.yaml"
        manifest_path.write_text(manifest_yaml)

        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "odlc.py"), "all", str(manifest_path), str(repo)],
            check=True,
        )

        main_tf = (repo / "infra" / "main.tf").read_text()
        assert 'module "bigquery"' in main_tf
        assert '"ads_raw"' in main_tf
        assert '"ads_mart"' in main_tf
        assert 'resource "google_project_iam_member" "extra_roles"' in main_tf
        assert '"roles/aiplatform.user"' in main_tf
        assert (repo / "infra" / "modules" / "bigquery" / "main.tf").is_file()
        assert (repo / "infra" / "custom.keep.tf").is_file()

        # Check fixture postgres migrate job in test_generate_selects_capabilities style
        pg_dest = Path(tmp) / "pg-app"
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "generate.py"), str(FIXTURE), str(pg_dest)],
            check=True,
        )
        pg_main_tf = (pg_dest / "components" / "console" / "infra" / "main.tf").read_text()
        assert 'resource "google_cloud_run_v2_job" "migrate"' in pg_main_tf
        assert '"${var.name}-migrate"' in pg_main_tf

        # Test discover-infra writes discovered pubsub topic into custom.keep.tf
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "odlc.py"),
                "discover-infra",
                str(repo),
                "--write-imports",
                str(manifest_path),
            ],
            check=True,
        )
        assert 'resource "google_pubsub_topic" "ads_events"' in (
            repo / "infra" / "custom.keep.tf"
        ).read_text()

        # Test odlc next and odlc secrets
        next_res = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "odlc.py"), "next", str(repo), "--json"],
            check=True,
            capture_output=True,
            text=True,
        )
        next_data = json.loads(next_res.stdout)
        assert next_data["aligned"] is True

        sec_res = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "odlc.py"), "secrets", str(repo), "--json"],
            check=True,
            capture_output=True,
            text=True,
        )
        sec_data = json.loads(sec_res.stdout)
        assert sec_data["secrets"][0]["secret_id"] == "ads-GEMINI_API_KEY"


def test_connect_preexisting_postgres_bigquery_bucket_and_shared_secrets() -> None:
    manifest_yaml = """name: finance-reconciler
prefix: fin
purpose: Reconcile invoices against pre-existing Cloud SQL, cross-project BigQuery, shared bucket, and shared secrets.
prod_project: opptra-applications
region: asia-south1
components:
  - name: api
    archetype: cloud-run-service
    path: .
    auth: iap
    database: postgres
    postgres_instance: opptra-applications:asia-south1:shared-erp-db
    postgres_secret: shared-erp-db-password
    bigquery: true
    bigquery_project: opptra-data-warehouse
    bigquery_datasets: [billing_mart, opptra-raw.invoices_raw]
    bucket: private
    existing_bucket: opptra-shared-invoices
    parts: [api]
    secrets: [APP_SIGNING_KEY]
    existing_secrets: [SHARED_SLACK_TOKEN]
    secret_map:
      SHARED_SLACK_TOKEN: corp-slack-bot-token
"""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "finance-reconciler"
        repo.mkdir(parents=True)
        manifest_path = repo / "service.yaml"
        manifest_path.write_text(manifest_yaml)

        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "odlc.py"), "all", str(manifest_path), str(repo)],
            check=True,
        )

        main_tf = (repo / "infra" / "main.tf").read_text()
        # 1. Pre-existing Postgres: does NOT create module "db", mounts existing Cloud SQL socket & secret
        assert 'module "db"' not in main_tf
        assert 'cloud_sql_instance = "opptra-applications:asia-south1:shared-erp-db"' in main_tf
        assert 'db_secret_id       = "shared-erp-db-password"' in main_tf
        assert 'secret_id = "shared-erp-db-password"' in main_tf

        # 2. Pre-existing BigQuery: passes dataset_project and datasets, sets BIGQUERY_PROJECT & BIGQUERY_DATASET
        assert 'module "bigquery"' in main_tf
        assert 'dataset_project         = "opptra-data-warehouse"' in main_tf
        assert '"billing_mart"' in main_tf
        assert '"opptra-raw.invoices_raw"' in main_tf
        assert 'BIGQUERY_PROJECT = "opptra-data-warehouse"' in main_tf
        assert 'BIGQUERY_DATASET = "billing_mart"' in main_tf

        # 3. Pre-existing Bucket: does NOT create module "bucket", grants IAM on existing bucket
        assert 'module "bucket"' not in main_tf
        assert 'resource "google_storage_bucket_iam_member" "existing_bucket"' in main_tf
        assert 'bucket = "opptra-shared-invoices"' in main_tf
        assert 'gcs_bucket_name = "opptra-shared-invoices"' in main_tf

        # 4. Pre-existing Secrets: module "secrets" only creates shell for APP_SIGNING_KEY, not SHARED_SLACK_TOKEN
        secrets_block = main_tf.split('module "secrets"')[1]
        assert '"fin-APP_SIGNING_KEY"' in secrets_block
        assert "corp-slack-bot-token" not in secrets_block
        # But module "service" mounts both (app-owned via module.secrets.by_id and existing as direct string)
        assert 'module.secrets.by_id["fin-APP_SIGNING_KEY"]' in main_tf
        assert '"corp-slack-bot-token",' in main_tf

        # Verify check_secret_versions.py detects both app-owned and pre-existing mounted secret IDs
        sys.path.insert(0, str(ROOT / "scripts"))
        from check_secret_versions import mounted_secret_ids

        mounted = mounted_secret_ids(main_tf)
        assert "fin-APP_SIGNING_KEY" in mounted
        assert "corp-slack-bot-token" in mounted

        # Verify .env.example has pre-existing BigQuery & Bucket defaults
        env_example = (repo / ".env.example").read_text()
        assert "BIGQUERY_PROJECT=opptra-data-warehouse" in env_example
        assert "BIGQUERY_DATASET=billing_mart" in env_example
        assert "GCS_BUCKET_NAME=opptra-shared-invoices" in env_example

        # Verify 17-point scorecard passes 100%
        status_res = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "odlc.py"), "status", str(repo), "--check"],
            check=False,
            capture_output=True,
            text=True,
        )
        assert status_res.returncode == 0, status_res.stderr

        # Verify discover-infra --propose-manifest sets postgres_external vs postgres_instance
        ext_pg_repo = Path(tmp) / "ext-pg-app"
        ext_pg_repo.mkdir(parents=True)
        (ext_pg_repo / "requirements.txt").write_text("sqlalchemy>=2.0\npsycopg[binary]>=3.2\n")
        (ext_pg_repo / "deploy.sh").write_text(
            "gcloud run deploy ext-pg-app --region asia-south1 --set-secrets=DATABASE_URL=neon-db-url:latest\n"
        )
        prop_ext = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "odlc.py"), "discover-infra", str(ext_pg_repo), "--propose-manifest"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        assert "postgres_external: true" in prop_ext
        assert "postgres_instance:" not in prop_ext

        csql_repo = Path(tmp) / "csql-pg-app"
        csql_repo.mkdir(parents=True)
        (csql_repo / "requirements.txt").write_text("sqlalchemy>=2.0\n")
        (csql_repo / "deploy.sh").write_text(
            "gcloud run deploy csql-pg-app --region asia-south1 "
            "--add-cloudsql-instances=opptra-applications:asia-south1:existing-pg\n"
        )
        prop_csql = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "odlc.py"), "discover-infra", str(csql_repo), "--propose-manifest"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        assert "postgres_instance: \"opptra-applications:asia-south1:existing-pg\"" in prop_csql
        assert "postgres_external:" not in prop_csql


def test_docker_context_is_passed_only_when_set() -> None:
    manifest_yaml = """name: image-root
purpose: Build one job image from the repository root.
prod_project: opptra-applications
region: asia-south1
components:
  - name: jobs
    archetype: scheduled-jobs
    auth: none
    parts: [job]
    docker_context: .
    dockerfile: backend/Dockerfile
    jobs:
      - name: tick
        command: python -m app.jobs.tick
  - name: plain
    archetype: scheduled-jobs
    auth: none
    parts: [job]
    jobs:
      - name: nightly
        command: python -m app.jobs.nightly
"""
    with tempfile.TemporaryDirectory() as tmp:
        manifest = Path(tmp) / "service.yaml"
        manifest.write_text(manifest_yaml)
        dest = Path(tmp) / "app"
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "generate.py"), str(manifest), str(dest)],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        deploy = (dest / ".github" / "workflows" / "deploy-staging.yml").read_text()
        jobs_block = deploy.split("deploy-job-jobs:")[1].split("deploy-job-plain:")[0]
        plain_block = deploy.split("deploy-job-plain:")[1]
        assert "docker_context: ." in jobs_block
        assert "dockerfile: backend/Dockerfile" in jobs_block
        assert "docker_context:" not in plain_block
        assert "dockerfile:" not in plain_block
        component = (dest / "components" / "jobs" / "service.yaml").read_text()
        assert 'docker_context: "."' in component
        assert 'dockerfile: "backend/Dockerfile"' in component
        makefile = (dest / "Makefile").read_text()
        assert "docker build -f 'backend/Dockerfile' '.'" in makefile
        assert "terraform init -backend=false" in makefile


def test_scheduled_job_mounts_secret_map_ids() -> None:
    manifest_yaml = """name: inventory-optimizer
prefix: inventory-optimizer
purpose: Jobs read the secret ids named in secret_map.
prod_project: opptra-applications
region: asia-south1
components:
  - name: jobs
    archetype: scheduled-jobs
    auth: none
    parts: [job]
    secrets: [DATABASE_URL, ANTHROPIC_API_KEY]
    secret_map:
      DATABASE_URL: inventory-optimizer-database-url
      ANTHROPIC_API_KEY: FLOW_AGENT_KEY
    jobs:
      - name: tick
        command: python -m app.approvals tick
        secrets: [DATABASE_URL]
      - name: agentic
        command: python -m app.agentic work
        secrets: [DATABASE_URL, ANTHROPIC_API_KEY]
"""
    with tempfile.TemporaryDirectory() as tmp:
        manifest = Path(tmp) / "service.yaml"
        manifest.write_text(manifest_yaml)
        dest = Path(tmp) / "app"
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "generate.py"), str(manifest), str(dest)],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        infra = dest / "components" / "jobs" / "infra"
        main_tf = (infra / "main.tf").read_text()
        module_tf = (infra / "modules" / "cloud-run-job" / "main.tf").read_text()
        assert 'secrets         = ["DATABASE_URL"]' in main_tf
        assert 'secrets         = ["DATABASE_URL", "ANTHROPIC_API_KEY"]' in main_tf
        assert 'DATABASE_URL = "inventory-optimizer-database-url"' in main_tf
        assert 'ANTHROPIC_API_KEY = "FLOW_AGENT_KEY"' in main_tf
        assert 'module.secrets.by_id["inventory-optimizer-database-url"]' in main_tf
        assert 'module.secrets.by_id["FLOW_AGENT_KEY"]' in main_tf
        assert "inventory-optimizer-DATABASE_URL" not in main_tf
        assert "inventory-optimizer-ANTHROPIC_API_KEY" not in main_tf
        assert "lookup(var.secret_map, env.value," in module_tf


def test_docker_context_must_be_a_pair_inside_the_repo() -> None:
    base = """name: image-root
purpose: Build one job image from the repository root.
prod_project: opptra-applications
region: asia-south1
components:
  - name: jobs
    archetype: scheduled-jobs
    auth: none
    parts: [job]
    {extra}
    jobs:
      - name: tick
        command: python -m app.jobs.tick
"""
    for extra, expected in (
        ("docker_context: .", "set docker_context and dockerfile together"),
        ("dockerfile: ../Dockerfile", "dockerfile must be a path inside the repo"),
        (
            "docker_context: backend\n    dockerfile: Dockerfile",
            "dockerfile must be inside docker_context",
        ),
    ):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "service.yaml"
            path.write_text(base.format(extra=extra))
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "check_manifest.py"), str(path)],
                check=False,
                capture_output=True,
                text=True,
            )
            assert result.returncode == 1
            assert expected in result.stderr


def test_discover_proposes_the_dockerfile_the_repo_already_builds() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "jobs-repo"
        (repo / "backend").mkdir(parents=True)
        (repo / "backend" / "Dockerfile").write_text(
            "FROM python:3.12-slim\n"
            "COPY app /app\n"
            'CMD ["python", "-m", "app.jobs.tick"]\n'
        )
        (repo / "backend" / "app").mkdir()
        (repo / "deploy.sh").write_text(
            "gcloud run jobs deploy tick --region asia-south1 "
            "--command=python --args=-m,app.tick\n"
            "docker build -f backend/Dockerfile -t tick .\n"
        )
        proposed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "odlc.py"),
                "discover-infra",
                str(repo),
                "--propose-manifest",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        assert "docker_context: ." in proposed
        assert "dockerfile: backend/Dockerfile" in proposed
        assert "command: python -m app.tick" in proposed


def test_status_fails_when_the_declared_dockerfile_is_missing() -> None:
    manifest_yaml = """name: image-root
purpose: Build one job image from the repository root.
prod_project: opptra-applications
region: asia-south1
components:
  - name: jobs
    archetype: scheduled-jobs
    auth: none
    parts: [job]
    path: .
    docker_context: .
    dockerfile: backend/Dockerfile
    jobs:
      - name: tick
        command: python -m app.jobs.tick
"""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "app"
        repo.mkdir()
        (repo / "service.yaml").write_text(manifest_yaml)
        (repo / ".github" / "workflows").mkdir(parents=True)
        (repo / ".github" / "workflows" / "deploy-staging.yml").write_text("name: deploy\n")
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "odlc.py"), "status", str(repo), "--check"],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "dockerfile backend/Dockerfile is not a file" in result.stderr


def test_status_notes_a_copy_outside_the_context() -> None:
    manifest_yaml = """name: image-root
purpose: Build one job image from the repository root.
prod_project: opptra-applications
region: asia-south1
components:
  - name: jobs
    archetype: scheduled-jobs
    auth: none
    parts: [job]
    path: backend
    docker_context: backend
    dockerfile: backend/Dockerfile
    jobs:
      - name: tick
        command: python -m app.jobs.tick
"""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "app"
        (repo / "backend").mkdir(parents=True)
        (repo / "service.yaml").write_text(manifest_yaml)
        (repo / "backend" / "Dockerfile").write_text("FROM python:3.12-slim\nCOPY ../shared /shared\n")
        (repo / ".github" / "workflows").mkdir(parents=True)
        (repo / ".github" / "workflows" / "ci.yml").write_text("name: ci\n")
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "odlc.py"),
                "status",
                str(repo),
                "--json",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        report = json.loads(result.stdout)
        assert any("COPY ../shared" in note for note in report["image_notes"])


def test_deploy_workflows_do_not_export_docker_context() -> None:
    """DOCKER_CONTEXT is reserved by the Docker CLI. A value of . fails the build."""
    workflows = ROOT / ".github" / "workflows"
    for name in ("deploy-job.yml", "deploy-cloud-run.yml", "deploy-worker.yml"):
        text = (workflows / name).read_text()
        assert "BUILD_CONTEXT: ${{ inputs.docker_context }}" in text
        assert "DOCKER_CONTEXT" not in text
        assert "$GITHUB_WORKSPACE/${BUILD_CONTEXT}" in text
