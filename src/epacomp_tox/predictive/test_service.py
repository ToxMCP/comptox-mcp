from __future__ import annotations

from typing import Any, Dict, Optional

from ctxpy import CtxApiError
from epacomp_tox.metadata.applicability import ApplicabilityDomainStore
from epacomp_tox.predictive.base import (
    ADCheckResult,
    PredictiveRequest,
    PredictiveServiceBase,
)
from epacomp_tox.predictive.clients import PredictiveClient


class TestClient(PredictiveClient):
    """Wrapper around ctxpy TEST client."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def predict(self, request: PredictiveRequest) -> Dict[str, Any]:
        try:
            return self.client.predict(
                chemical=request.chemical_identifier,
                identifier_type=request.identifier_type,
            )
        except CtxApiError as exc:  # pragma: no cover - passthrough
            raise ValueError(f"TEST prediction failed: {exc}") from exc

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


class TestConsensusPredictiveService(PredictiveServiceBase):
    """Predictive service wrapper for TEST consensus toxicity models."""

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
            raise RuntimeError("TEST client not configured")
        return self.client

    def _predict_impl(self, request: PredictiveRequest) -> Dict[str, Any]:
        client = self._ensure_client()
        payload = client.predict(request)
        return payload

    def _check_ad_impl(self, request: PredictiveRequest) -> ADCheckResult:
        client = self._ensure_client()
        return client.check_applicability_domain(request)


TestConsensusPredictiveService.__test__ = False
