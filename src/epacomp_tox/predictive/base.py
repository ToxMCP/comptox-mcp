from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from epacomp_tox.metadata.applicability import ApplicabilityDomainStore
from epacomp_tox.predictive.ad_evaluators import (
    ApplicabilityDomainEvaluator,
    build_ad_evaluator,
)


class PredictiveRequest(BaseModel):
    """Base request model for predictive micro-servers."""

    chemical_identifier: str
    identifier_type: str = "dtxsid"
    ad_inputs: Dict[str, Any] = Field(default_factory=dict)


class ADCheckResult(BaseModel):
    """Standard response for applicability domain evaluations."""

    in_domain: bool
    confidence: float
    details: Dict[str, Any] = Field(default_factory=dict)


class PredictiveResponse(BaseModel):
    """Standardized predictive response envelope."""

    prediction: Dict[str, Any]
    applicability_domain: ADCheckResult
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PredictiveServiceBase(ABC):
    """Shared scaffolding for predictive micro-servers."""

    def __init__(
        self,
        *,
        config: Dict[str, Any],
        ad_store: Optional[ApplicabilityDomainStore] = None,
        ad_evaluator: Optional[ApplicabilityDomainEvaluator] = None,
    ) -> None:
        self.config = config
        self.logger = logger.getChild(self.__class__.__name__)
        self.ad_store = ad_store or ApplicabilityDomainStore()
        self.ad_definition = self._resolve_ad_definition()
        self.ad_evaluator = ad_evaluator or build_ad_evaluator(self.config)

    def prepare_request(self, request: PredictiveRequest) -> PredictiveRequest:
        """Allow services to enrich requests before AD/prediction execution."""
        return request

    def backfill_request_from_outputs(
        self,
        request: PredictiveRequest,
        *,
        ad_result: Optional[ADCheckResult],
        prediction_payload: Optional[Dict[str, Any]],
    ) -> PredictiveRequest:
        """Allow services to enrich stored request provenance after execution."""
        return request

    def predict(
        self,
        request: PredictiveRequest,
        *,
        ad_result: Optional[ADCheckResult] = None,
    ) -> PredictiveResponse:
        """Run applicability domain check, prediction, and assemble response."""
        checked_ad_result = ad_result or self.check_applicability_domain(request)
        policy_metadata = self._apply_ad_policy(request, checked_ad_result)
        payload = self._predict_impl(request)
        metadata = self._build_metadata(request, checked_ad_result, payload)
        metadata.update(policy_metadata)
        return PredictiveResponse(
            prediction=payload,
            applicability_domain=checked_ad_result,
            metadata=metadata,
        )

    def check_applicability_domain(self, request: PredictiveRequest) -> ADCheckResult:
        """Evaluate whether the request falls within the validated domain."""
        return self.ad_evaluator.evaluate(
            request,
            definition=self.ad_definition,
            delegated_check=self._check_ad_impl,
        )

    @abstractmethod
    def _predict_impl(self, request: PredictiveRequest) -> Dict[str, Any]:
        """Model-specific prediction."""

    @abstractmethod
    def _check_ad_impl(self, request: PredictiveRequest) -> ADCheckResult:
        """Model-specific AD evaluation."""

    def _build_metadata(
        self,
        request: PredictiveRequest,
        ad_result: ADCheckResult,
        prediction_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Hook for adding provenance/telemetry to responses."""
        metadata: Dict[str, Any] = {
            "identifier": request.chemical_identifier,
            "identifier_type": request.identifier_type,
            "model": self.config.get("name"),
            "model_version": self.config.get("version"),
        }
        if self.ad_definition:
            metadata["adPolicy"] = self.ad_definition.get("policy")
            metadata["adErrorCode"] = self.ad_definition.get("errorCode")
            metadata["adDefinition"] = {
                "model": self.ad_definition.get("model"),
                "version": self.ad_definition.get("version"),
            }
        metadata["adEvaluator"] = ad_result.details.get(
            "adEvaluator", getattr(self.ad_evaluator, "name", "unknown")
        )
        metadata["adEnforcementLocation"] = ad_result.details.get(
            "adEnforcementLocation",
            getattr(self.ad_evaluator, "enforcement_location", "delegated-service"),
        )
        if "adFallbackUsed" in ad_result.details:
            metadata["adFallbackUsed"] = ad_result.details["adFallbackUsed"]
        if "adFallbackReason" in ad_result.details:
            metadata["adFallbackReason"] = ad_result.details["adFallbackReason"]
        return metadata

    def _resolve_ad_definition(self) -> Optional[Dict[str, Any]]:
        target = self.config.get("ad_model_name") or self.config.get("name")
        if not target:
            return None
        definition = self.ad_store.get_definition(target)
        if not definition:
            self.logger.debug("No AD definition found for %s", target)
        return definition

    def _apply_ad_policy(
        self, request: PredictiveRequest, ad_result: ADCheckResult
    ) -> Dict[str, Any]:
        definition = self.ad_definition or {}
        policy = (definition.get("policy") or "block").lower()
        metadata: Dict[str, Any] = {}
        if not ad_result.in_domain:
            message = (
                f"Applicability domain check failed for {request.chemical_identifier}"
            )
            error_code = definition.get("errorCode")
            if policy == "block":
                raise ValueError(error_code or message)
            if policy == "warn":
                metadata["adWarning"] = True
                metadata["adMessage"] = error_code or message
                self.logger.warning("%s", metadata["adMessage"])
            else:
                # Unknown policy defaults to block
                raise ValueError(error_code or message)
        return metadata
