#!/usr/bin/env python3
"""Turn rules/source into the files Cursor and Claude actually read."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from yaml_subset import parse

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1"

GLOBS = {
    "python": "backend/**/*.py",
    "react": "frontend/**/*.{ts,tsx}",
    "terraform": "infra/**",
    "job": "backend/**/*.py",
    "worker": "backend/**/*.py",
    "config": "README.md",
}


def rule_text(name: str) -> str:
    mapping = parse((ROOT / "mapping.yaml").read_text())
    path = ROOT / mapping["rules"][name]
    return path.read_text().strip() + "\n"


def cursor_rule(name: str, body: str) -> str:
    if name == "always":
        header = "---\ndescription: Opptra standard\nalwaysApply: true\n---\n\n"
    else:
        header = (
            "---\n"
            f"description: Opptra {name} rules\n"
            f"globs: {GLOBS[name]}\n"
            "alwaysApply: false\n"
            "---\n\n"
        )
    return f"{header}{body}"


def write_bundle(directory: Path, names: list[str]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    rules_dir = directory / ".cursor" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    sections = [f"<!-- sdlc-rules-version: {VERSION} -->\n"]
    for name in names:
        body = rule_text(name)
        sections.append(f"## {name}\n\n{body}")
        (rules_dir / f"{name}.mdc").write_text(cursor_rule(name, body))
    text = "\n".join(sections)
    (directory / "AGENTS.md").write_text(text)
    (directory / "CLAUDE.md").write_text(text)


def main() -> int:
    mapping = parse((ROOT / "mapping.yaml").read_text())
    names = ["always"] + [name for name in mapping["rules"] if name != "always"]
    write_bundle(ROOT / "rules" / "dist", names)
    print(ROOT / "rules" / "dist")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
