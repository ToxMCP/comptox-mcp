from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional

from epacomp_tox.predictive import (
    ADCheckResult,
    PredictiveRequest,
    PredictiveResponse,
    PredictiveServiceBase,
)

from .models import (
    GuardrailEvent,
    PredictiveRunResult,
    PredictiveStepResult,
    PredictiveTask,
)


class PredictiveCoordinator:
    """Coordinate predictive micro-service execution with applicability guardrails."""

    def __init__(
        self,
        services: Dict[str, PredictiveServiceBase],
        *,
        default_require_ad_clearance: bool = True,
        stage_name: str = "RunPredictiveModels",
    ) -> None:
        self._services = dict(services)
        self.default_require_ad_clearance = default_require_ad_clearance
        self.stage_name = stage_name

    def register_service(self, name: str, service: PredictiveServiceBase) -> None:
        """Register or replace a predictive service."""
        self._services[name] = service

    def run(
        self,
        tasks: Iterable[PredictiveTask],
        *,
        require_ad_clearance: Optional[bool] = None,
    ) -> PredictiveRunResult:
        """Execute predictive tasks and aggregate guardrail events."""
        require = (
            self.default_require_ad_clearance
            if require_ad_clearance is None
            else require_ad_clearance
        )
        results: List[PredictiveStepResult] = []
        guardrails: List[GuardrailEvent] = []
        succeeded = True

        for task in tasks:
            service = self._ensure_service(task.service)
            ad_result: Optional[ADCheckResult] = None
            try:
                ad_result = service.check_applicability_domain(task.request)
            except Exception as exc:  # pragma: no cover - defensive
                succeeded = False
                results.append(
                    PredictiveStepResult(
                        service=task.service,
                        status="error",
                        scenario=task.scenario,
                        label=task.label,
                        request=task.request,
                        error=str(exc),
                    )
                )
                guardrails.append(
                    self._make_guardrail_event(
                        component=task.service,
                        status="error",
                        code=self._resolve_error_code(service),
                        message=f"Applicability domain check failed ({exc})",
                        confidence=None,
                        metadata={"stage": "check_applicability_domain"},
                    )
                )
                continue

            policy = self._resolve_policy(service)
            if not ad_result.in_domain and (require or policy == "block"):
                succeeded = False
                guardrails.append(
                    self._make_guardrail_event(
                        component=task.service,
                        status="denied",
                        code=self._resolve_error_code(service),
                        message="Applicability domain check failed.",
                        confidence=ad_result.confidence,
                        metadata={"policy": policy},
                    )
                )
                results.append(
                    PredictiveStepResult(
                        service=task.service,
                        status="denied",
                        scenario=task.scenario,
                        label=task.label,
                        request=task.request,
                        ad=ad_result,
                        metadata={"policy": policy},
                    )
                )
                continue

            try:
                prediction = service.predict(task.request)
            except Exception as exc:  # pragma: no cover - defensive
                succeeded = False
                guardrails.append(
                    self._make_guardrail_event(
                        component=task.service,
                        status="error",
                        code=self._resolve_error_code(service),
                        message=f"Prediction failed ({exc})",
                        confidence=ad_result.confidence if ad_result else None,
                        metadata={"policy": policy},
                    )
                )
                results.append(
                    PredictiveStepResult(
                        service=task.service,
                        status="error",
                        scenario=task.scenario,
                        label=task.label,
                        request=task.request,
                        ad=ad_result,
                        error=str(exc),
                        metadata={"policy": policy},
                    )
                )
                continue

            step_status = "success"
            if not prediction.applicability_domain.in_domain:
                guardrails.append(
                    self._make_guardrail_event(
                        component=task.service,
                        status="warning",
                        code=self._resolve_error_code(service),
                        message="Applicability domain warning.",
                        confidence=prediction.applicability_domain.confidence,
                        metadata={"policy": policy},
                    )
                )
                if policy == "block":
                    step_status = "denied"
                    succeeded = False

            results.append(
                PredictiveStepResult(
                    service=task.service,
                    status=step_status,
                    scenario=task.scenario,
                    label=task.label,
                    request=task.request,
                    ad=prediction.applicability_domain,
                    prediction=prediction.prediction,
                    metadata=prediction.metadata,
                )
            )

        return PredictiveRunResult(results=results, guardrails=guardrails, succeeded=succeeded)

    # Internal utilities -----------------------------------------------------

    def _ensure_service(self, name: str) -> PredictiveServiceBase:
        if name not in self._services:
            raise KeyError(f"Predictive service '{name}' is not registered.")
        return self._services[name]

    def _resolve_policy(self, service: PredictiveServiceBase) -> str:
        definition = getattr(service, "ad_definition", None) or {}
        policy = definition.get("policy") if isinstance(definition, dict) else None
        if isinstance(policy, str):
            return policy.lower()
        return "block"

    def _resolve_error_code(self, service: PredictiveServiceBase) -> Optional[str]:
        definition = getattr(service, "ad_definition", None) or {}
        if isinstance(definition, dict):
            return definition.get("errorCode")
        return None

    def _make_guardrail_event(
        self,
        *,
        component: str,
        status: str,
        message: str,
        code: Optional[str],
        confidence: Optional[float],
        metadata: Optional[Dict[str, str]] = None,
    ) -> GuardrailEvent:
        timestamp = datetime.now(timezone.utc).isoformat()
        return GuardrailEvent(
            stage=self.stage_name,
            component=component,
            status=status,
            code=code,
            message=message,
            confidence=confidence,
            timestamp=timestamp,
            metadata=metadata or {},
        )
