from __future__ import annotations

import json
from pathlib import Path

from epacomp_tox.contracts import validate_payload
from epacomp_tox.resources.prioritization import PrioritizationResource
from tests.interop_test_support import (
    StubBioactivityResource,
    StubChemicalResource,
    StubExposureResource,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "prioritization"


def build_prioritization_resource() -> PrioritizationResource:
    return PrioritizationResource(
        api_key="fake",
        chemical_resource=StubChemicalResource(),
        bioactivity_resource=StubBioactivityResource(),
        exposure_resource=StubExposureResource(),
    )


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def _sanitize_prioritization(payload: dict) -> dict:
    return {
        "chemicalRef": payload["chemicalRef"],
        "hazardSignal": payload["hazardSignal"],
        "exposureSignal": payload["exposureSignal"],
        "prioritization": payload["prioritization"],
        "knownDataGaps": payload["knownDataGaps"],
        "limitations": payload["limitations"],
        "generatedFromTools": payload["generatedFromTools"],
        "provenanceSummary": {
            "generatedBy": payload["provenanceSummary"]["generatedBy"],
            "identityMode": payload["provenanceSummary"]["identityMode"],
            "sourceCount": payload["provenanceSummary"]["sourceCount"],
            "sourceTools": payload["provenanceSummary"]["sourceTools"],
        },
    }


def test_prioritize_risk_signals_computes_screening_margin() -> None:
    resource = build_prioritization_resource()

    result = resource.execute_tool(
        "prioritize_risk_signals",
        {"dtxsid": "DTXSID7020182"},
    )

    validate_payload(
        result,
        namespace="risk",
        name="prioritize_risk_signals.response.schema",
    )
    assert result["chemicalRef"]["dtxsid"] == "DTXSID7020182"
    assert result["hazardSignal"]["selectedMetric"]["aedVal"] == 6.0
    assert result["prioritization"]["marginOfExposure"] == 50.0
    assert result["prioritization"]["priorityBand"] == "higher"
    assert "get_bioactivity_aed" in result["generatedFromTools"]
    assert _sanitize_prioritization(result) == _load_fixture(
        "prioritize_risk_signals.json"
    )


def test_prioritize_risk_signals_carries_identity_resolution_for_non_dtxsid_input() -> None:
    resource = build_prioritization_resource()

    result = resource.execute_tool(
        "prioritize_risk_signals",
        {"identifier": "80-05-7", "identifier_type": "casrn"},
    )

    validate_payload(
        result,
        namespace="risk",
        name="prioritize_risk_signals.response.schema",
    )
    assert result["identityResolution"]["canonicalDtxsid"] == "DTXSID7020182"
    assert result["provenanceSummary"]["identityMode"] == "resolved_identifier"


class MissingAedBioactivityResource(StubBioactivityResource):
    def get_bioactivity_aed(self, dtxsid: str):
        return []


def test_prioritize_risk_signals_returns_inconclusive_when_aed_is_missing() -> None:
    resource = PrioritizationResource(
        api_key="fake",
        chemical_resource=StubChemicalResource(),
        bioactivity_resource=MissingAedBioactivityResource(),
        exposure_resource=StubExposureResource(),
    )

    result = resource.execute_tool(
        "prioritize_risk_signals",
        {"dtxsid": "DTXSID7020182"},
    )

    validate_payload(
        result,
        namespace="risk",
        name="prioritize_risk_signals.response.schema",
    )
    assert result["prioritization"]["priorityBand"] == "inconclusive"
    assert result["prioritization"]["marginOfExposure"] is None
    assert "bioactivity:aed" in result["knownDataGaps"]
