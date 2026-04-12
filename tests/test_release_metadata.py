from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from epacomp_tox.server import MCPServer

ROOT_DIR = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = ROOT_DIR / "pyproject.toml"
README_PATH = ROOT_DIR / "README.md"
CHANGELOG_PATH = ROOT_DIR / "CHANGELOG.md"
RELEASE_VERIFICATION_GUIDE_PATH = (
    ROOT_DIR / "docs" / "releases" / "release_artifact_verification.md"
)
V021_RELEASE_DESCRIPTION_PATH = (
    ROOT_DIR / "docs" / "releases" / "v0.2.1_release_description.md"
)
V021_STABILIZATION_PLAN_PATH = (
    ROOT_DIR / "docs" / "releases" / "v0.2.1_stabilization_plan.md"
)
TESTING_MATRIX_PATH = ROOT_DIR / "docs" / "testing_matrix.md"
TRANSPORT_SMOKE_CHECKLIST_PATH = (
    ROOT_DIR / "docs" / "qa" / "transport_smoke_checklist.md"
)
DEVELOPMENT_GUIDE_PATH = ROOT_DIR / "docs" / "development_guide.md"
INTEROP_SMOKE_SCRIPT_PATH = ROOT_DIR / "scripts" / "mcp_interop_smoke.py"
CURRENT_BOUNDARY_DOC_PATHS = (
    ROOT_DIR / "docs" / "development_guide.md",
    ROOT_DIR / "docs" / "predictive_services.md",
    ROOT_DIR / "docs" / "model_cards_and_policies.md",
    ROOT_DIR / "docs" / "workflow_testing_strategy.md",
    ROOT_DIR / "docs" / "dev_experience_content_plan.md",
    ROOT_DIR / "docs" / "observability_requirements.md",
    ROOT_DIR / "docs" / "releases" / "mcp_phase2_planning_snapshot.md",
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


def _current_release_description_path() -> Path:
    return (
        ROOT_DIR / "docs" / "releases" / f"v{_project_version()}_release_description.md"
    )


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


def test_release_description_exists_for_current_project_version() -> None:
    release_description_path = _current_release_description_path()
    assert release_description_path.exists()
    release_description = _read_text(release_description_path)
    version = _project_version()
    assert f"# v{version} Release Description" in release_description


def test_readme_roadmap_links_to_current_release_and_v021_stabilization_plan() -> None:
    version = _project_version()
    readme = _read_text(README_PATH)
    v021_release_description = _read_text(V021_RELEASE_DESCRIPTION_PATH)
    plan = _read_text(V021_STABILIZATION_PLAN_PATH)
    assert f"docs/releases/v{version}_release_description.md" in readme
    assert f"`v{version}` release cleanup" in readme
    assert "docs/releases/v0.2.1_stabilization_plan.md" in readme
    assert "v0.2.1" in v021_release_description
    assert "CTX-backed golden payload capture" in plan
    assert "Contract manifest resource" in plan
    assert "Targeted workflow-contract expansion" in plan


def test_live_interop_smoke_script_is_documented_and_has_help_output() -> None:
    docs = "\n".join(
        (
            _read_text(README_PATH),
            _read_text(TESTING_MATRIX_PATH),
            _read_text(TRANSPORT_SMOKE_CHECKLIST_PATH),
            _read_text(DEVELOPMENT_GUIDE_PATH),
        )
    )
    assert "scripts/mcp_interop_smoke.py" in docs

    result = subprocess.run(
        [sys.executable, str(INTEROP_SMOKE_SCRIPT_PATH), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "build_aop_linkage_summary" in result.stdout
    assert "assemble_comptox_evidence_pack" in result.stdout
    assert "--dtxsid" in result.stdout
    assert "--capture-dir" in result.stdout
    assert "--refresh-live-fixtures" in result.stdout


def test_live_interop_fixture_refresh_path_is_documented() -> None:
    docs = "\n".join(
        (
            _read_text(TESTING_MATRIX_PATH),
            _read_text(TRANSPORT_SMOKE_CHECKLIST_PATH),
            _read_text(DEVELOPMENT_GUIDE_PATH),
        )
    )
    assert "tests/golden/interop_live" in docs
    assert "--capture-dir" in docs
    assert "--refresh-live-fixtures" in docs


def test_current_boundary_docs_reference_current_release_version() -> None:
    version = _project_version()
    for path in CURRENT_BOUNDARY_DOC_PATHS:
        text = _read_text(path)
        assert (
            f"v{version}" in text
        ), f"{path} should reference the current release version"
