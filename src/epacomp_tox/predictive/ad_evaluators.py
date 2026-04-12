from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

if TYPE_CHECKING:
    from .base import ADCheckResult, PredictiveRequest


class ADEvaluatorError(RuntimeError):
    """Raised when an AD evaluator backend cannot complete successfully."""


class ApplicabilityDomainEvaluator(ABC):
    """Abstraction layer for AD evaluation backends."""

    name = "abstract"
    enforcement_location = "delegated-service"

    @abstractmethod
    def evaluate(
        self,
        request: "PredictiveRequest",
        *,
        definition: Optional[Dict[str, Any]],
        delegated_check: Callable[["PredictiveRequest"], "ADCheckResult"],
    ) -> "ADCheckResult":
        """Return a normalized applicability-domain decision."""


class DelegatedServiceADEvaluator(ApplicabilityDomainEvaluator):
    """Current behavior: defer AD math to the predictive service/client."""

    name = "delegated-service"
    enforcement_location = "delegated-service"

    def evaluate(
        self,
        request: "PredictiveRequest",
        *,
        definition: Optional[Dict[str, Any]],
        delegated_check: Callable[["PredictiveRequest"], "ADCheckResult"],
    ) -> "ADCheckResult":
        return delegated_check(request)


class ExternalChemistryServiceADEvaluator(ApplicabilityDomainEvaluator):
    """Chemistry-service-backed AD checks with optional delegated fallback."""

    name = "external-chemistry-service"
    enforcement_location = "local-engine"

    def __init__(
        self,
        evaluator: Optional[
            Callable[
                ["PredictiveRequest", Optional[Dict[str, Any]]],
                "ADCheckResult" | Dict[str, Any],
            ]
        ] = None,
        *,
        endpoint: Optional[str] = None,
        timeout_seconds: float = 30.0,
        bearer_token: Optional[str] = None,
        api_key: Optional[str] = None,
        fallback_to_delegated: bool = False,
        urlopen: Callable[..., Any] = urllib.request.urlopen,
    ) -> None:
        if evaluator is not None and endpoint is not None:
            raise ValueError(
                "Provide either a callable evaluator or an endpoint, not both."
            )
        if evaluator is None and not endpoint:
            raise ValueError(
                "External chemistry AD evaluator requires a callable or endpoint."
            )
        self._evaluator = evaluator
        self.endpoint = endpoint
        self.timeout_seconds = float(timeout_seconds)
        self.bearer_token = bearer_token
        self.api_key = api_key
        self.fallback_to_delegated = fallback_to_delegated
        self._urlopen = urlopen

    def evaluate(
        self,
        request: "PredictiveRequest",
        *,
        definition: Optional[Dict[str, Any]],
        delegated_check: Callable[["PredictiveRequest"], "ADCheckResult"],
    ) -> "ADCheckResult":
        from .base import ADCheckResult

        if self._evaluator is not None:
            result = self._evaluator(request, definition)
            if isinstance(result, ADCheckResult):
                return result
            return ADCheckResult(**result)

        try:
            payload = self._post_to_sidecar(request, definition)
        except ADEvaluatorError:
            if not self.fallback_to_delegated:
                raise
            delegated = delegated_check(request)
            details = dict(delegated.details)
            details.update(
                {
                    "adEvaluator": self.name,
                    "adEnforcementLocation": "delegated-service",
                    "adFallbackUsed": True,
                    "adFallbackReason": "external-chemistry-service-unavailable",
                }
            )
            return ADCheckResult(
                in_domain=delegated.in_domain,
                confidence=delegated.confidence,
                details=details,
            )

        return ADCheckResult(**self._normalize_sidecar_response(payload))

    def _post_to_sidecar(
        self, request: "PredictiveRequest", definition: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        assert self.endpoint is not None  # guarded in __init__

        payload = {
            "request": request.model_dump(),
            "applicabilityDomain": definition,
        }
        headers = {"Content-Type": "application/json"}
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        if self.api_key:
            headers["x-api-key"] = self.api_key

        http_request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
        )

        try:
            with self._urlopen(http_request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ADEvaluatorError(
                f"external chemistry AD evaluator returned HTTP {exc.code}: {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise ADEvaluatorError(
                f"external chemistry AD evaluator failed: {exc}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise ADEvaluatorError(
                "external chemistry AD evaluator returned invalid JSON"
            ) from exc

        if not isinstance(body, dict):
            raise ADEvaluatorError(
                "external chemistry AD evaluator returned a non-object payload"
            )
        return body

    def _normalize_sidecar_response(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        body = payload.get("result", payload)
        if not isinstance(body, dict):
            raise ADEvaluatorError(
                "external chemistry AD evaluator returned an invalid result object"
            )

        in_domain = body.get("in_domain")
        if in_domain is None:
            in_domain = body.get("inDomain")
        if in_domain is None:
            raise ADEvaluatorError(
                "external chemistry AD evaluator response omitted in_domain"
            )

        confidence = body.get("confidence", 0.0)
        details = dict(body.get("details") or {})
        for key, value in body.items():
            if key in {"in_domain", "inDomain", "confidence", "details"}:
                continue
            details.setdefault(key, value)
        details.setdefault("adEvaluator", self.name)
        details.setdefault("adEnforcementLocation", self.enforcement_location)
        return {
            "in_domain": bool(in_domain),
            "confidence": float(confidence),
            "details": details,
        }


def build_ad_evaluator(
    config: Optional[Dict[str, Any]] = None,
    *,
    urlopen: Callable[..., Any] = urllib.request.urlopen,
) -> ApplicabilityDomainEvaluator:
    """Resolve the configured AD evaluator backend."""
    config = config or {}
    evaluator_name = str(
        config.get("ad_evaluator")
        or os.environ.get("EPACOMP_AD_EVALUATOR")
        or "delegated-service"
    ).strip()
    normalized_name = evaluator_name.lower()

    if normalized_name in {"delegated-service", "delegated"}:
        return DelegatedServiceADEvaluator()

    if normalized_name in {"external-chemistry-service", "sidecar"}:
        endpoint = config.get("ad_sidecar_url") or os.environ.get(
            "EPACOMP_AD_SIDECAR_URL"
        )
        if not endpoint:
            raise ValueError(
                "External chemistry AD evaluator requires "
                "`ad_sidecar_url` or EPACOMP_AD_SIDECAR_URL."
            )
        timeout_seconds = float(
            config.get("ad_sidecar_timeout_seconds")
            or os.environ.get("EPACOMP_AD_SIDECAR_TIMEOUT_SECONDS")
            or 30.0
        )
        bearer_token = config.get("ad_sidecar_bearer_token") or os.environ.get(
            "EPACOMP_AD_SIDECAR_BEARER_TOKEN"
        )
        api_key = config.get("ad_sidecar_api_key") or os.environ.get(
            "EPACOMP_AD_SIDECAR_API_KEY"
        )
        fallback_to_delegated = _coerce_bool(
            config.get("ad_sidecar_fallback_to_delegated"),
            default=_coerce_bool(
                os.environ.get("EPACOMP_AD_SIDECAR_FALLBACK_TO_DELEGATED"),
                default=False,
            ),
        )
        return ExternalChemistryServiceADEvaluator(
            endpoint=str(endpoint),
            timeout_seconds=timeout_seconds,
            bearer_token=bearer_token,
            api_key=api_key,
            fallback_to_delegated=fallback_to_delegated,
            urlopen=urlopen,
        )

    raise ValueError(f"Unsupported AD evaluator '{evaluator_name}'.")


def _coerce_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


__all__ = [
    "ADEvaluatorError",
    "ApplicabilityDomainEvaluator",
    "DelegatedServiceADEvaluator",
    "ExternalChemistryServiceADEvaluator",
    "build_ad_evaluator",
]
