from __future__ import annotations

import re
from pathlib import Path

WORKFLOWS_DIR = Path(__file__).resolve().parents[1] / ".github" / "workflows"
SHA_REF_PATTERN = re.compile(
    r"uses:\s+(?P<action>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?)@(?P<ref>[0-9a-f]{40})\s+#\s+v",
)
EXTERNAL_ACTION_PATTERN = re.compile(
    r"uses:\s+(?P<action>(?:actions|github)/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?)@(?P<ref>\S+)"
)


def _workflow_text(name: str) -> str:
    return (WORKFLOWS_DIR / name).read_text(encoding="utf-8")


def test_external_github_actions_are_pinned_to_commit_shas() -> None:
    offenders: list[str] = []
    for workflow_path in sorted(WORKFLOWS_DIR.glob("*.yml")):
        for line_number, line in enumerate(
            workflow_path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            match = EXTERNAL_ACTION_PATTERN.search(line)
            if not match:
                continue
            if not SHA_REF_PATTERN.search(line):
                offenders.append(f"{workflow_path.name}:{line_number}:{line.strip()}")
    assert (
        not offenders
    ), "Workflow actions must be pinned to commit SHAs: " + ", ".join(offenders)


def test_codeql_workflow_exists_with_python_analysis() -> None:
    text = _workflow_text("codeql.yml")
    assert "name: CodeQL" in text
    assert "CodeQL (python)" in text
    assert "security-events: write" in text
    assert "build-mode: none" in text
    assert "github/codeql-action/init@" in text
    assert "github/codeql-action/analyze@" in text
