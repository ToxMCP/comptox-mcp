from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pytest

from epacomp_tox import PredictiveTask, PredictiveRequest
from epacomp_tox.orchestrator.offline import (
    OFFLINE_SCENARIOS,
    build_offline_orchestrator,
)


def _sanitize_bundle(bundle: Dict[str, any]) -> Dict[str, any]:
    predictive = bundle["predictive"]["results"][0]
    metadata = predictive["metadata"]
    return {
        "status": bundle["status"],
        "scenarios": bundle.get("scenarios"),
        "target": {
            "dtxsid": bundle["target"]["dtxsid"],
            "preferredName": bundle["target"].get("preferredName"),
            "casrn": bundle["target"].get("casrn"),
            "synonyms": sorted(bundle["target"].get("synonyms", [])),
        },
        "guardrails": bundle.get("guardrails", []),
        "ctxData": {
            "hazardEndpoints": [item.get("endpoint") for item in bundle["ctxData"]["hazard"].get("all", [])],
            "exposureKeys": sorted(bundle["ctxData"]["exposure"].keys()),
            "cheminformaticsKeys": sorted(bundle["ctxData"]["cheminformatics"].keys()),
            "dataGaps": bundle["ctxData"].get("dataGaps", []),
        },
        "predictive": {
            "service": predictive["service"],
            "status": predictive["status"],
            "scenario": predictive.get("scenario"),
            "prediction": predictive["prediction"],
            "ad": predictive["ad"],
            "metadata": {
                "model": metadata.get("model"),
                "model_version": metadata.get("model_version"),
                "identifier": metadata.get("identifier"),
                "identifier_type": metadata.get("identifier_type"),
                "analogueCoverage": metadata.get("analogueCoverage"),
                "evidenceQuality": metadata.get("evidenceQuality"),
                "predictiveAgreement": metadata.get("predictiveAgreement"),
            },
        },
        "evidence": {
            "confidenceBand": bundle["evidence"].get("confidenceBand"),
            "scores": bundle["evidence"].get("scores"),
            "recommendedActions": bundle["evidence"].get("recommendedActions"),
        },
    }


def _expected_snapshot(scenario: str) -> Dict[str, any]:
    exposure_lookup = {
        "acute_toxicity": ["cpdat:fc", "httk"],
        "exposure_prioritization": ["cpdat:fc", "cpdat:puc", "httk", "pathways", "seem"],
        "genra_read_across": ["cpdat:fc", "httk", "qsurs"],
    }
    return {
        "status": "success",
        "scenarios": [scenario],
        "target": {
            "dtxsid": "DTXSID0000001",
            "preferredName": "Offline Example",
            "casrn": "50-00-0",
            "synonyms": ["Formaldehyde", "Methanal"],
        },
        "guardrails": [],
        "ctxData": {
            "hazardEndpoints": ["Acute toxicity"],
            "exposureKeys": exposure_lookup[scenario],
            "cheminformaticsKeys": ["toxprints"],
            "dataGaps": [],
        },
        "predictive": {
            "service": "offline_genra",
            "status": "success",
            "scenario": scenario,
            "prediction": {
                "prediction": "Read-across suggests low concern.",
                "confidence": 0.82,
            },
            "ad": {
                "in_domain": True,
                "confidence": 0.85,
                "details": {"analogues": 4},
            },
            "metadata": {
                "model": "Offline GenRA",
                "model_version": "0.1",
                "identifier": "DTXSID0000001",
                "identifier_type": "dtxsid",
                "analogueCoverage": 0.88,
                "evidenceQuality": 0.74,
                "predictiveAgreement": 0.85,
            },
        },
        "evidence": {
            "confidenceBand": "Limited",
            "scores": {
                "analogue_coverage": 0.88,
                "evidence_quality": 0.74,
                "predictive_agreement": 0.85,
            },
            "recommendedActions": [
                "Seek SME review",
                "Augment analogue set or supporting evidence",
            ],
        },
    }


@pytest.mark.parametrize("scenario", OFFLINE_SCENARIOS)
def test_offline_orchestrator_scenarios(tmp_path: Path, scenario: str) -> None:
    orchestrator = build_offline_orchestrator(
        persistence_dir=tmp_path,
        clock=lambda: "2025-03-26T00:00:00Z",
    )
    bundle = orchestrator.run_workflow(
        target_identifier="50-00-0",
        identifier_type="casrn",
        scenarios=[scenario],
        predictive_plan=[
            PredictiveTask(
                service="offline_genra",
                scenario=scenario,
                request=PredictiveRequest(chemical_identifier="DTXSID0000001"),
            )
        ],
    )

    sanitized = _sanitize_bundle(bundle)
    assert sanitized == _expected_snapshot(scenario)

    run_dir = tmp_path / bundle["workflowRunId"]
    bundle_path = run_dir / "bundle.json"
    metadata_path = run_dir / "metadata.json"
    attachments_dir = run_dir / "attachments"

    assert bundle_path.exists()
    assert metadata_path.exists()
    assert attachments_dir.exists()

    attachment_names = {path.name for path in attachments_dir.iterdir()}
    assert {"ctx_data.json", "predictive_results.json", "evidence.json"}.issubset(attachment_names)

    storage_meta = bundle.get("storage") or {}
    assert storage_meta.get("bundlePath") == str(bundle_path.relative_to(tmp_path))
    assert storage_meta.get("bundleChecksum")


def test_audit_bundle_store_lists_runs(tmp_path: Path) -> None:
    orchestrator = build_offline_orchestrator(
        persistence_dir=tmp_path,
        clock=lambda: "2025-03-26T00:00:00Z",
    )
    bundle_ids: List[str] = []
    for scenario in OFFLINE_SCENARIOS:
        result = orchestrator.run_workflow(
            target_identifier="50-00-0",
            identifier_type="casrn",
            scenarios=[scenario],
            predictive_plan=[
                PredictiveTask(
                    service="offline_genra",
                    scenario=scenario,
                    request=PredictiveRequest(chemical_identifier="DTXSID0000001"),
                )
            ],
        )
        bundle_ids.append(result["workflowRunId"])

    store = orchestrator.bundle_store
    assert store is not None
    runs = store.list_runs()
    assert len(runs) == len(OFFLINE_SCENARIOS)
    retrieved_ids = {row["workflowRunId"] for row in runs}
    assert retrieved_ids == set(bundle_ids)
