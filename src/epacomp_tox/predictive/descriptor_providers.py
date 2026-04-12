from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from .base import PredictiveRequest


class DescriptorProviderError(RuntimeError):
    """Raised when a descriptor provider cannot resolve descriptor context."""


@dataclass(frozen=True)
class DescriptorContext:
    values: Dict[str, float]
    bounds: Dict[str, Dict[str, float]]
    source: str
    metadata: Dict[str, Any]


class DescriptorProvider(ABC):
    """Abstraction for fetching descriptor values and numeric bounds."""

    name = "abstract"

    @abstractmethod
    def resolve(
        self,
        *,
        request: "PredictiveRequest",
        descriptors: List[str],
        criterion: Dict[str, Any],
        definition: Optional[Dict[str, Any]],
    ) -> DescriptorContext:
        """Return descriptor values and numeric bounds for the request."""


class ExternalChemistryDescriptorProvider(DescriptorProvider):
    """Fetch descriptor context from an optional chemistry backend."""

    name = "external-chemistry-backend"

    def __init__(
        self,
        *,
        endpoint: str,
        timeout_seconds: float = 30.0,
        bearer_token: Optional[str] = None,
        api_key: Optional[str] = None,
        urlopen: Callable[..., Any] = urllib.request.urlopen,
    ) -> None:
        self.endpoint = endpoint
        self.timeout_seconds = float(timeout_seconds)
        self.bearer_token = bearer_token
        self.api_key = api_key
        self._urlopen = urlopen

    def resolve(
        self,
        *,
        request: "PredictiveRequest",
        descriptors: List[str],
        criterion: Dict[str, Any],
        definition: Optional[Dict[str, Any]],
    ) -> DescriptorContext:
        payload = {
            "chemicalIdentifier": request.chemical_identifier,
            "identifierType": request.identifier_type,
            "descriptors": descriptors,
            "criterion": criterion,
            "applicabilityDomain": {
                "model": (definition or {}).get("model"),
                "version": (definition or {}).get("version"),
                "range": criterion.get("range"),
            },
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
            raise DescriptorProviderError(
                f"descriptor backend returned HTTP {exc.code}: {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise DescriptorProviderError(f"descriptor backend failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise DescriptorProviderError(
                "descriptor backend returned invalid JSON"
            ) from exc

        payload = body.get("result", body)
        if not isinstance(payload, dict):
            raise DescriptorProviderError(
                "descriptor backend returned a non-object payload"
            )

        values = (
            payload.get("descriptorValues") or payload.get("descriptor_values") or {}
        )
        bounds = (
            payload.get("descriptorBounds") or payload.get("descriptor_bounds") or {}
        )
        if not isinstance(values, dict) or not isinstance(bounds, dict):
            raise DescriptorProviderError(
                "descriptor backend response omitted descriptor values or bounds"
            )

        normalized_values = {
            str(name): float(value)
            for name, value in values.items()
            if _is_number(value)
        }
        normalized_bounds: Dict[str, Dict[str, float]] = {}
        for descriptor, bound_payload in bounds.items():
            if not isinstance(bound_payload, dict):
                continue
            normalized = _normalize_bounds(bound_payload)
            if normalized is not None:
                normalized_bounds[str(descriptor)] = normalized

        metadata = (
            payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        )
        source = str(payload.get("source") or self.name)
        return DescriptorContext(
            values=normalized_values,
            bounds=normalized_bounds,
            source=source,
            metadata=metadata,
        )


def build_descriptor_provider_from_env() -> Optional[DescriptorProvider]:
    """Build the optional descriptor provider from environment settings."""
    endpoint = os.environ.get("EPACOMP_AD_DESCRIPTOR_BACKEND_URL")
    if not endpoint:
        return None
    timeout_seconds = float(
        os.environ.get("EPACOMP_AD_DESCRIPTOR_BACKEND_TIMEOUT_SECONDS") or 30.0
    )
    bearer_token = os.environ.get("EPACOMP_AD_DESCRIPTOR_BACKEND_BEARER_TOKEN")
    api_key = os.environ.get("EPACOMP_AD_DESCRIPTOR_BACKEND_API_KEY")
    return ExternalChemistryDescriptorProvider(
        endpoint=endpoint,
        timeout_seconds=timeout_seconds,
        bearer_token=bearer_token,
        api_key=api_key,
    )


def _normalize_bounds(bound_payload: Dict[str, Any]) -> Optional[Dict[str, float]]:
    lower = (
        bound_payload.get("lower")
        if bound_payload.get("lower") is not None
        else bound_payload.get("min")
    )
    upper = (
        bound_payload.get("upper")
        if bound_payload.get("upper") is not None
        else bound_payload.get("max")
    )
    if not _is_number(lower) or not _is_number(upper):
        return None
    return {"lower": float(lower), "upper": float(upper)}


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


__all__ = [
    "DescriptorContext",
    "DescriptorProvider",
    "DescriptorProviderError",
    "ExternalChemistryDescriptorProvider",
    "build_descriptor_provider_from_env",
]
