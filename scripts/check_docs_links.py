"""Basic markdown link checker for docs and README."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MD_FILES = list((ROOT / "docs").rglob("*.md")) + [
    ROOT / "README.md",
    ROOT / "research.md",
]

LINK_PATTERN = re.compile(r"\[[^\]]+]\(([^)]+)\)")


def iter_links(markdown: str):
    for match in LINK_PATTERN.finditer(markdown):
        target = match.group(1)
        if target.startswith("#"):
            continue
        if "://" in target or target.startswith("mailto:"):
            continue
        yield target


def normalize(target: str) -> tuple[str, str]:
    if "#" in target:
        path, anchor = target.split("#", 1)
    else:
        path, anchor = target, ""
    return path, anchor


def check_file(path: Path) -> list[str]:
    errors: list[str] = []
    content = path.read_text(encoding="utf-8")
    for raw_link in iter_links(content):
        link, _ = normalize(raw_link)
        if not link:
            continue
        link_path = (path.parent / link).resolve()
        # Allow directories (e.g., linking to docs/qa/)
        if not link_path.exists():
            errors.append(
                f"{path.relative_to(ROOT)} -> missing link target '{raw_link}'"
            )
    return errors


def main() -> int:
    errors: list[str] = []
    for md_path in MD_FILES:
        if not md_path.exists():
            continue
        errors.extend(check_file(md_path))

    if errors:
        print("Broken markdown links detected:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print("Markdown link check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
