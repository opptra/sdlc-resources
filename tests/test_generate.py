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
        assert (dest / "components" / "console" / "frontend" / "package.json").is_file()
        assert (dest / "components" / "nightly" / "backend" / "tests" / "test_run.py").is_file()
        assert (dest / "CLAUDE.md").is_file()
        agents = (dest / "AGENTS.md").read_text()
        assert "sdlc-rules-version: 1" in agents
        assert "feat: <ticket-id>" in agents
        assert (dest / ".cursor" / "rules" / "react.mdc").is_file()
        assert not (dest / ".cursor" / "rules" / "worker.mdc").exists()
