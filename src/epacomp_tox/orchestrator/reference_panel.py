from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Literal, Optional, Sequence

from pydantic import BaseModel, Field

from epacomp_tox.config import get_api_key
from epacomp_tox.predictive.base import PredictiveRequest
from epacomp_tox.resources.hazard import HazardResource

from .evidence import EvidenceSynthesizer
from .models import CtxDataBundle, IdentifierResolution, PredictiveStepResult

ObservedConcordanceStatus = Literal["robust", "limited", "unavailable"]
PredictionMode = Literal["mirror", "offset"]
PanelResultStatus = Literal["pass", "fail", "error"]


class LiveConcordancePanelCase(BaseModel):
    """Curated live CTX concordance check with an expected synthesis outcome."""

    case_id: str
    dtxsid: str
    expected_status: ObservedConcordanceStatus
    prediction_mode: PredictionMode = "mirror"
    offset: float = 0.0
    source_contains: Optional[str] = None
    toxval_type: Optional[str] = None
    toxval_subtype: Optional[str] = None
    effect_contains: Optional[str] = None


class LiveConcordanceCaseResult(BaseModel):
    """Outcome for one live concordance panel case."""

    case_id: str
    dtxsid: str
    result: PanelResultStatus
    expected_observed_concordance: ObservedConcordanceStatus
    actual_observed_concordance: Optional[ObservedConcordanceStatus] = None
    confidence_band: Optional[str] = None
    matched_effect: Optional[str] = None
    source: Optional[str] = None
    toxval_type: Optional[str] = None
    toxval_subtype: Optional[str] = None
    observed_value: Optional[float] = None
    predicted_value: Optional[float] = None
    guardrail_codes: List[str] = Field(default_factory=list)
    message: Optional[str] = None


class LiveConcordancePanelSummary(BaseModel):
    """Aggregate status for a live concordance reference run."""

    total_cases: int
    passed_cases: int
    failed_cases: int
    error_cases: int
    expected_status_counts: Dict[str, int] = Field(default_factory=dict)
    actual_status_counts: Dict[str, int] = Field(default_factory=dict)
    all_cases_passed: bool = False


class LiveConcordancePanelReport(BaseModel):
    """Portable report for CTX-backed concordance reference checks."""

    report_version: str = "0.1"
    generated_at: str
    threshold: float
    cases: List[LiveConcordanceCaseResult]
    summary: LiveConcordancePanelSummary


DEFAULT_LIVE_CONCORDANCE_PANEL: tuple[LiveConcordancePanelCase, ...] = (
    LiveConcordancePanelCase(
        case_id="benzene_acute_mrl_match",
        dtxsid="DTXSID3039242",
        expected_status="robust",
        prediction_mode="mirror",
        source_contains="ATSDR",
        toxval_type="MRL",
        toxval_subtype="acute",
        effect_contains="immunological",
    ),
    LiveConcordancePanelCase(
        case_id="formaldehyde_acute_mrl_offset",
        dtxsid="DTXSID7020637",
        expected_status="limited",
        prediction_mode="offset",
        offset=2.0,
        source_contains="ATSDR",
        toxval_type="MRL",
        toxval_subtype="acute",
        effect_contains="respiratory",
    ),
    LiveConcordancePanelCase(
        case_id="toluene_acute_mrl_match",
        dtxsid="DTXSID7021360",
        expected_status="robust",
        prediction_mode="mirror",
        source_contains="ATSDR",
        toxval_type="MRL",
        toxval_subtype="acute",
        effect_contains="neurological",
    ),
)


def generate_live_concordance_panel_report(
    *,
    panel: Optional[Sequence[LiveConcordancePanelCase]] = None,
    threshold: float = 1.0,
    api_key: Optional[str] = None,
    hazard_resource: Optional[Any] = None,
) -> LiveConcordancePanelReport:
    """Run a curated CTX-backed panel against the live concordance logic."""

    selected_panel = list(panel or DEFAULT_LIVE_CONCORDANCE_PANEL)
    resource = hazard_resource or HazardResource(api_key=api_key or get_api_key())
    synthesizer = EvidenceSynthesizer()
    case_results = [
        _run_panel_case(
            case,
            synthesizer=synthesizer,
            threshold=threshold,
            hazard_resource=resource,
        )
        for case in selected_panel
    ]
    return LiveConcordancePanelReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        threshold=threshold,
        cases=case_results,
        summary=_build_panel_summary(case_results),
    )


def render_live_concordance_panel_markdown(
    report: LiveConcordancePanelReport,
) -> str:
    """Render a concise Markdown scorecard for the live concordance panel."""

    lines = [
        "# Live Concordance Panel",
        "",
        f"- Generated: `{report.generated_at}`",
        f"- Threshold: `{report.threshold}`",
        f"- All cases passed: `{report.summary.all_cases_passed}`",
        f"- Passed / Failed / Error: `{report.summary.passed_cases}/{report.summary.failed_cases}/{report.summary.error_cases}`",
        "",
        "| Case | Result | Expected | Actual | Effect | Observed | Predicted |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in report.cases:
        lines.append(
            "| "
            f"{item.case_id} | "
            f"{item.result} | "
            f"{item.expected_observed_concordance} | "
            f"{item.actual_observed_concordance or 'n/a'} | "
            f"{item.matched_effect or 'n/a'} | "
            f"{item.observed_value if item.observed_value is not None else 'n/a'} | "
            f"{item.predicted_value if item.predicted_value is not None else 'n/a'} |"
        )
        if item.message:
            lines.append(f"> {item.case_id}: {item.message}")

    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- Expected concordance counts: `{report.summary.expected_status_counts}`",
            f"- Actual concordance counts: `{report.summary.actual_status_counts}`",
        ]
    )
    return "\n".join(lines)


def build_default_live_concordance_panel() -> List[LiveConcordancePanelCase]:
    """Return a mutable copy of the default curated panel."""

    return [case.model_copy(deep=True) for case in DEFAULT_LIVE_CONCORDANCE_PANEL]


def _run_panel_case(
    case: LiveConcordancePanelCase,
    *,
    synthesizer: EvidenceSynthesizer,
    threshold: float,
    hazard_resource: Any,
) -> LiveConcordanceCaseResult:
    try:
        hazard_records = hazard_resource.get_hazard_toxval(case.dtxsid)
        matched_record = _select_toxval_record(hazard_records, case)
        if matched_record is None:
            return LiveConcordanceCaseResult(
                case_id=case.case_id,
                dtxsid=case.dtxsid,
                result="error",
                expected_observed_concordance=case.expected_status,
                message="No live ToxVal record matched the curated panel selectors.",
            )

        observed_endpoint = synthesizer._pick_observed_endpoint(matched_record)
        observed_value = synthesizer._coerce_number(
            synthesizer._pick_observed_value(matched_record)
        )
        if observed_endpoint is None or observed_value is None:
            return LiveConcordanceCaseResult(
                case_id=case.case_id,
                dtxsid=case.dtxsid,
                result="error",
                expected_observed_concordance=case.expected_status,
                matched_effect=_string_or_none(
                    matched_record.get("toxicologicalEffect")
                ),
                message="Matched ToxVal record did not expose a comparable numeric endpoint/value pair.",
            )

        predicted_value = _predicted_value(observed_value, case)
        evidence = synthesizer.synthesize(
            [
                PredictiveStepResult(
                    service="reference_panel",
                    status="success",
                    scenario="live_concordance",
                    label=str(observed_endpoint),
                    request=PredictiveRequest(chemical_identifier=case.dtxsid),
                    prediction={
                        "endpoint": observed_endpoint,
                        "value": predicted_value,
                    },
                    metadata={
                        "referencePanelCase": case.case_id,
                        "predictionMode": case.prediction_mode,
                    },
                )
            ],
            resolution=_resolution_for_case(case, matched_record),
            ctx_bundle=CtxDataBundle(
                dtxsid=case.dtxsid,
                scenarios=["live_concordance"],
                hazard={"toxval": [matched_record]},
                data_gaps=[],
            ),
            concordance_threshold=threshold,
        )
        actual_status = evidence.assessment["observedConcordance"]["status"]
        result = "pass" if actual_status == case.expected_status else "fail"
        message = None
        if result != "pass":
            message = (
                "Observed concordance drifted from the curated expectation. "
                f"Expected `{case.expected_status}` but got `{actual_status}`."
            )
        elif evidence.guardrail_events:
            message = evidence.guardrail_events[0].message

        return LiveConcordanceCaseResult(
            case_id=case.case_id,
            dtxsid=case.dtxsid,
            result=result,
            expected_observed_concordance=case.expected_status,
            actual_observed_concordance=actual_status,
            confidence_band=evidence.confidence_band,
            matched_effect=_string_or_none(
                synthesizer._pick_observed_endpoint(matched_record)
            ),
            source=_string_or_none(matched_record.get("source")),
            toxval_type=_string_or_none(matched_record.get("toxvalType")),
            toxval_subtype=_string_or_none(matched_record.get("toxvalSubtype")),
            observed_value=observed_value,
            predicted_value=predicted_value,
            guardrail_codes=[
                event.code for event in evidence.guardrail_events if event.code
            ],
            message=message,
        )
    except Exception as exc:  # pragma: no cover - defensive live-report envelope
        return LiveConcordanceCaseResult(
            case_id=case.case_id,
            dtxsid=case.dtxsid,
            result="error",
            expected_observed_concordance=case.expected_status,
            message=str(exc),
        )


def _build_panel_summary(
    case_results: Iterable[LiveConcordanceCaseResult],
) -> LiveConcordancePanelSummary:
    results = list(case_results)
    expected_counts = Counter(item.expected_observed_concordance for item in results)
    actual_counts = Counter(
        item.actual_observed_concordance
        for item in results
        if item.actual_observed_concordance
    )
    passed_cases = sum(1 for item in results if item.result == "pass")
    failed_cases = sum(1 for item in results if item.result == "fail")
    error_cases = sum(1 for item in results if item.result == "error")
    return LiveConcordancePanelSummary(
        total_cases=len(results),
        passed_cases=passed_cases,
        failed_cases=failed_cases,
        error_cases=error_cases,
        expected_status_counts=dict(expected_counts),
        actual_status_counts=dict(actual_counts),
        all_cases_passed=failed_cases == 0 and error_cases == 0,
    )


def _select_toxval_record(
    records: Sequence[Dict[str, Any]], case: LiveConcordancePanelCase
) -> Optional[Dict[str, Any]]:
    for record in records:
        if case.source_contains and not _contains(
            record.get("source"), case.source_contains
        ):
            continue
        if case.toxval_type and _normalize_text(
            record.get("toxvalType")
        ) != _normalize_text(case.toxval_type):
            continue
        if case.toxval_subtype and _normalize_text(
            record.get("toxvalSubtype")
        ) != _normalize_text(case.toxval_subtype):
            continue
        if case.effect_contains and not _contains(
            record.get("toxicologicalEffect"), case.effect_contains
        ):
            continue
        return record
    return None


def _predicted_value(observed_value: float, case: LiveConcordancePanelCase) -> float:
    if case.prediction_mode == "offset":
        return observed_value + case.offset
    return observed_value


def _resolution_for_case(
    case: LiveConcordancePanelCase, matched_record: Dict[str, Any]
) -> IdentifierResolution:
    return IdentifierResolution(
        input_identifier=case.dtxsid,
        input_type="dtxsid",
        dtxsid=case.dtxsid,
        matched_record={"dtxsid": case.dtxsid},
        detail_record={"dtxsid": case.dtxsid},
        preferred_name=_string_or_none(matched_record.get("preferredName")),
        casrn=_string_or_none(matched_record.get("casrn")),
    )


def _contains(value: Any, needle: str) -> bool:
    normalized_value = _normalize_text(value)
    normalized_needle = _normalize_text(needle)
    return bool(
        normalized_value and normalized_needle and normalized_needle in normalized_value
    )


def _normalize_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().lower()
    return text or None


def _string_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
