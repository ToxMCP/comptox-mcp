from __future__ import annotations

from typing import Callable, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from epacomp_tox.predictive.base import (
    ADCheckResult,
    PredictiveRequest,
    PredictiveResponse,
    PredictiveServiceBase,
)
from epacomp_tox.contracts import validate_payload

PREDICT_RESPONSE_SCHEMA = ("predictive", "predict.response.schema")
AD_RESPONSE_SCHEMA = ("predictive", "ad_check.response.schema")


def build_predictive_router(
    *,
    service_factory: Callable[[], PredictiveServiceBase],
    prefix: str = "",
    tags: Optional[list[str]] = None,
) -> APIRouter:
    """Construct a router exposing predict and AD check endpoints."""
    router = APIRouter(prefix=prefix, tags=tags or ["predictive"])

    async def get_service() -> PredictiveServiceBase:
        return service_factory()

    @router.post(
        "/predict",
        response_model=PredictiveResponse,
        summary="Run predictive model with applicability domain enforcement",
    )
    async def predict_endpoint(
        body: PredictiveRequest, service: PredictiveServiceBase = Depends(get_service)
    ) -> PredictiveResponse:
        try:
            response = service.predict(body)
            validate_payload(
                response.model_dump(),
                namespace=PREDICT_RESPONSE_SCHEMA[0],
                name=PREDICT_RESPONSE_SCHEMA[1],
            )
            return response
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc

    @router.post(
        "/check_applicability_domain",
        response_model=ADCheckResult,
        summary="Evaluate applicability domain for the given request",
    )
    async def ad_endpoint(
        body: PredictiveRequest, service: PredictiveServiceBase = Depends(get_service)
    ) -> ADCheckResult:
        result = service.check_applicability_domain(body)
        validate_payload(
            result.model_dump(),
            namespace=AD_RESPONSE_SCHEMA[0],
            name=AD_RESPONSE_SCHEMA[1],
        )
        return result

    return router
