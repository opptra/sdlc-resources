#!/usr/bin/env python3
"""Turn rules/source into the files Cursor and Claude actually read."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from yaml_subset import parse

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1"

GLOBS = {
    "python": "**/backend/**/*.py",
    "react": "**/frontend/**/*.{ts,tsx}",
    "terraform": "**/infra/**",
    "job": "**/backend/**/*.py",
    "worker": "**/backend/**/*.py",
    "config": "README.md",
    "database": "**/backend/**/*.py",
    "firestore": "**/backend/**/*.py",
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
            f"globs: {GLOBS.get(name, '**/*')}\n"
            "alwaysApply: false\n"
            "---\n\n"
        )
    return f"{header}{body}"


def render_bundle(names: list[str]) -> tuple[str, dict[str, str]]:
    sections = [f"<!-- sdlc-rules-version: {VERSION} -->\n"]
    mdc_files: dict[str, str] = {}
    for name in names:
        body = rule_text(name)
        sections.append(f"## {name}\n\n{body}")
        mdc_files[f"{name}.mdc"] = cursor_rule(name, body)
    return "\n".join(sections), mdc_files


def write_bundle(directory: Path, names: list[str]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    rules_dir = directory / ".cursor" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    text, mdc_files = render_bundle(names)
    for filename, content in mdc_files.items():
        (rules_dir / filename).write_text(content)
    (directory / "AGENTS.md").write_text(text)
    (directory / "CLAUDE.md").write_text(text)


def check_bundle(directory: Path, names: list[str]) -> list[str]:
    errors: list[str] = []
    expected_text, mdc_files = render_bundle(names)
    for doc_name in ("AGENTS.md", "CLAUDE.md"):
        doc_path = directory / doc_name
        if not doc_path.is_file():
            errors.append(f"missing {doc_name}")
        elif f"<!-- sdlc-rules-version: {VERSION} -->" not in doc_path.read_text():
            errors.append(f"{doc_name} is missing sdlc-rules-version {VERSION} stamp")
        else:
            content = doc_path.read_text()
            for name in names:
                if f"## {name}\n" not in content:
                    errors.append(f"{doc_name} is missing rule section '{name}'")
    rules_dir = directory / ".cursor" / "rules"
    for filename in mdc_files:
        if not (rules_dir / filename).is_file():
            errors.append(f"missing .cursor/rules/{filename}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dest", type=Path, default=ROOT / "rules" / "dist")
    parser.add_argument("--rules", nargs="*", help="Rule names to include")
    parser.add_argument("--check", action="store_true", help="Verify rules exist and match")
    args = parser.parse_args(argv)

    mapping = parse((ROOT / "mapping.yaml").read_text())
    names = args.rules or (["always"] + [name for name in mapping["rules"] if name != "always"])
    if "always" not in names:
        names = ["always"] + list(names)

    if args.check:
        errs = check_bundle(args.dest, names)
        if errs:
            for e in errs:
                print(e, file=sys.stderr)
            return 1
        print("rules: ok")
        return 0

    write_bundle(args.dest, names)
    print(args.dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
