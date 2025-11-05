from __future__ import annotations

import json
from dataclasses import is_dataclass, asdict
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence
from uuid import uuid4

from .ctx_data import CtxDataAssembler, CtxDataAssemblyError
from .identifiers import IdentifierResolver, IdentifierResolutionError
from .models import (
    CtxDataBundle,
    GuardrailEvent,
    IdentifierResolution,
    EvidenceSynthesis,
    MetadataTrace,
    PredictiveRunResult,
    PredictiveStepResult,
    PredictiveTask,
)
from .predictive import PredictiveCoordinator
from .evidence import EvidenceSynthesizer
from .audit import AuditBundleStore
from .utils import sanitize_metadata


def _serialize(obj: Any) -> Any:
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, (list, tuple)):
        return [_serialize(item) for item in obj]
    if isinstance(obj, dict):
        return {key: _serialize(val) for key, val in obj.items()}
    return obj


class GenRAOrchestrator:
    """Controller that ties identifier resolution, CTX data staging, and predictive runs."""

    def __init__(
        self,
        *,
        identifier_resolver: IdentifierResolver,
        ctx_data_assembler: CtxDataAssembler,
        predictive_coordinator: PredictiveCoordinator,
        persistence_dir: Optional[Path] = None,
        clock: Callable[[], str] = lambda: None,
        evidence_synthesizer: Optional[EvidenceSynthesizer] = None,
    ) -> None:
        self.identifier_resolver = identifier_resolver
        self.ctx_data_assembler = ctx_data_assembler
        self.predictive_coordinator = predictive_coordinator
        self.bundle_store = AuditBundleStore(persistence_dir) if persistence_dir else None
        self._clock = clock
        self.evidence_synthesizer = evidence_synthesizer or EvidenceSynthesizer()

    def run_workflow(
        self,
        *,
        target_identifier: str,
        identifier_type: Optional[str] = None,
        scenarios: Optional[Sequence[str]] = None,
        predictive_plan: Iterable[PredictiveTask],
        workflow_run_id: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        run_id = workflow_run_id or str(uuid4())
        options = options or {}
        guardrails: List[GuardrailEvent] = []
        timeline: List[Dict[str, Any]] = []

        resolution: IdentifierResolution
        try:
            resolution = self.identifier_resolver.resolve(target_identifier, identifier_type)
            timeline.append(self._timeline_entry("NormalizeIdentifier", resolution.trace))
        except IdentifierResolutionError as exc:
            guardrails.append(
                GuardrailEvent(
                    stage="NormalizeIdentifier",
                    component="IdentifierResolver",
                    status="denied",
                    code="IDENTIFIER_NOT_RESOLVED",
                    message=str(exc),
                    confidence=None,
                    timestamp=self._clock() or "",
                    metadata={},
                )
            )
            return self._assemble_bundle(
                run_id=run_id,
                resolution=None,
                ctx_bundle=None,
                predictive_result=None,
                guardrails=guardrails,
                timeline=timeline,
                scenarios=list(scenarios or []),
                options=options,
                status="denied",
            )

        ctx_bundle: CtxDataBundle
        try:
            ctx_bundle = self.ctx_data_assembler.assemble(
                resolution.dtxsid,
                scenarios=scenarios,
            )
            timeline.append(self._timeline_entry("AssembleCtxData", ctx_bundle.trace))
        except CtxDataAssemblyError as exc:
            guardrails.append(
                GuardrailEvent(
                    stage="AssembleCtxData",
                    component="CtxDataAssembler",
                    status="error",
                    code="CTX_DATA_UNAVAILABLE",
                    message=str(exc),
                    confidence=None,
                    timestamp=self._clock() or "",
                    metadata={},
                )
            )
            return self._assemble_bundle(
                run_id=run_id,
                resolution=resolution,
                ctx_bundle=None,
                predictive_result=None,
                guardrails=guardrails,
                timeline=timeline,
                scenarios=list(scenarios or []),
                options=options,
                status="error",
            )

        predictive_result: PredictiveRunResult = self.predictive_coordinator.run(
            predictive_plan,
            require_ad_clearance=options.get("requireAdClearance"),
        )
        guardrails.extend(predictive_result.guardrails)
        timeline.append(
            {
                "stage": "RunPredictiveModels",
                "metadata": [self._result_metadata(step) for step in predictive_result.results],
            }
        )

        status = "success" if predictive_result.succeeded else "error"
        evidence = self.evidence_synthesizer.synthesize(predictive_result.results)

        bundle = self._assemble_bundle(
            run_id=run_id,
            resolution=resolution,
            ctx_bundle=ctx_bundle,
            predictive_result=predictive_result,
            evidence=evidence,
            guardrails=guardrails,
            timeline=timeline,
            scenarios=list(scenarios or []),
            options=options,
            status=status,
        )
        storage = self._persist_bundle(
            bundle,
            ctx_bundle=ctx_bundle,
            predictive_result=predictive_result,
            evidence=evidence,
        )
        if storage:
            bundle["storage"] = storage
        return bundle

    # Internal helpers -----------------------------------------------------

    def _timeline_entry(self, stage: str, trace: Sequence[MetadataTrace]) -> Dict[str, Any]:
        return {
            "stage": stage,
            "metadata": [_serialize(item) for item in trace],
        }

    def _result_metadata(self, step: PredictiveStepResult) -> Dict[str, Any]:
        payload = {
            "service": step.service,
            "status": step.status,
            "scenario": step.scenario,
            "label": step.label,
            "metadata": step.metadata,
        }
        if step.ad:
            payload["ad"] = step.ad.model_dump()
        return payload

    def _assemble_bundle(
        self,
        *,
        run_id: str,
        resolution: Optional[IdentifierResolution],
        ctx_bundle: Optional[CtxDataBundle],
        predictive_result: Optional[PredictiveRunResult],
        evidence: Optional[EvidenceSynthesis],
        guardrails: Sequence[GuardrailEvent],
        timeline: Sequence[Dict[str, Any]],
        scenarios: List[str],
        options: Dict[str, Any],
        status: str,
    ) -> Dict[str, Any]:
        bundle: Dict[str, Any] = {
            "bundleVersion": "0.1",
            "workflowRunId": run_id,
            "status": status,
            "scenarios": scenarios,
            "options": options,
            "guardrails": [_serialize(item) for item in guardrails],
            "timeline": timeline,
        }

        if resolution:
            bundle["target"] = {
                "dtxsid": resolution.dtxsid,
                "inputIdentifier": {
                    "value": resolution.input_identifier,
                    "type": resolution.input_type,
                },
                "preferredName": resolution.preferred_name,
                "casrn": resolution.casrn,
                "synonyms": resolution.synonyms,
                "warnings": resolution.warnings,
            }

        if ctx_bundle:
            bundle["ctxData"] = {
                "hazard": ctx_bundle.hazard,
                "exposure": ctx_bundle.exposure,
                "cheminformatics": ctx_bundle.cheminformatics,
                "dataGaps": ctx_bundle.data_gaps,
            }

        if predictive_result:
            bundle["predictive"] = {
                "results": [
                    {
                        "service": step.service,
                        "status": step.status,
                        "scenario": step.scenario,
                        "label": step.label,
                        "request": step.request.model_dump(),
                        "ad": step.ad.model_dump() if step.ad else None,
                        "prediction": step.prediction,
                        "metadata": sanitize_metadata(step.metadata),
                        "error": step.error,
                    }
                    for step in predictive_result.results
                ],
            }

        if evidence:
            bundle["evidence"] = {
                "confidenceBand": evidence.confidence_band,
                "scores": evidence.scores.model_dump(),
                "narrative": evidence.narrative,
                "recommendedActions": evidence.recommended_actions,
            }

        return bundle

    def _persist_bundle(
        self,
        bundle: Dict[str, Any],
        *,
        ctx_bundle: Optional[CtxDataBundle],
        predictive_result: Optional[PredictiveRunResult],
        evidence: Optional[EvidenceSynthesis],
    ) -> Optional[Dict[str, Any]]:
        if not self.bundle_store:
            return None
        attachments: Dict[str, str] = {}
        if ctx_bundle:
            attachments["ctx_data.json"] = json.dumps(_serialize(ctx_bundle), indent=2, sort_keys=True)
        if predictive_result:
            attachments["predictive_results.json"] = json.dumps(
                _serialize(predictive_result),
                indent=2,
                sort_keys=True,
            )
        if evidence:
            attachments["evidence.json"] = json.dumps(_serialize(evidence), indent=2, sort_keys=True)
        return self.bundle_store.save(bundle, attachments=attachments)
