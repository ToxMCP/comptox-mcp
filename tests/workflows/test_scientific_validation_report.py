from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from epacomp_tox.orchestrator import (
    OFFLINE_SCENARIOS,
    generate_offline_validation_report,
    render_validation_report_markdown,
)

ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT_DIR / "scripts" / "scientific_validation_report.py"


def test_generate_offline_validation_report_offline_suite(tmp_path: Path) -> None:
    report = generate_offline_validation_report(persistence_dir=tmp_path)

    assert report.orchestrator_mode == "offline"
    assert report.summary.total_scenarios == len(OFFLINE_SCENARIOS)
    assert report.summary.status_counts == {"success": len(OFFLINE_SCENARIOS)}
    assert report.summary.confidence_band_counts == {"Limited": len(OFFLINE_SCENARIOS)}
    assert report.summary.total_guardrail_events == 0
    assert report.summary.scenarios_with_data_gaps == 0
    assert report.summary.scenarios_with_complete_interop == len(OFFLINE_SCENARIOS)
    assert report.summary.all_scenarios_succeeded is True
    assert report.summary.all_identity_robust is True
    assert report.summary.all_domain_clear is True
    assert report.summary.all_data_complete is True
    assert report.summary.interop_attachment_coverage == {
        "interop/comptox_evidence_pack.json": len(OFFLINE_SCENARIOS),
        "interop/aop_linkage_summary.json": len(OFFLINE_SCENARIOS),
        "interop/pbpk_context_bundle.json": len(OFFLINE_SCENARIOS),
    }
    assert report.summary.assessment_status_counts["identityIntegrity"] == {
        "robust": len(OFFLINE_SCENARIOS)
    }
    assert report.summary.assessment_status_counts["predictiveSupport"] == {
        "limited": len(OFFLINE_SCENARIOS)
    }
    assert {item.scenario for item in report.scenarios} == set(OFFLINE_SCENARIOS)
    assert all(item.bundle_path for item in report.scenarios)
    assert all(item.bundle_checksum for item in report.scenarios)


def test_render_validation_report_markdown(tmp_path: Path) -> None:
    report = generate_offline_validation_report(
        persistence_dir=tmp_path, scenarios=["acute_toxicity"]
    )
    markdown = render_validation_report_markdown(report)

    assert "# Scientific Validation Report" in markdown
    assert "acute_toxicity" in markdown
    assert "Complete interop coverage" in markdown
    assert "`identityIntegrity`" in markdown
    assert "interop/comptox_evidence_pack.json" in markdown


def test_scientific_validation_report_script_writes_outputs(tmp_path: Path) -> None:
    json_path = tmp_path / "report.json"
    markdown_path = tmp_path / "report.md"
    persistence_dir = tmp_path / "artifacts"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--scenario",
            "acute_toxicity",
            "--persistence-dir",
            str(persistence_dir),
            "--output-json",
            str(json_path),
            "--output-markdown",
            str(markdown_path),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["summary"]["total_scenarios"] == 1
    assert payload["scenarios"][0]["scenario"] == "acute_toxicity"
    assert json_path.exists()
    assert markdown_path.exists()
    assert "# Scientific Validation Report" in markdown_path.read_text(encoding="utf-8")
