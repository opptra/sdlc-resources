"""The plan comment lists changed resources and hides the refresh log."""

import json
import sys
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from summarize_plan import artifact_name, main, summarize  # noqa: E402


def _resource(address, actions, **change):
    body = {
        "actions": actions,
        "before": change.get("before"),
        "after": change.get("after"),
        "before_sensitive": change.get("before_sensitive", False),
        "after_sensitive": change.get("after_sensitive", False),
        "after_unknown": change.get("after_unknown", False),
    }
    if "replace_paths" in change:
        body["replace_paths"] = change["replace_paths"]
    return {"address": address, "mode": "managed", "change": body}


def _comment(plan, **kwargs) -> str:
    options = {
        "environment": "staging",
        "project": "opptra-staging",
        "component": "apps/billing",
        "artifact": "terraform-plan-staging-apps-billing",
    }
    options.update(kwargs)
    return summarize(plan, **options)


def test_noop_plan_says_no_changes_and_does_not_say_destroy() -> None:
    plan = {
        "resource_changes": [
            _resource(
                "module.service.google_cloud_run_v2_service.app",
                ["no-op"],
                before={"image": "same"},
                after={"image": "same"},
            ),
            {
                "address": "data.google_project.current",
                "mode": "data",
                "change": {"actions": ["read"], "before": None, "after": {"id": "opptra-staging"}},
            },
        ]
    }
    text = _comment(plan)
    assert "No changes." in text
    assert "Add " not in text
    assert "destroy" not in text.lower()
    assert "<!-- terraform-plan: staging:apps/billing -->" in text
    assert "### Terraform plan · staging · apps/billing" in text
    assert "Plan only. opptra-staging is unchanged." in text


def test_update_lists_only_attributes_that_differ() -> None:
    plan = {
        "resource_changes": [
            _resource(
                "module.service.google_cloud_run_v2_service.app",
                ["update"],
                before={
                    "template": [{"containers": [{"image": "billing:9f3ab12", "env": [{"name": "APP_ENV"}]}]}],
                    "scaling": {"max_instance_count": 10},
                },
                after={
                    "template": [{"containers": [{"image": "billing:c41e88d", "env": [{"name": "APP_ENV"}]}]}],
                    "scaling": {"max_instance_count": 20},
                },
            )
        ]
    }
    text = _comment(plan)
    assert "Add 0 · Change 1" in text
    assert "Replace" not in text
    assert "destroy" not in text.lower()
    assert "template[0].containers[0].image: billing:9f3ab12 → billing:c41e88d" in text
    assert "scaling.max_instance_count: 10 → 20" in text
    assert "APP_ENV" not in text


def test_sensitive_values_are_redacted() -> None:
    plan = {
        "resource_changes": [
            _resource(
                "module.service.google_cloud_run_v2_service.app",
                ["update"],
                before={"token": "super-secret-value", "image": "sha-old"},
                after={"token": "next-secret-value", "image": "sha-new"},
                before_sensitive={"token": True, "image": False},
                after_sensitive={"token": True, "image": False},
            )
        ]
    }
    text = _comment(plan)
    assert "super-secret-value" not in text
    assert "next-secret-value" not in text
    assert "(sensitive value)" in text
    assert "sha-old → sha-new" in text


def test_one_sided_sensitive_redacts_both_values() -> None:
    plan = {
        "resource_changes": [
            _resource(
                "module.service.google_cloud_run_v2_service.app",
                ["update"],
                before={"token": "old-secret"},
                after={"token": "new-secret"},
                before_sensitive={"token": False},
                after_sensitive={"token": True},
            )
        ]
    }
    text = _comment(plan)
    assert "old-secret" not in text
    assert "new-secret" not in text
    assert "(sensitive value)" in text


def test_unknown_after_apply_stays_unknown() -> None:
    plan = {
        "resource_changes": [
            _resource(
                "module.service.google_cloud_run_v2_service.app",
                ["update"],
                before={"image": "sha-old"},
                after={"image": None},
                after_unknown={"image": True},
            )
        ]
    }
    text = _comment(plan)
    assert "image: sha-old → (known after apply)" in text


def test_create_lists_the_address_only() -> None:
    plan = {
        "resource_changes": [
            _resource(
                "module.service.google_cloud_run_v2_service.app",
                ["create"],
                before=None,
                after={"name": "billing", "image": "billing:c41e88d"},
            )
        ]
    }
    text = _comment(plan)
    assert "Add 1 · Change 0" in text
    assert "- module.service.google_cloud_run_v2_service.app" in text
    assert "c41e88d" not in text


def test_destroy_uses_terraform_phrase() -> None:
    plan = {
        "resource_changes": [
            _resource(
                "module.uploads.google_storage_bucket.uploads",
                ["delete"],
                before={"name": "uploads"},
                after=None,
            )
        ]
    }
    text = _comment(plan)
    assert "Add 0 · Change 0 · Destroy 1" in text
    assert "module.uploads.google_storage_bucket.uploads will be destroyed" in text
    assert text.index("Will be destroyed") < text.index("Full plan:")


def test_replace_is_called_out_and_contains_destroy() -> None:
    plan = {
        "resource_changes": [
            _resource(
                "module.service.google_cloud_run_v2_service.app",
                ["delete", "create"],
                before={"template": [{"containers": [{"image": "old", "cpu": "1"}]}]},
                after={"template": [{"containers": [{"image": "new", "cpu": "2"}]}]},
                replace_paths=[["template", 0, "containers", 0, "image"]],
            )
        ]
    }
    text = _comment(plan)
    assert "Replace 1" in text
    assert "must be replaced" in text
    assert "destroys the existing resource" in text
    image = text.index("template[0].containers[0].image")
    cpu = text.index("template[0].containers[0].cpu")
    assert image < cpu
    assert "old → new" in text


def test_long_attribute_lists_are_capped() -> None:
    before = {f"k{i:02d}": "old" for i in range(13)}
    after = {f"k{i:02d}": "new" for i in range(13)}
    plan = {"resource_changes": [_resource("module.service.google_cloud_run_v2_service.app", ["update"], before=before, after=after)]}
    text = _comment(plan)
    assert "k00: old → new" in text
    assert "k11: old → new" in text
    assert "k12" not in text
    assert "and 1 more" in text


def test_run_url_is_linked() -> None:
    text = _comment(
        {"resource_changes": []},
        run_url="https://github.com/opptra/billing/actions/runs/15",
    )
    assert "[this run](https://github.com/opptra/billing/actions/runs/15)" in text


def test_artifact_name_sanitizes_the_component_path() -> None:
    assert artifact_name("staging", "apps/billing") == "terraform-plan-staging-apps-billing"
    assert artifact_name("prod", ".") == "terraform-plan-prod-repo"
    assert artifact_name("staging", "") == "terraform-plan-staging-repo"


def test_repo_root_component_is_labeled_repo() -> None:
    text = _comment({"resource_changes": []}, component=".")
    assert "### Terraform plan · staging · repo" in text
    assert "<!-- terraform-plan: staging:. -->" in text


def test_cli_writes_the_comment_and_prints_the_artifact_name() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        plan_path = Path(tmp) / "plan.json"
        plan_path.write_text(json.dumps({"resource_changes": []}))
        out = Path(tmp) / "comment.md"
        code = main(
            [
                "--plan",
                str(plan_path),
                "--environment",
                "staging",
                "--project",
                "opptra-staging",
                "--component",
                "apps/billing",
                "--artifact",
                "terraform-plan-staging-apps-billing",
                "--out",
                str(out),
            ]
        )
        assert code == 0
        assert "No changes." in out.read_text()

    buffer = StringIO()
    with redirect_stdout(buffer):
        code = main(
            [
                "--print-artifact-name",
                "--environment",
                "prod",
                "--component",
                "apps/billing",
            ]
        )
    assert code == 0
    assert buffer.getvalue().strip() == "terraform-plan-prod-apps-billing"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("ok")
