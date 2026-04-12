from __future__ import annotations

from typing import Any, Dict, Optional

from epacomp_tox.metadata.applicability import ApplicabilityDomainStore
from epacomp_tox.predictive.ad_evaluators import ApplicabilityDomainEvaluator
from epacomp_tox.predictive.base import (
    ADCheckResult,
    PredictiveRequest,
    PredictiveServiceBase,
)
from epacomp_tox.predictive.clients import PredictiveClient


class OperaClient(PredictiveClient):
    """Wrapper around OPERA CLI/API integration."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def predict(self, request: PredictiveRequest) -> Dict[str, Any]:
        payload = self.client.predict_property(
            chemical=request.chemical_identifier,
            identifier_type=request.identifier_type,
        )
        return payload

    def check_applicability_domain(self, request: PredictiveRequest) -> ADCheckResult:
        result = self.client.check_applicability_domain(
            chemical=request.chemical_identifier,
            identifier_type=request.identifier_type,
        )
        return ADCheckResult(
            in_domain=result.get("in_domain", False),
            confidence=result.get("confidence", 0.0),
            details=result,
        )


class OperaPropertyService(PredictiveServiceBase):
    """Predictive service wrapper for OPERA property models."""

    def __init__(
        self,
        *,
        config: Dict[str, Any],
        client: Optional[PredictiveClient] = None,
        ad_store: Optional[ApplicabilityDomainStore] = None,
        ad_evaluator: Optional[ApplicabilityDomainEvaluator] = None,
    ) -> None:
        super().__init__(
            config=config,
            ad_store=ad_store,
            ad_evaluator=ad_evaluator,
        )
        self.client = client

    def _ensure_client(self) -> PredictiveClient:
        if self.client is None:
            raise RuntimeError("OPERA client not configured")
        return self.client

    def _predict_impl(self, request: PredictiveRequest) -> Dict[str, Any]:
        client = self._ensure_client()
        return client.predict(request)

    def _check_ad_impl(self, request: PredictiveRequest) -> ADCheckResult:
        client = self._ensure_client()
        return client.check_applicability_domain(request)
