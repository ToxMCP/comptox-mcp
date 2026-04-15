from __future__ import annotations

import json
import os
import sys
from copy import deepcopy
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence
from uuid import uuid4

from epacomp_tox.resources.interop import InteropResource

from .audit import AuditBundleStore
from .ctx_data import CtxDataAssembler, CtxDataAssemblyError
from .evidence import EvidenceSynthesizer
from .identifiers import IdentifierResolutionError, IdentifierResolver
from .models import (
    CtxDataBundle,
    EvidenceSynthesis,
    GuardrailEvent,
    IdentifierResolution,
    MetadataTrace,
    PredictiveRunResult,
    PredictiveStepResult,
    PredictiveTask,
)
from .predictive import PredictiveCoordinator
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


def _resolve_runtime_version() -> str:
    """Resolve the installed package version for provenance."""
    for distribution_name in ("epacomp-tox-mcp", "epacomp_tox"):
        try:
            return metadata.version(distribution_name)
        except metadata.PackageNotFoundError:
            continue
    return os.environ.get("EPACOMP_TOX_VERSION", "0.0.0-dev")


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
        interop_resource: Optional[InteropResource] = None,
    ) -> None:
        self.identifier_resolver = identifier_resolver
        self.ctx_data_assembler = ctx_data_assembler
        self.predictive_coordinator = predictive_coordinator
        self.bundle_store = (
            AuditBundleStore(persistence_dir) if persistence_dir else None
        )
        self._clock = clock
        self.evidence_synthesizer = evidence_synthesizer or EvidenceSynthesizer()
        self.interop_resource = interop_resource

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
            resolution = self.identifier_resolver.resolve(
                target_identifier, identifier_type
            )
            timeline.append(
                self._timeline_entry("NormalizeIdentifier", resolution.trace)
            )
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

        prepared_plan = self._prepare_predictive_plan(
            predictive_plan,
            resolution=resolution,
            ctx_bundle=ctx_bundle,
        )
        has_predictive_tasks = bool(list(prepared_plan))
        require_ad_clearance = options.get("requireAdClearance")
        if require_ad_clearance is None:
            require_ad_clearance = has_predictive_tasks
        predictive_result: PredictiveRunResult = self.predictive_coordinator.run(
            prepared_plan,
            require_ad_clearance=require_ad_clearance,
        )
        predictive_result = self._enrich_predictive_result_requests(
            predictive_result,
            resolution=resolution,
            ctx_bundle=ctx_bundle,
        )
        guardrails.extend(predictive_result.guardrails)
        timeline.append(
            {
                "stage": "RunPredictiveModels",
                "metadata": [
                    self._result_metadata(step) for step in predictive_result.results
                ],
            }
        )

        has_denied_guardrail = any(g.status == "denied" for g in guardrails)
        if predictive_result.succeeded:
            status = "success"
        elif has_denied_guardrail:
            status = "denied"
        else:
            status = "error"
        evidence = self.evidence_synthesizer.synthesize(
            predictive_result.results,
            resolution=resolution,
            ctx_bundle=ctx_bundle,
        )
        guardrails.extend(evidence.guardrail_events)

        handoff_attachments = self._build_handoff_attachments(
            resolution=resolution,
            guardrails=guardrails,
        )

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
            handoff_attachments=handoff_attachments,
        )
        if storage:
            bundle["storage"] = storage
        return bundle

    # Internal helpers -----------------------------------------------------

    def _timeline_entry(
        self, stage: str, trace: Sequence[MetadataTrace]
    ) -> Dict[str, Any]:
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
                "mechanisticContext": ctx_bundle.mechanistic_context,
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
            bundle["analogueProvenance"] = self._build_analogue_provenance(
                predictive_result.results
            )

        if evidence:
            bundle["evidence"] = {
                "confidenceBand": evidence.confidence_band,
                "scores": evidence.scores.model_dump() if evidence.scores else None,
                "assessment": evidence.assessment,
                "narrative": evidence.narrative,
                "recommendedActions": evidence.recommended_actions,
            }

        bundle["reviewCheckpoints"] = self._build_review_checkpoints(
            resolution=resolution,
            predictive_result=predictive_result,
        )
        bundle["provenance"] = self._build_provenance(
            run_id=run_id,
            options=options,
            ctx_bundle=ctx_bundle,
            predictive_result=predictive_result,
        )
        return bundle

    def _build_review_checkpoints(
        self,
        resolution: Optional[IdentifierResolution],
        predictive_result: Optional[PredictiveRunResult],
    ) -> List[Dict[str, Any]]:
        """Advisory review checkpoint metadata for workflow governance."""
        checkpoints: List[Dict[str, Any]] = []
        if resolution:
            checkpoints.append(
                {
                    "step": "chemical_id_confirmation",
                    "status": "passed",
                    "required": True,
                }
            )
        if predictive_result:
            has_ad_warning = any(
                step.ad and not step.ad.in_domain for step in predictive_result.results
            )
            ad_status = "required" if has_ad_warning else "passed"
            checkpoints.append(
                {
                    "step": "ad_assessment",
                    "status": ad_status,
                    "required": True,
                }
            )
            checkpoints.append(
                {
                    "step": "final_report",
                    "status": "required",
                    "required": True,
                }
            )
        return checkpoints

    def _build_provenance(
        self,
        *,
        run_id: str,
        options: Dict[str, Any],
        ctx_bundle: Optional[CtxDataBundle],
        predictive_result: Optional[PredictiveRunResult],
    ) -> Dict[str, Any]:
        provenance: Dict[str, Any] = {
            "serverVersion": _resolve_runtime_version(),
            "runtimeEnvironment": {
                "pythonVersion": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                "environment": os.environ.get("TOXMCP_ENVIRONMENT", "unknown"),
            },
            "traceId": options.get("traceId"),
            "createdAt": self._clock() or datetime.now(timezone.utc).isoformat(),
            "upstreamProvenance": {},
        }

        if ctx_bundle:
            provenance["upstreamProvenance"]["ctxData"] = {
                "cacheHit": ctx_bundle.cache_hit,
                "trace": [_serialize(t) for t in ctx_bundle.trace],
            }

        if predictive_result:
            provenance["upstreamProvenance"]["predictive"] = [
                {
                    "service": step.service,
                    "status": step.status,
                    "metadata": sanitize_metadata(step.metadata),
                }
                for step in predictive_result.results
            ]

        return provenance

    def _build_analogue_provenance(
        self, results: Sequence[PredictiveStepResult]
    ) -> Dict[str, Any]:
        resolved_ids: List[str] = []
        seen = set()
        steps: List[Dict[str, Any]] = []

        for step in results:
            analogue_ids = self._extract_analogue_ids(step.request.ad_inputs)
            for analogue_id in analogue_ids:
                if analogue_id not in seen:
                    seen.add(analogue_id)
                    resolved_ids.append(analogue_id)

            mechanistic_context = self._mechanistic_context_from_request(step.request)
            analogue_context = mechanistic_context.get("analogues")
            source = step.metadata.get("analogueIdSource")
            if source is None:
                expert_rule = step.request.ad_inputs.get(
                    "expert_rule"
                ) or step.request.ad_inputs.get("expertRule")
                if isinstance(expert_rule, dict):
                    source = expert_rule.get("analogueIdSource")

            if analogue_ids or source or analogue_context:
                steps.append(
                    {
                        "service": step.service,
                        "status": step.status,
                        "source": source,
                        "analogueIds": analogue_ids,
                        "analogueCount": len(analogue_ids),
                        "mechanisticContextAttached": bool(analogue_context),
                    }
                )

        return {
            "resolvedAnalogueIds": resolved_ids,
            "resolvedAnalogueCount": len(resolved_ids),
            "steps": steps,
        }

    def _persist_bundle(
        self,
        bundle: Dict[str, Any],
        *,
        ctx_bundle: Optional[CtxDataBundle],
        predictive_result: Optional[PredictiveRunResult],
        evidence: Optional[EvidenceSynthesis],
        handoff_attachments: Optional[Dict[str, str]] = None,
    ) -> Optional[Dict[str, Any]]:
        if not self.bundle_store:
            return None
        attachments: Dict[str, str] = {}
        if ctx_bundle:
            attachments["ctx_data.json"] = json.dumps(
                _serialize(ctx_bundle), indent=2, sort_keys=True
            )
        if predictive_result:
            attachments["predictive_results.json"] = json.dumps(
                _serialize(predictive_result),
                indent=2,
                sort_keys=True,
            )
        if evidence:
            attachments["evidence.json"] = json.dumps(
                _serialize(evidence), indent=2, sort_keys=True
            )
        if handoff_attachments:
            attachments.update(handoff_attachments)
        return self.bundle_store.save(bundle, attachments=attachments)

    def _build_handoff_attachments(
        self,
        *,
        resolution: Optional[IdentifierResolution],
        guardrails: List[GuardrailEvent],
    ) -> Optional[Dict[str, str]]:
        if self.interop_resource is None or resolution is None:
            return None
        try:
            evidence_pack = self.interop_resource.assemble_comptox_evidence_pack(
                dtxsid=resolution.dtxsid
            )
            aop_summary = self.interop_resource.build_aop_linkage_summary(
                dtxsid=resolution.dtxsid
            )
            pbpk_bundle = self.interop_resource.build_pbpk_context_bundle(
                dtxsid=resolution.dtxsid
            )
        except Exception as exc:  # pragma: no cover - defensive
            guardrails.append(
                GuardrailEvent(
                    stage="BuildInteropHandoffs",
                    component="InteropResource",
                    status="warning",
                    code="INTEROP_ATTACHMENT_FAILED",
                    message=str(exc),
                    confidence=None,
                    timestamp=self._clock() or "",
                    metadata={},
                )
            )
            return None

        return {
            "interop/comptox_evidence_pack.json": json.dumps(
                evidence_pack, indent=2, sort_keys=True
            ),
            "interop/aop_linkage_summary.json": json.dumps(
                aop_summary, indent=2, sort_keys=True
            ),
            "interop/pbpk_context_bundle.json": json.dumps(
                pbpk_bundle, indent=2, sort_keys=True
            ),
        }

    def _enrich_predictive_result_requests(
        self,
        predictive_result: PredictiveRunResult,
        *,
        resolution: IdentifierResolution,
        ctx_bundle: CtxDataBundle,
    ) -> PredictiveRunResult:
        enriched_results: List[PredictiveStepResult] = []
        for step in predictive_result.results:
            enriched_request = self._merge_mechanistic_context_into_request(
                step.request,
                resolution=resolution,
                ctx_bundle=ctx_bundle,
            )
            enriched_results.append(
                step.model_copy(update={"request": enriched_request})
            )
        return predictive_result.model_copy(update={"results": enriched_results})

    def _prepare_predictive_plan(
        self,
        predictive_plan: Iterable[PredictiveTask],
        *,
        resolution: IdentifierResolution,
        ctx_bundle: CtxDataBundle,
    ) -> List[PredictiveTask]:
        prepared: List[PredictiveTask] = []
        for task in predictive_plan:
            task = self.predictive_coordinator.prepare_task(task)
            request = self._merge_mechanistic_context_into_request(
                task.request,
                resolution=resolution,
                ctx_bundle=ctx_bundle,
            )
            prepared.append(task.model_copy(update={"request": request}))
        return prepared

    def _merge_mechanistic_context_into_request(
        self,
        request,
        *,
        resolution: IdentifierResolution,
        ctx_bundle: CtxDataBundle,
    ):
        target_context = ctx_bundle.mechanistic_context.get("target") or {}
        analogue_ids = self._extract_analogue_ids(request.ad_inputs)
        if not target_context and not analogue_ids:
            return request

        ad_inputs = deepcopy(request.ad_inputs)
        expert_rule = dict(
            ad_inputs.get("expert_rule") or ad_inputs.get("expertRule") or {}
        )
        mechanistic_context = dict(
            expert_rule.get("mechanistic_context")
            or expert_rule.get("mechanisticContext")
            or {}
        )
        if target_context:
            mechanistic_context["target"] = self._merge_mechanistic_mapping(
                mechanistic_context.get("target"),
                target_context,
            )

        if analogue_ids:
            existing_analogues = mechanistic_context.get("analogues") or []
            mechanistic_context["analogues"] = (
                self._merge_analogue_mechanistic_contexts(
                    existing_analogues,
                    analogue_ids,
                    target_dtxsid=resolution.dtxsid,
                )
            )

        if not mechanistic_context:
            return request
        expert_rule["mechanistic_context"] = mechanistic_context
        ad_inputs["expert_rule"] = expert_rule
        return request.model_copy(update={"ad_inputs": ad_inputs})

    def _merge_analogue_mechanistic_contexts(
        self,
        existing_analogues: Any,
        analogue_ids: Sequence[str],
        *,
        target_dtxsid: str,
    ) -> List[Dict[str, Any]]:
        merged: List[Dict[str, Any]] = []
        existing_by_id: Dict[str, Dict[str, Any]] = {}
        if isinstance(existing_analogues, list):
            for index, item in enumerate(existing_analogues):
                analogue_id = self._extract_analogue_id(item, fallback_index=index)
                if not analogue_id:
                    continue
                payload = item if isinstance(item, dict) else {"id": analogue_id}
                existing_by_id[analogue_id] = dict(payload)

        for analogue_id in analogue_ids:
            normalized_id = analogue_id.strip().upper()
            if not normalized_id or normalized_id == target_dtxsid:
                continue
            existing = existing_by_id.pop(normalized_id, None)
            fetched = self.ctx_data_assembler.get_mechanistic_context_slice(
                normalized_id
            )
            if existing:
                merged.append(
                    self._merge_mechanistic_mapping(
                        existing, fetched, analogue_id=normalized_id
                    )
                )
            elif fetched:
                merged.append(dict(fetched))

        merged.extend(existing_by_id.values())
        return merged

    def _mechanistic_context_from_request(self, request) -> Dict[str, Any]:
        expert_rule = request.ad_inputs.get("expert_rule") or request.ad_inputs.get(
            "expertRule"
        )
        if not isinstance(expert_rule, dict):
            return {}
        mechanistic_context = expert_rule.get("mechanistic_context") or expert_rule.get(
            "mechanisticContext"
        )
        if isinstance(mechanistic_context, dict):
            return mechanistic_context
        return {}

    def _merge_mechanistic_mapping(
        self,
        existing: Any,
        fetched: Dict[str, Any],
        *,
        analogue_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = dict(existing) if isinstance(existing, dict) else {}
        for key, value in fetched.items():
            if key not in payload or not payload[key]:
                payload[key] = deepcopy(value)
        if analogue_id and "id" not in payload:
            payload["id"] = analogue_id
        return payload

    def _extract_analogue_ids(self, ad_inputs: Dict[str, Any]) -> List[str]:
        analogue_ids: List[str] = []
        seen = set()
        candidates = [
            ad_inputs.get("expert_rule"),
            ad_inputs.get("expertRule"),
            ad_inputs.get("similarity"),
        ]
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            for key in (
                "analogues",
                "analogueIds",
                "analogue_ids",
                "neighborIds",
                "neighbor_ids",
            ):
                value = candidate.get(key)
                if key == "analogues" and isinstance(value, list):
                    for index, item in enumerate(value):
                        analogue_id = self._extract_analogue_id(
                            item, fallback_index=index
                        )
                        if analogue_id and analogue_id not in seen:
                            seen.add(analogue_id)
                            analogue_ids.append(analogue_id)
                elif isinstance(value, list):
                    for item in value:
                        analogue_id = self._normalize_dtxsid_candidate(item)
                        if analogue_id and analogue_id not in seen:
                            seen.add(analogue_id)
                            analogue_ids.append(analogue_id)
            mechanistic = candidate.get("mechanistic_context") or candidate.get(
                "mechanisticContext"
            )
            if isinstance(mechanistic, dict):
                analogue_values = mechanistic.get("analogues")
                if isinstance(analogue_values, list):
                    for index, item in enumerate(analogue_values):
                        analogue_id = self._extract_analogue_id(
                            item, fallback_index=index
                        )
                        if analogue_id and analogue_id not in seen:
                            seen.add(analogue_id)
                            analogue_ids.append(analogue_id)
        return analogue_ids

    def _extract_analogue_id(self, value: Any, *, fallback_index: int) -> Optional[str]:
        if isinstance(value, dict):
            candidate = (
                value.get("id")
                or value.get("dtxsid")
                or value.get("chemical_identifier")
                or value.get("chemicalIdentifier")
                or value.get("name")
            )
            return self._normalize_dtxsid_candidate(candidate)
        return self._normalize_dtxsid_candidate(value)

    def _normalize_dtxsid_candidate(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip().upper()
        if text.startswith("DTXSID"):
            return text
        return None
