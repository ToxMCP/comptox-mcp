from __future__ import annotations

from epacomp_tox import PredictiveRequest
from epacomp_tox.orchestrator import (
    CtxDataBundle,
    EvidenceSynthesizer,
    IdentifierResolution,
    PredictiveStepResult,
)
from epacomp_tox.orchestrator.reference_panel import (
    LiveConcordancePanelCase,
    generate_live_concordance_panel_report,
    render_live_concordance_panel_markdown,
)


class StubHazardResource:
    def __init__(self, payloads: dict[str, list[dict[str, object]]]) -> None:
        self.payloads = payloads

    def get_hazard_toxval(self, dtxsid: str) -> list[dict[str, object]]:
        return list(self.payloads[dtxsid])


def _resolution(dtxsid: str) -> IdentifierResolution:
    return IdentifierResolution(
        input_identifier=dtxsid,
        input_type="dtxsid",
        dtxsid=dtxsid,
        matched_record={"dtxsid": dtxsid},
        detail_record={"dtxsid": dtxsid},
    )


def _synthesize(
    record: dict[str, object], *, predicted_value: float
) -> dict[str, object]:
    synthesizer = EvidenceSynthesizer()
    evidence = synthesizer.synthesize(
        [
            PredictiveStepResult(
                service="test",
                status="success",
                label="respiratory",
                request=PredictiveRequest(chemical_identifier="DTXSID123"),
                prediction={"endpoint": "respiratory", "value": predicted_value},
            )
        ],
        resolution=_resolution("DTXSID123"),
        ctx_bundle=CtxDataBundle(
            dtxsid="DTXSID123",
            hazard={"toxval": [record]},
            data_gaps=[],
        ),
    )
    return {
        "status": evidence.assessment["observedConcordance"]["status"],
        "guardrail_codes": [
            event.code for event in evidence.guardrail_events if event.code
        ],
    }


def test_evidence_synthesizer_matches_toxval_numeric_records() -> None:
    record = {
        "toxicologicalEffect": "respiratory",
        "toxvalNumeric": 0.04912250116467476,
        "toxvalType": "MRL",
        "toxvalSubtype": "acute",
    }

    result = _synthesize(record, predicted_value=0.04912250116467476)

    assert result["status"] == "robust"
    assert result["guardrail_codes"] == []


def test_evidence_synthesizer_flags_toxval_numeric_mismatch() -> None:
    record = {
        "toxicologicalEffect": "respiratory",
        "toxvalNumeric": 0.04912250116467476,
        "toxvalType": "MRL",
        "toxvalSubtype": "acute",
    }

    result = _synthesize(record, predicted_value=2.0491225011646746)

    assert result["status"] == "limited"
    assert result["guardrail_codes"] == ["PREDICTION_OBSERVATION_MISMATCH"]


def test_generate_live_concordance_panel_report_with_stub_resource() -> None:
    hazard_resource = StubHazardResource(
        {
            "DTXSID1": [
                {
                    "source": "ATSDR MRLs",
                    "toxicologicalEffect": "immunological in male mice",
                    "toxvalNumeric": 0.028753800317645073,
                    "toxvalType": "MRL",
                    "toxvalSubtype": "acute",
                }
            ],
            "DTXSID2": [
                {
                    "source": "ATSDR MRLs",
                    "toxicologicalEffect": "respiratory",
                    "toxvalNumeric": 0.04912250116467476,
                    "toxvalType": "MRL",
                    "toxvalSubtype": "acute",
                }
            ],
        }
    )
    panel = [
        LiveConcordancePanelCase(
            case_id="benzene_match",
            dtxsid="DTXSID1",
            expected_status="robust",
            source_contains="ATSDR",
            toxval_type="MRL",
            toxval_subtype="acute",
            effect_contains="immunological",
        ),
        LiveConcordancePanelCase(
            case_id="formaldehyde_offset",
            dtxsid="DTXSID2",
            expected_status="limited",
            prediction_mode="offset",
            offset=2.0,
            source_contains="ATSDR",
            toxval_type="MRL",
            toxval_subtype="acute",
            effect_contains="respiratory",
        ),
    ]

    report = generate_live_concordance_panel_report(
        panel=panel,
        hazard_resource=hazard_resource,
    )
    markdown = render_live_concordance_panel_markdown(report)

    assert report.summary.total_cases == 2
    assert report.summary.passed_cases == 2
    assert report.summary.failed_cases == 0
    assert report.summary.error_cases == 0
    assert report.summary.all_cases_passed is True
    assert report.summary.actual_status_counts == {"robust": 1, "limited": 1}
    assert report.cases[0].actual_observed_concordance == "robust"
    assert report.cases[1].actual_observed_concordance == "limited"
    assert report.cases[1].guardrail_codes == ["PREDICTION_OBSERVATION_MISMATCH"]
    assert "# Live Concordance Panel" in markdown
    assert "benzene_match" in markdown
    assert "formaldehyde_offset" in markdown
