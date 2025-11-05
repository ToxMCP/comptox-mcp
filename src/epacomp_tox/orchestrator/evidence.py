from __future__ import annotations

from typing import Iterable, List

from epacomp_tox.predictive import PredictiveResponse

from .models import EvidenceScore, EvidenceSynthesis, PredictiveStepResult


class EvidenceSynthesizer:
    """Compose GenRA evidence grades and narrative summaries."""

    def synthesize(self, results: Iterable[PredictiveStepResult]) -> EvidenceSynthesis:
        steps: List[PredictiveStepResult] = [step for step in results if step.status == "success"]
        if not steps:
            return EvidenceSynthesis(
                confidence_band="Unavailable",
                scores=EvidenceScore(analogue_coverage=0.0, evidence_quality=0.0, predictive_agreement=0.0),
                narrative="No successful predictive results available for synthesis.",
                recommended_actions=["Review applicability domain denials", "Re-run orchestration after addressing guardrail failures"],
            )

        analogue_scores = [self._extract_score(step, "analogueCoverage") for step in steps]
        quality_scores = [self._extract_score(step, "evidenceQuality") for step in steps]
        agreement_scores = [self._extract_score(step, "predictiveAgreement") for step in steps]

        coverage = sum(analogue_scores) / len(analogue_scores)
        evidence_quality = sum(quality_scores) / len(quality_scores)
        predictive_agreement = sum(agreement_scores) / len(agreement_scores)

        band = self._resolve_confidence_band(coverage, evidence_quality, predictive_agreement)
        narrative = self._build_narrative(band, coverage, evidence_quality, predictive_agreement)

        return EvidenceSynthesis(
            confidence_band=band,
            scores=EvidenceScore(
                analogue_coverage=coverage,
                evidence_quality=evidence_quality,
                predictive_agreement=predictive_agreement,
            ),
            narrative=narrative,
            recommended_actions=self._recommended_actions(band),
        )

    def _extract_score(self, step: PredictiveStepResult, key: str) -> float:
        metadata = step.metadata or {}
        value = metadata.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        if key == "predictiveAgreement" and step.prediction:
            return float(step.prediction.get("confidence", 0.0))
        return 0.0

    def _resolve_confidence_band(self, coverage: float, quality: float, agreement: float) -> str:
        if min(coverage, quality, agreement) >= 0.8:
            return "Robust"
        if min(coverage, quality, agreement) >= 0.5:
            return "Limited"
        return "Unavailable"

    def _build_narrative(self, band: str, coverage: float, quality: float, agreement: float) -> str:
        return (
            f"Confidence band: {band}. Analogue coverage={coverage:.2f}, "
            f"evidence quality={quality:.2f}, predictive agreement={agreement:.2f}."
        )

    def _recommended_actions(self, band: str) -> List[str]:
        if band == "Robust":
            return ["Proceed with automated dossier generation", "Document rationale for regulatory submission"]
        if band == "Limited":
            return ["Seek SME review", "Augment analogue set or supporting evidence"]
        return ["Address guardrail failures", "Acquire additional data or adjust predictor inputs"]
