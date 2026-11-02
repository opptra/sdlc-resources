#!/usr/bin/env python3
"""Write a short pull-request comment from a Terraform JSON plan.

The plan workflow runs ``terraform show -json`` and passes that file here.
The comment lists resources to add, change, replace, or destroy, and only
the attributes that differ. A later run updates the same comment: the first
line is a hidden marker the workflow searches for.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

MAX_ATTRS = 12
MAX_VALUE = 72
ONE_LINE_LIMIT = 100

_ABSENT = object()


def artifact_name(environment: str, component: str) -> str:
    """Return a GitHub artifact name for this plan."""
    slug = _component_slug(component)
    return f"terraform-plan-{environment}-{slug}"


def comment_marker(environment: str, component: str) -> str:
    """Return the hidden marker that identifies this component's comment."""
    return f"<!-- terraform-plan: {environment}:{component} -->"


def summarize(
    plan: dict,
    *,
    environment: str,
    project: str,
    component: str,
    artifact: str,
    run_url: str = "",
) -> str:
    """Return the pull-request comment for one saved plan."""
    adds: list[dict] = []
    changes: list[dict] = []
    replaces: list[dict] = []
    destroys: list[dict] = []
    for resource in plan.get("resource_changes") or []:
        if resource.get("mode") != "managed":
            continue
        kind = _classify((resource.get("change") or {}).get("actions") or [])
        if kind == "add":
            adds.append(resource)
        elif kind == "change":
            changes.append(resource)
        elif kind == "replace":
            replaces.append(resource)
        elif kind == "destroy":
            destroys.append(resource)

    label = _display_component(component)
    lines = [
        comment_marker(environment, component),
        f"### Terraform plan · {environment} · {label}",
        f"Plan only. {project} is unchanged.",
        "",
    ]
    if not adds and not changes and not replaces and not destroys:
        lines.append("No changes.")
    else:
        counts = [f"Add {len(adds)}", f"Change {len(changes)}"]
        if replaces:
            counts.append(f"Replace {len(replaces)}")
        if destroys:
            counts.append(f"Destroy {len(destroys)}")
        lines.append(" · ".join(counts))
        lines.append("")
        blocks = []
        if destroys:
            blocks.append(_destroy_block(destroys))
        if replaces:
            blocks.append(_replace_block(replaces))
        if adds:
            blocks.append(_address_block("Add", adds))
        if changes:
            blocks.append(_change_block(changes))
        lines.append("\n\n".join(blocks))
    lines.append("")
    lines.append(_footer(artifact, run_url))
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--component", required=True)
    parser.add_argument("--print-artifact-name", action="store_true")
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--project", default="")
    parser.add_argument("--artifact", default="")
    parser.add_argument("--run-url", default="")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    if args.print_artifact_name:
        print(artifact_name(args.environment, args.component))
        return 0
    if args.plan is None or args.out is None or not args.project or not args.artifact:
        parser.error("--plan, --project, --artifact, and --out are required")

    try:
        payload = json.loads(args.plan.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"plan JSON could not be read: {exc}", file=sys.stderr)
        return 1
    if not isinstance(payload, dict):
        print("plan JSON must be an object", file=sys.stderr)
        return 1
    text = summarize(
        payload,
        environment=args.environment,
        project=args.project,
        component=args.component,
        artifact=args.artifact,
        run_url=args.run_url,
    )
    args.out.write_text(text)
    return 0


def _classify(actions: list[str]) -> str:
    kinds = set(actions)
    if not kinds or kinds <= {"no-op", "read"}:
        return "skip"
    if "delete" in kinds and "create" in kinds:
        return "replace"
    if "delete" in kinds:
        return "destroy"
    if "create" in kinds:
        return "add"
    return "change"


def _destroy_block(resources: list[dict]) -> str:
    lines = ["Will be destroyed"]
    for resource in resources:
        lines.append(f"- {resource['address']} will be destroyed")
    return "\n".join(lines)


def _replace_block(resources: list[dict]) -> str:
    lines = [
        "Must be replaced",
        "Each replace destroys the existing resource and creates a new one.",
    ]
    for resource in resources:
        lines.append(f"- {resource['address']} must be replaced")
        lines.extend(_attribute_lines(resource))
    return "\n".join(lines)


def _address_block(title: str, resources: list[dict]) -> str:
    lines = [title]
    for resource in resources:
        lines.append(f"- {resource['address']}")
    return "\n".join(lines)


def _change_block(resources: list[dict]) -> str:
    lines = ["Change"]
    for resource in resources:
        lines.append(f"- {resource['address']}")
        lines.extend(_attribute_lines(resource))
    return "\n".join(lines)


def _attribute_lines(resource: dict) -> list[str]:
    change = resource.get("change") or {}
    leaves = _leaves(
        change.get("before"),
        change.get("after"),
        change.get("before_sensitive", False),
        change.get("after_sensitive", False),
        change.get("after_unknown", False),
        "",
    )
    preferred = [_format_path(path) for path in change.get("replace_paths") or []]
    rank = {path: index for index, path in enumerate(preferred)}
    forced = [item for item in leaves if item[0] in rank]
    forced.sort(key=lambda item: rank[item[0]])
    leaves = forced + [item for item in leaves if item[0] not in rank]
    shown = leaves[:MAX_ATTRS]
    lines: list[str] = []
    for path, before, after in shown:
        lines.extend(_format_leaf(path, before, after))
    hidden = len(leaves) - len(shown)
    if hidden:
        lines.append(f"  - and {hidden} more")
    return lines


def _leaves(before, after, before_sensitive, after_sensitive, after_unknown, path: str):
    if _flag(before_sensitive) or _flag(after_sensitive):
        if before == after and not _flag(after_unknown):
            return []
        after_text = "(known after apply)" if _flag(after_unknown) else "(sensitive value)"
        return [(path, "(sensitive value)", after_text)]
    if _flag(after_unknown):
        return [(path, _render(before), "(known after apply)")]
    if isinstance(before, dict) and isinstance(after, dict):
        return _walk_dict(before, after, before_sensitive, after_sensitive, after_unknown, path)
    if isinstance(before, list) and isinstance(after, list):
        return _walk_list(before, after, before_sensitive, after_sensitive, after_unknown, path)
    if before == after:
        return []
    return [(path, _render(before), _render(after))]


def _walk_dict(before, after, before_sensitive, after_sensitive, after_unknown, path: str):
    before_sensitive = before_sensitive if isinstance(before_sensitive, dict) else {}
    after_sensitive = after_sensitive if isinstance(after_sensitive, dict) else {}
    after_unknown = after_unknown if isinstance(after_unknown, dict) else {}
    found = []
    for key in list(dict.fromkeys([*before.keys(), *after.keys()])):
        child = f"{path}.{key}" if path else str(key)
        found.extend(
            _leaves(
                before.get(key, _ABSENT),
                after.get(key, _ABSENT),
                before_sensitive.get(key, False),
                after_sensitive.get(key, False),
                after_unknown.get(key, False),
                child,
            )
        )
    return found


def _walk_list(before, after, before_sensitive, after_sensitive, after_unknown, path: str):
    found = []
    for index in range(max(len(before), len(after))):
        child = f"{path}[{index}]"
        found.extend(
            _leaves(
                before[index] if index < len(before) else _ABSENT,
                after[index] if index < len(after) else _ABSENT,
                _at(before_sensitive, index),
                _at(after_sensitive, index),
                _at(after_unknown, index),
                child,
            )
        )
    return found


def _at(value, index: int):
    if isinstance(value, list) and index < len(value):
        return value[index]
    return False


def _flag(value) -> bool:
    return value is True


def _format_leaf(path: str, before: str, after: str) -> list[str]:
    if not path:
        one_line = f"{before} → {after}"
        if len(one_line) <= ONE_LINE_LIMIT:
            return [f"  - {one_line}"]
        return [f"  - {before}", f"    → {after}"]
    one_line = f"{path}: {before} → {after}"
    if len(one_line) <= ONE_LINE_LIMIT:
        return [f"  - {one_line}"]
    return [f"  - {path}", f"    {before}", f"    → {after}"]


def _format_path(parts: list) -> str:
    rendered = ""
    for part in parts:
        if isinstance(part, int):
            rendered += f"[{part}]"
        else:
            rendered += f".{part}" if rendered else str(part)
    return rendered


def _render(value) -> str:
    if value is _ABSENT:
        return "(absent)"
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return _truncate(" ".join(value.split()))
    if isinstance(value, (int, float)):
        return str(value)
    return _truncate(json.dumps(value, sort_keys=True, separators=(", ", ": ")))


def _truncate(value: str) -> str:
    if len(value) <= MAX_VALUE:
        return value
    return value[: MAX_VALUE - 1] + "…"


def _display_component(component: str) -> str:
    slug = component.strip()
    if slug.startswith("./"):
        slug = slug[2:]
    if slug in {"", "."}:
        return "repo"
    return slug


def _component_slug(component: str) -> str:
    slug = component.strip()
    if slug.startswith("./"):
        slug = slug[2:]
    slug = slug.strip("/")
    if slug in {"", "."}:
        return "repo"
    slug = slug.replace("/", "-").replace(" ", "-")
    slug = re.sub(r"[^A-Za-z0-9._-]", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug or "repo"


def _footer(artifact: str, run_url: str) -> str:
    if run_url:
        return f"Full plan: [this run]({run_url})"
    return f"Full plan: artifact {artifact} on this run."


if __name__ == "__main__":
    sys.exit(main())
