#!/usr/bin/env python3
"""Check documentation links and prepare the GitHub Pages build.

Relative links in docs/*.md stay useful in a clone. Links that point outside
docs/ are rewritten to this commit on GitHub only in the Pages build.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
REPO = "opptra/sdlc-resources"
LINK = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
FENCE = re.compile(r"```.*?```", re.DOTALL)


def page_files() -> list[Path]:
    return sorted(path for path in DOCS.glob("*.md") if path.is_file())


def visible_text(path: Path) -> str:
    return FENCE.sub("", path.read_text())


def resolve_target(page: Path, raw: str) -> Path | None:
    path_part = raw.split("#", 1)[0]
    if not path_part or raw.startswith(("http://", "https://", "mailto:")):
        return None
    target = (page.parent / path_part).resolve()
    if not target.is_relative_to(ROOT):
        raise SystemExit(f"{page.relative_to(ROOT)}: link escapes the repo: {raw}")
    return target


def check() -> list[str]:
    errors: list[str] = []
    pages = page_files()
    if not pages:
        return ["docs/ has no markdown pages"]
    for page in pages:
        for match in LINK.finditer(visible_text(page)):
            raw = match.group(2)
            try:
                target = resolve_target(page, raw)
            except SystemExit as exc:
                errors.append(str(exc))
                continue
            if target is None:
                continue
            if not target.exists():
                errors.append(
                    f"{page.relative_to(ROOT)}: missing {raw} -> {target.relative_to(ROOT)}"
                )
    return errors


def github_url(target: Path, ref: str) -> str:
    rel = target.relative_to(ROOT).as_posix()
    kind = "tree" if target.is_dir() else "blob"
    return f"https://github.com/{REPO}/{kind}/{ref}/{rel}"


def rewrite(text: str, page: Path, ref: str) -> str:
    def replace(match: re.Match[str]) -> str:
        raw = match.group(2)
        target = resolve_target(page, raw)
        if target is None or DOCS in target.parents or target == DOCS:
            return match.group(0)
        fragment = ""
        if "#" in raw and not raw.startswith("#"):
            fragment = "#" + raw.split("#", 1)[1]
        label = match.group(1)
        if label == raw or label.startswith("../"):
            label = target.relative_to(ROOT).as_posix()
        return f"[{label}]({github_url(target, ref)}{fragment})"

    return LINK.sub(replace, text)


def prepare(dest: Path) -> None:
    errors = check()
    if errors:
        raise SystemExit("\n".join(errors))
    if dest.exists():
        shutil.rmtree(dest)
    copied = dest / "docs"
    copied.mkdir(parents=True)
    ref = os.environ.get("DOCS_GIT_REF", "main")
    for page in page_files():
        text = rewrite(page.read_text(), page, ref)
        (copied / page.name).write_text(text)
    config = (ROOT / "mkdocs.yml").read_text()
    config += "\nsite_dir: ../site\n"
    (dest / "mkdocs.yml").write_text(config)


def main(argv: list[str]) -> int:
    if not argv or argv[0] == "check":
        errors = check()
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 1
        print(f"docs links ok ({len(page_files())} pages)")
        return 0
    if argv[0] == "prepare":
        if len(argv) != 2:
            print("usage: docs_site.py prepare <dest>", file=sys.stderr)
            return 2
        prepare(Path(argv[1]).resolve())
        print(f"prepared {argv[1]}")
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
