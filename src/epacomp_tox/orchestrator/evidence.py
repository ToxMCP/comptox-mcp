from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, List, Optional

from .models import (
    CtxDataBundle,
    EvidenceScore,
    EvidenceSynthesis,
    GuardrailEvent,
    IdentifierResolution,
    PredictiveStepResult,
)


class EvidenceSynthesizer:
    """Compose structured evidence assessments for orchestrator workflows."""

    def synthesize(
        self,
        results: Iterable[PredictiveStepResult],
        *,
        resolution: Optional[IdentifierResolution] = None,
        ctx_bundle: Optional[CtxDataBundle] = None,
        concordance_threshold: float = 1.0,
    ) -> EvidenceSynthesis:
        steps = list(results)
        successful_steps = [step for step in steps if step.status == "success"]

        identity_assessment = self._identity_integrity(resolution)
        domain_assessment = self._domain_clearance(steps)
        data_assessment = self._data_completeness(ctx_bundle)
        predictive_assessment = self._predictive_support(successful_steps)
        concordance_assessment, concordance_events = self._observed_concordance(
            successful_steps,
            ctx_bundle=ctx_bundle,
            threshold=concordance_threshold,
        )

        assessment = {
            "identityIntegrity": identity_assessment,
            "domainClearance": domain_assessment,
            "dataCompleteness": data_assessment,
            "predictiveSupport": predictive_assessment,
            "observedConcordance": concordance_assessment,
        }
        band = self._resolve_confidence_band(
            assessment=assessment,
            successful_steps=successful_steps,
        )
        narrative = self._build_narrative(band=band, assessment=assessment)

        return EvidenceSynthesis(
            confidence_band=band,
            scores=self._legacy_scores(successful_steps),
            assessment=assessment,
            narrative=narrative,
            recommended_actions=self._recommended_actions(
                band=band,
                assessment=assessment,
                concordance_events=concordance_events,
            ),
            guardrail_events=concordance_events,
        )

    def _identity_integrity(
        self, resolution: Optional[IdentifierResolution]
    ) -> dict[str, Any]:
        if resolution is None:
            return {
                "status": "unavailable",
                "summary": "No resolved target identity was available for assessment.",
                "details": {"resolutionStatus": "not_found"},
            }
        if resolution.resolution_status != "exact":
            return {
                "status": "limited",
                "summary": "Target identity required fallback resolution and should be reviewed.",
                "details": {
                    "resolutionStatus": resolution.resolution_status,
                    "searchModeUsed": resolution.search_mode_used,
                    "warnings": resolution.warnings,
                },
            }
        if resolution.warnings:
            return {
                "status": "limited",
                "summary": "Target identity resolved exactly but surfaced review warnings.",
                "details": {"warnings": resolution.warnings},
            }
        return {
            "status": "robust",
            "summary": "Target identity resolved uniquely through an exact match.",
            "details": {
                "resolutionStatus": resolution.resolution_status,
                "searchModeUsed": resolution.search_mode_used,
            },
        }

    def _domain_clearance(self, steps: List[PredictiveStepResult]) -> dict[str, Any]:
        if not steps:
            return {
                "status": "unavailable",
                "summary": "No predictive tasks were available for domain assessment.",
                "details": {"successfulSteps": 0},
            }
        denied_or_warn = [
            step
            for step in steps
            if step.status in {"denied", "error"}
            or (step.ad is not None and not step.ad.in_domain)
        ]
        if len(denied_or_warn) == len(steps):
            return {
                "status": "unavailable",
                "summary": "Every predictive step failed or fell outside its applicability domain.",
                "details": {
                    "successfulSteps": 0,
                    "flaggedServices": [step.service for step in denied_or_warn],
                },
            }
        if denied_or_warn:
            return {
                "status": "limited",
                "summary": "At least one predictive step carried an AD warning or denial.",
                "details": {
                    "flaggedServices": [step.service for step in denied_or_warn],
                    "successfulSteps": len(
                        [step for step in steps if step.status == "success"]
                    ),
                },
            }
        return {
            "status": "robust",
            "summary": "All predictive steps that ran were inside domain.",
            "details": {
                "successfulSteps": len(
                    [step for step in steps if step.status == "success"]
                )
            },
        }

    def _data_completeness(self, ctx_bundle: Optional[CtxDataBundle]) -> dict[str, Any]:
        if ctx_bundle is None:
            return {
                "status": "unavailable",
                "summary": "No staged CTX data bundle was available for evidence completeness checks.",
                "details": {"criticalGaps": ["ctx_bundle"]},
            }
        gaps = ctx_bundle.data_gaps
        critical_gaps = [
            gap
            for gap in gaps
            if gap.startswith("hazard:") or gap in {"exposure:httk", "ctx_bundle"}
        ]
        if critical_gaps:
            return {
                "status": "unavailable",
                "summary": "Critical CTX evidence slices were missing.",
                "details": {"criticalGaps": critical_gaps, "allGaps": gaps},
            }
        if gaps:
            return {
                "status": "limited",
                "summary": "Some CTX evidence slices were missing or empty.",
                "details": {"allGaps": gaps},
            }
        return {
            "status": "robust",
            "summary": "Required CTX context slices were present.",
            "details": {"allGaps": []},
        }

    def _predictive_support(
        self, successful_steps: List[PredictiveStepResult]
    ) -> dict[str, Any]:
        if not successful_steps:
            return {
                "status": "unavailable",
                "summary": "No successful predictive results were available for support assessment.",
                "details": {"successfulSteps": 0},
            }
        agreement_values = [
            self._extract_score(step, "predictiveAgreement")
            for step in successful_steps
            if self._extract_score(step, "predictiveAgreement") > 0
        ]
        mean_agreement = (
            sum(agreement_values) / len(agreement_values) if agreement_values else 0.0
        )
        if len(successful_steps) >= 2 and mean_agreement >= 0.8:
            status = "robust"
            summary = (
                "Multiple successful predictive results provided consistent support."
            )
        else:
            status = "limited"
            summary = "Predictive support was present but sparse or only moderately consistent."
        return {
            "status": status,
            "summary": summary,
            "details": {
                "successfulSteps": len(successful_steps),
                "meanPredictiveAgreement": round(mean_agreement, 3),
            },
        }

    def _observed_concordance(
        self,
        successful_steps: List[PredictiveStepResult],
        *,
        ctx_bundle: Optional[CtxDataBundle],
        threshold: float,
    ) -> tuple[dict[str, Any], List[GuardrailEvent]]:
        if ctx_bundle is None:
            return (
                {
                    "status": "unavailable",
                    "summary": "No staged hazard evidence was available for concordance checks.",
                    "details": {"comparisons": 0, "mismatches": 0},
                },
                [],
            )

        hazard_records = [
            record
            for records in ctx_bundle.hazard.values()
            for record in records
            if isinstance(record, dict)
        ]
        comparisons = 0
        mismatches: List[GuardrailEvent] = []
        for step in successful_steps:
            comparison = self._compare_step_to_hazard(
                step,
                hazard_records=hazard_records,
                threshold=threshold,
            )
            if comparison is None:
                continue
            comparisons += 1
            if comparison["status"] == "mismatch":
                mismatches.append(
                    GuardrailEvent(
                        stage="EvidenceSynthesis",
                        component="ConcordanceCheck",
                        status="warning",
                        code="PREDICTION_OBSERVATION_MISMATCH",
                        message=comparison["message"],
                        confidence=None,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        metadata=comparison["metadata"],
                    )
                )

        if comparisons == 0:
            return (
                {
                    "status": "limited",
                    "summary": "No comparable observed hazard records were available for concordance checks.",
                    "details": {"comparisons": 0, "mismatches": 0},
                },
                mismatches,
            )
        if mismatches:
            return (
                {
                    "status": "limited",
                    "summary": "At least one prediction disagreed with comparable observed hazard data.",
                    "details": {
                        "comparisons": comparisons,
                        "mismatches": len(mismatches),
                    },
                },
                mismatches,
            )
        return (
            {
                "status": "robust",
                "summary": "Comparable observed hazard records were concordant with successful predictions.",
                "details": {"comparisons": comparisons, "mismatches": 0},
            },
            mismatches,
        )

    def _compare_step_to_hazard(
        self,
        step: PredictiveStepResult,
        *,
        hazard_records: List[dict[str, Any]],
        threshold: float,
    ) -> Optional[dict[str, Any]]:
        if not step.prediction:
            return None
        predicted_endpoint = self._normalize_text(
            self._pick_value(step.prediction, "endpoint", "effect", "label", "metric")
            or step.label
        )
        predicted_value = self._pick_value(
            step.prediction, "value", "prediction", "estimate", "score"
        )
        if predicted_endpoint is None or predicted_value is None:
            return None

        for record in hazard_records:
            observed_endpoint = self._normalize_text(
                self._pick_value(record, "endpoint", "effect", "assay")
            )
            if not observed_endpoint or observed_endpoint != predicted_endpoint:
                continue

            observed_value = self._pick_value(record, "value", "score", "ac50")
            if observed_value is None:
                continue

            predicted_numeric = self._coerce_number(predicted_value)
            observed_numeric = self._coerce_number(observed_value)
            if predicted_numeric is not None and observed_numeric is not None:
                if abs(predicted_numeric - observed_numeric) > threshold:
                    return {
                        "status": "mismatch",
                        "message": (
                            f"Prediction for endpoint '{predicted_endpoint}' diverged "
                            f"from observed value by more than {threshold} log unit(s)."
                        ),
                        "metadata": {
                            "service": step.service,
                            "endpoint": predicted_endpoint,
                            "predictedValue": predicted_numeric,
                            "observedValue": observed_numeric,
                            "threshold": threshold,
                        },
                    }
                return {"status": "match", "message": "", "metadata": {}}

            if self._normalize_text(str(predicted_value)) != self._normalize_text(
                str(observed_value)
            ):
                return {
                    "status": "mismatch",
                    "message": (
                        f"Prediction for endpoint '{predicted_endpoint}' disagreed with "
                        "the comparable observed categorical outcome."
                    ),
                    "metadata": {
                        "service": step.service,
                        "endpoint": predicted_endpoint,
                        "predictedValue": str(predicted_value),
                        "observedValue": str(observed_value),
                    },
                }
            return {"status": "match", "message": "", "metadata": {}}

        return None

    def _resolve_confidence_band(
        self,
        *,
        assessment: dict[str, dict[str, Any]],
        successful_steps: List[PredictiveStepResult],
    ) -> str:
        if not successful_steps:
            return "Unavailable"
        if assessment["identityIntegrity"]["status"] == "unavailable":
            return "Unavailable"
        if assessment["dataCompleteness"]["status"] == "unavailable":
            return "Unavailable"
        if assessment["domainClearance"]["status"] == "unavailable":
            return "Unavailable"
        if any(
            assessment[name]["status"] == "limited"
            for name in (
                "identityIntegrity",
                "domainClearance",
                "dataCompleteness",
                "predictiveSupport",
                "observedConcordance",
            )
        ):
            return "Limited"
        return "Robust"

    def _legacy_scores(
        self, successful_steps: List[PredictiveStepResult]
    ) -> Optional[EvidenceScore]:
        if not successful_steps:
            return None
        analogue_scores = [
            self._extract_score(step, "analogueCoverage") for step in successful_steps
        ]
        quality_scores = [
            self._extract_score(step, "evidenceQuality") for step in successful_steps
        ]
        agreement_scores = [
            self._extract_score(step, "predictiveAgreement")
            for step in successful_steps
        ]
        return EvidenceScore(
            analogue_coverage=sum(analogue_scores) / len(analogue_scores),
            evidence_quality=sum(quality_scores) / len(quality_scores),
            predictive_agreement=sum(agreement_scores) / len(agreement_scores),
        )

    def _extract_score(self, step: PredictiveStepResult, key: str) -> float:
        metadata = step.metadata or {}
        value = metadata.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        if key == "predictiveAgreement" and step.prediction:
            fallback = step.prediction.get("confidence")
            if isinstance(fallback, (int, float)):
                return float(fallback)
        return 0.0

    def _build_narrative(
        self, *, band: str, assessment: dict[str, dict[str, Any]]
    ) -> str:
        return (
            f"Confidence band: {band}. "
            f"Identity={assessment['identityIntegrity']['status']}, "
            f"domain={assessment['domainClearance']['status']}, "
            f"data={assessment['dataCompleteness']['status']}, "
            f"predictive={assessment['predictiveSupport']['status']}, "
            f"concordance={assessment['observedConcordance']['status']}."
        )

    def _recommended_actions(
        self,
        *,
        band: str,
        assessment: dict[str, dict[str, Any]],
        concordance_events: List[GuardrailEvent],
    ) -> List[str]:
        if band == "Robust":
            return [
                "Proceed with structured evidence handoff.",
                "Document the supporting rationale in the audit bundle.",
            ]
        actions: List[str] = []
        if assessment["identityIntegrity"]["status"] != "robust":
            actions.append("Review and confirm the resolved chemical identity.")
        if assessment["domainClearance"]["status"] != "robust":
            actions.append(
                "Revisit applicability-domain constraints before relying on predictions."
            )
        if assessment["dataCompleteness"]["status"] != "robust":
            actions.append("Acquire or recover the missing CTX evidence slices.")
        if concordance_events:
            actions.append(
                "Investigate the prediction-vs-observation mismatch before downstream use."
            )
        if not actions:
            actions.append("Seek SME review before downstream use.")
        return actions

    @staticmethod
    def _pick_value(payload: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in payload and payload[key] is not None:
                return payload[key]
        return None

    @staticmethod
    def _coerce_number(value: Any) -> Optional[float]:
        if isinstance(value, (int, float)):
            return float(value)
        return None

    @staticmethod
    def _normalize_text(value: Optional[str]) -> Optional[str]:
        if not value or not isinstance(value, str):
            return None
        return " ".join(value.strip().lower().split())
