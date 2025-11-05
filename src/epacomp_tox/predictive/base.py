from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

from epacomp_tox.metadata.applicability import ApplicabilityDomainStore


class PredictiveRequest(BaseModel):
    """Base request model for predictive micro-servers."""

    chemical_identifier: str
    identifier_type: str = "dtxsid"


class ADCheckResult(BaseModel):
    """Standard response for applicability domain evaluations."""

    in_domain: bool
    confidence: float
    details: Dict[str, Any] = {}


class PredictiveResponse(BaseModel):
    """Standardized predictive response envelope."""

    prediction: Dict[str, Any]
    applicability_domain: ADCheckResult
    metadata: Dict[str, Any] = {}


class PredictiveServiceBase(ABC):
    """Shared scaffolding for predictive micro-servers."""

    def __init__(
        self,
        *,
        config: Dict[str, Any],
        ad_store: Optional[ApplicabilityDomainStore] = None,
    ) -> None:
        self.config = config
        self.logger = logger.getChild(self.__class__.__name__)
        self.ad_store = ad_store or ApplicabilityDomainStore()
        self.ad_definition = self._resolve_ad_definition()

    def predict(self, request: PredictiveRequest) -> PredictiveResponse:
        """Run applicability domain check, prediction, and assemble response."""
        ad_result = self.check_applicability_domain(request)
        policy_metadata = self._apply_ad_policy(request, ad_result)
        payload = self._predict_impl(request)
        metadata = self._build_metadata(request, ad_result)
        metadata.update(policy_metadata)
        return PredictiveResponse(
            prediction=payload,
            applicability_domain=ad_result,
            metadata=metadata,
        )

    def check_applicability_domain(self, request: PredictiveRequest) -> ADCheckResult:
        """Evaluate whether the request falls within the validated domain."""
        return self._check_ad_impl(request)

    @abstractmethod
    def _predict_impl(self, request: PredictiveRequest) -> Dict[str, Any]:
        """Model-specific prediction."""

    @abstractmethod
    def _check_ad_impl(self, request: PredictiveRequest) -> ADCheckResult:
        """Model-specific AD evaluation."""

    def _build_metadata(
        self, request: PredictiveRequest, ad_result: ADCheckResult
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
                raise ValueError(
                    error_code or message
                )
            if policy == "warn":
                metadata["adWarning"] = True
                metadata["adMessage"] = error_code or message
                self.logger.warning("%s", metadata["adMessage"])
            else:
                # Unknown policy defaults to block
                raise ValueError(error_code or message)
        return metadata
