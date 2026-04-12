from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from pydantic import BaseModel, Field

from epacomp_tox.predictive.base import PredictiveRequest

from .models import PredictiveTask
from .offline import OFFLINE_SCENARIOS, build_offline_orchestrator

_INTEROP_ATTACHMENT_NAMES = (
    "interop/comptox_evidence_pack.json",
    "interop/aop_linkage_summary.json",
    "interop/pbpk_context_bundle.json",
)


class ScenarioValidationResult(BaseModel):
    """Scientific-validation outcome for one orchestrator scenario run."""

    scenario: str
    workflow_run_id: str
    status: str
    confidence_band: Optional[str] = None
    predictive_services: List[str] = Field(default_factory=list)
    in_domain_services: List[str] = Field(default_factory=list)
    guardrail_count: int = 0
    guardrail_codes: List[str] = Field(default_factory=list)
    data_gaps: List[str] = Field(default_factory=list)
    assessment_statuses: Dict[str, str] = Field(default_factory=dict)
    interop_attachment_coverage: Dict[str, bool] = Field(default_factory=dict)
    analogue_count: int = 0
    bundle_path: Optional[str] = None
    bundle_checksum: Optional[str] = None
    recommended_actions: List[str] = Field(default_factory=list)


class ValidationSummary(BaseModel):
    """Aggregated metrics for a scientific-validation suite run."""

    total_scenarios: int
    status_counts: Dict[str, int] = Field(default_factory=dict)
    confidence_band_counts: Dict[str, int] = Field(default_factory=dict)
    assessment_status_counts: Dict[str, Dict[str, int]] = Field(default_factory=dict)
    interop_attachment_coverage: Dict[str, int] = Field(default_factory=dict)
    total_guardrail_events: int = 0
    scenarios_with_data_gaps: int = 0
    scenarios_with_complete_interop: int = 0
    all_scenarios_succeeded: bool = False
    all_identity_robust: bool = False
    all_domain_clear: bool = False
    all_data_complete: bool = False


class ScientificValidationReport(BaseModel):
    """Portable scientific-validation report for orchestrator scenario suites."""

    report_version: str = "0.1"
    generated_at: str
    orchestrator_mode: str
    target_identifier: Dict[str, str]
    scenarios: List[ScenarioValidationResult]
    summary: ValidationSummary


def generate_offline_validation_report(
    *,
    persistence_dir: Path,
    scenarios: Optional[Sequence[str]] = None,
    target_identifier: str = "50-00-0",
    identifier_type: str = "casrn",
) -> ScientificValidationReport:
    """Run the offline orchestrator scenarios and summarize scientific-quality signals."""

    selected_scenarios = list(scenarios or OFFLINE_SCENARIOS)
    unknown = sorted(set(selected_scenarios) - set(OFFLINE_SCENARIOS))
    if unknown:
        raise ValueError(
            f"Unsupported offline scenarios requested: {', '.join(unknown)}"
        )

    orchestrator = build_offline_orchestrator(persistence_dir=persistence_dir)
    scenario_results: List[ScenarioValidationResult] = []

    for scenario in selected_scenarios:
        bundle = orchestrator.run_workflow(
            target_identifier=target_identifier,
            identifier_type=identifier_type,
            scenarios=[scenario],
            predictive_plan=[
                PredictiveTask(
                    service="offline_genra",
                    scenario=scenario,
                    request=PredictiveRequest(chemical_identifier="DTXSID0000001"),
                )
            ],
        )
        scenario_results.append(_scenario_validation_result(bundle, scenario=scenario))

    return ScientificValidationReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        orchestrator_mode="offline",
        target_identifier={"value": target_identifier, "type": identifier_type},
        scenarios=scenario_results,
        summary=_validation_summary(scenario_results),
    )


def render_validation_report_markdown(report: ScientificValidationReport) -> str:
    """Render a concise Markdown summary for human review."""

    summary = report.summary
    lines = [
        "# Scientific Validation Report",
        "",
        f"- Generated: `{report.generated_at}`",
        f"- Mode: `{report.orchestrator_mode}`",
        (
            f"- Target identifier: `{report.target_identifier['value']}` "
            f"(`{report.target_identifier['type']}`)"
        ),
        f"- Scenarios: `{summary.total_scenarios}`",
        f"- All scenarios succeeded: `{summary.all_scenarios_succeeded}`",
        f"- Complete interop coverage: `{summary.scenarios_with_complete_interop}/{summary.total_scenarios}`",
        "",
        "## Summary",
        "",
        f"- Status counts: `{summary.status_counts}`",
        f"- Confidence bands: `{summary.confidence_band_counts}`",
        f"- Guardrail events: `{summary.total_guardrail_events}`",
        f"- Scenarios with data gaps: `{summary.scenarios_with_data_gaps}`",
        "",
        "## Scenario Results",
        "",
        "| Scenario | Status | Confidence Band | Guardrails | Data Gaps | Interop |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    for result in report.scenarios:
        interop_ok = all(result.interop_attachment_coverage.values())
        lines.append(
            "| "
            f"{result.scenario} | "
            f"{result.status} | "
            f"{result.confidence_band or 'n/a'} | "
            f"{result.guardrail_count} | "
            f"{len(result.data_gaps)} | "
            f"{'complete' if interop_ok else 'partial'} |"
        )

    lines.extend(
        [
            "",
            "## Assessment Rollup",
            "",
        ]
    )

    for key, counts in sorted(summary.assessment_status_counts.items()):
        lines.append(f"- `{key}`: `{counts}`")

    lines.extend(
        [
            "",
            "## Interop Attachment Coverage",
            "",
        ]
    )
    for name, count in sorted(summary.interop_attachment_coverage.items()):
        lines.append(f"- `{name}`: `{count}/{summary.total_scenarios}`")

    return "\n".join(lines)


def _scenario_validation_result(
    bundle: Dict[str, object], *, scenario: str
) -> ScenarioValidationResult:
    predictive_results = (bundle.get("predictive") or {}).get("results", [])  # type: ignore[union-attr]
    evidence = bundle.get("evidence") or {}
    assessment = evidence.get("assessment") or {}
    storage = bundle.get("storage") or {}
    attachment_names = {
        item.get("name")
        for item in storage.get("attachments", [])
        if isinstance(item, dict)
    }

    predictive_services = [
        step.get("service")
        for step in predictive_results
        if isinstance(step, dict) and isinstance(step.get("service"), str)
    ]
    in_domain_services = [
        step.get("service")
        for step in predictive_results
        if isinstance(step, dict)
        and isinstance(step.get("service"), str)
        and isinstance(step.get("ad"), dict)
        and step["ad"].get("in_domain") is True
    ]
    guardrail_codes = [
        item.get("code")
        for item in bundle.get("guardrails", [])
        if isinstance(item, dict) and isinstance(item.get("code"), str)
    ]

    analogue_provenance = bundle.get("analogueProvenance") or {}
    return ScenarioValidationResult(
        scenario=scenario,
        workflow_run_id=str(bundle.get("workflowRunId") or ""),
        status=str(bundle.get("status") or "unknown"),
        confidence_band=evidence.get("confidenceBand"),
        predictive_services=predictive_services,
        in_domain_services=in_domain_services,
        guardrail_count=len(bundle.get("guardrails", [])),
        guardrail_codes=guardrail_codes,
        data_gaps=list(((bundle.get("ctxData") or {}).get("dataGaps") or [])),
        assessment_statuses={
            key: str(value.get("status") or "unavailable")
            for key, value in assessment.items()
            if isinstance(value, dict)
        },
        interop_attachment_coverage={
            name: name in attachment_names for name in _INTEROP_ATTACHMENT_NAMES
        },
        analogue_count=int(analogue_provenance.get("resolvedAnalogueCount") or 0),
        bundle_path=storage.get("bundlePath"),
        bundle_checksum=storage.get("bundleChecksum"),
        recommended_actions=list(evidence.get("recommendedActions") or []),
    )


def _validation_summary(
    scenario_results: Iterable[ScenarioValidationResult],
) -> ValidationSummary:
    results = list(scenario_results)
    status_counts = Counter(result.status for result in results)
    confidence_bands = Counter(
        result.confidence_band for result in results if result.confidence_band
    )

    assessment_rollup: Dict[str, Counter[str]] = defaultdict(Counter)
    interop_coverage = Counter[str]()

    for result in results:
        for key, status in result.assessment_statuses.items():
            assessment_rollup[key][status] += 1
        for name, present in result.interop_attachment_coverage.items():
            if present:
                interop_coverage[name] += 1

    total = len(results)
    return ValidationSummary(
        total_scenarios=total,
        status_counts=dict(status_counts),
        confidence_band_counts=dict(confidence_bands),
        assessment_status_counts={
            key: dict(counter) for key, counter in sorted(assessment_rollup.items())
        },
        interop_attachment_coverage=dict(interop_coverage),
        total_guardrail_events=sum(result.guardrail_count for result in results),
        scenarios_with_data_gaps=sum(1 for result in results if result.data_gaps),
        scenarios_with_complete_interop=sum(
            1
            for result in results
            if result.interop_attachment_coverage
            and all(result.interop_attachment_coverage.values())
        ),
        all_scenarios_succeeded=all(result.status == "success" for result in results),
        all_identity_robust=_all_assessment_status(
            results, "identityIntegrity", "robust"
        ),
        all_domain_clear=_all_assessment_status(results, "domainClearance", "robust"),
        all_data_complete=_all_assessment_status(results, "dataCompleteness", "robust"),
    )


def _all_assessment_status(
    results: Sequence[ScenarioValidationResult], key: str, expected: str
) -> bool:
    return bool(results) and all(
        result.assessment_statuses.get(key) == expected for result in results
    )
