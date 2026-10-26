#!/usr/bin/env python3
"""Turn rules/source into the files Cursor and Claude actually read.

Wraps the standard SDLC sections inside <!-- sdlc-rules-start --> and
<!-- sdlc-rules-end --> so any existing Product contract or repository-specific
guidance outside those markers is preserved intact.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from yaml_subset import parse

ROOT = Path(__file__).resolve().parents[1]
VERSION = "2"
START_MARKER = "<!-- sdlc-rules-start -->"
END_MARKER = "<!-- sdlc-rules-end -->"

GLOBS = {
    "python": "{**/backend/**/*.py,src/**/*.py,scripts/**/*.py,tests/**/*.py}",
    "react": "{components/**/frontend/**/*.{ts,tsx},**/frontend/**/*.{ts,tsx},apps/**/*.{ts,tsx}}",
    "terraform": "**/infra/**",
    "job": "{**/backend/**/*.py,src/**/*.py,scripts/**/*.py}",
    "worker": "{**/backend/**/*.py,src/**/*.py}",
    "config": "{README.md,**/README.md,service.yaml,Dockerfile,**/Dockerfile*,.github/workflows/**}",
    "database": "{**/backend/**/*.py,src/**/*.py}",
    "firestore": "{**/backend/**/*.py,src/**/*.py}",
    "bigquery": "{**/backend/**/*.py,src/**/*.py,scripts/**/*.sql,bq-schema/**/*.sql}",
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
    sections = [f"<!-- sdlc-rules-version: {VERSION} -->\n{START_MARKER}\n"]
    mdc_files: dict[str, str] = {}
    for name in names:
        body = rule_text(name)
        sections.append(f"## {name}\n\n{body}")
        mdc_files[f"{name}.mdc"] = cursor_rule(name, body)
    sections.append(f"{END_MARKER}\n")
    return "\n".join(sections), mdc_files


def _merge_preserving_tail(existing: str, managed_block: str) -> str:
    if START_MARKER in existing and END_MARKER in existing:
        after = existing.split(END_MARKER, 1)[1].lstrip("\n")
        return managed_block + ("\n" + after if after else "")
    if "## Product contract" in existing:
        tail = existing[existing.index("## Product contract") :]
        return managed_block + "\n" + tail
    if "<!-- sdlc-rules-version:" not in existing and existing.strip():
        return managed_block + "\n## Product contract\n\n" + existing.strip() + "\n"
    return managed_block


def write_bundle(directory: Path, names: list[str]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    rules_dir = directory / ".cursor" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    managed_text, mdc_files = render_bundle(names)
    known = set(parse((ROOT / "mapping.yaml").read_text())["rules"])
    keep = {Path(filename).stem for filename in mdc_files}
    for stale in rules_dir.glob("*.mdc"):
        if stale.stem in known and stale.stem not in keep:
            stale.unlink()
    for filename, content in mdc_files.items():
        (rules_dir / filename).write_text(content)
    for doc_name in ("AGENTS.md", "CLAUDE.md"):
        doc_path = directory / doc_name
        existing = doc_path.read_text() if doc_path.is_file() else ""
        doc_path.write_text(_merge_preserving_tail(existing, managed_text))


def check_bundle(directory: Path, names: list[str]) -> list[str]:
    errors: list[str] = []
    _, mdc_files = render_bundle(names)
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
