from __future__ import annotations

from typing import Any, Dict, Optional

from epacomp_tox.metadata.applicability import ApplicabilityDomainStore
from epacomp_tox.predictive.base import (
    ADCheckResult,
    PredictiveRequest,
    PredictiveServiceBase,
)
from epacomp_tox.predictive.clients import PredictiveClient


class GenRAClient(PredictiveClient):
    """Wrapper interface for GenRA analogue search + prediction service."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def predict(self, request: PredictiveRequest) -> Dict[str, Any]:
        return self.client.predict(
            chemical=request.chemical_identifier,
            identifier_type=request.identifier_type,
        )

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


class GenRAService(PredictiveServiceBase):
    """Predictive service wrapper for the GenRA read-across workflow."""

    def __init__(
        self,
        *,
        config: Dict[str, Any],
        client: Optional[PredictiveClient] = None,
        ad_store: Optional[ApplicabilityDomainStore] = None,
    ) -> None:
        super().__init__(config=config, ad_store=ad_store)
        self.client = client

    def _ensure_client(self) -> PredictiveClient:
        if self.client is None:
            raise RuntimeError("GenRA client not configured")
        return self.client

    def _predict_impl(self, request: PredictiveRequest) -> Dict[str, Any]:
        client = self._ensure_client()
        return client.predict(request)

    def _check_ad_impl(self, request: PredictiveRequest) -> ADCheckResult:
        client = self._ensure_client()
        return client.check_applicability_domain(request)
