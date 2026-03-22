from __future__ import annotations

import re
from pathlib import Path

from epacomp_tox.server import MCPServer

ROOT_DIR = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = ROOT_DIR / "pyproject.toml"
README_PATH = ROOT_DIR / "README.md"
CHANGELOG_PATH = ROOT_DIR / "CHANGELOG.md"
RELEASE_VERIFICATION_GUIDE_PATH = (
    ROOT_DIR / "docs" / "releases" / "release_artifact_verification.md"
)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _project_version() -> str:
    match = re.search(
        r'^version\s*=\s*"(?P<version>[^"]+)"',
        _read_text(PYPROJECT_PATH),
        re.MULTILINE,
    )
    assert match, "Project version not found in pyproject.toml"
    return match.group("version")


def test_server_version_matches_project_metadata() -> None:
    assert MCPServer._resolve_version() == _project_version()


def test_readme_whats_new_section_matches_project_version() -> None:
    version = _project_version()
    readme = _read_text(README_PATH)
    assert f"## What's New In v{version}" in readme


def test_changelog_has_unreleased_section_and_current_release_entry() -> None:
    version = _project_version()
    changelog = _read_text(CHANGELOG_PATH)
    unreleased_index = changelog.find("## [Unreleased]")
    release_index = changelog.find(f"## [{version}]")
    assert unreleased_index != -1, "CHANGELOG must include an [Unreleased] section"
    assert release_index != -1, f"CHANGELOG must include the current release {version}"
    assert (
        unreleased_index < release_index
    ), "CHANGELOG [Unreleased] section should appear before the current release entry"


def test_project_urls_use_canonical_repository() -> None:
    pyproject = _read_text(PYPROJECT_PATH)
    expected_urls = [
        'Homepage = "https://github.com/ToxMCP/comptox-mcp"',
        'Repository = "https://github.com/ToxMCP/comptox-mcp"',
        'Issues = "https://github.com/ToxMCP/comptox-mcp/issues"',
        'Documentation = "https://github.com/ToxMCP/comptox-mcp/tree/main/docs"',
        'Security = "https://github.com/ToxMCP/comptox-mcp/security/policy"',
    ]
    for expected in expected_urls:
        assert expected in pyproject


def test_release_verification_guide_is_linked_and_actionable() -> None:
    readme = _read_text(README_PATH)
    guide = _read_text(RELEASE_VERIFICATION_GUIDE_PATH)
    assert "docs/releases/release_artifact_verification.md" in readme
    assert "gh attestation verify" in guide
    assert "gh attestation download" in guide
    assert "gh attestation trusted-root" in guide
    assert "ToxMCP/comptox-mcp/.github/workflows/release-sbom.yml" in guide
    assert "https://cyclonedx.org/bom" in guide
