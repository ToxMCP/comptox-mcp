from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

if TYPE_CHECKING:
    from .base import PredictiveRequest


class ExpertRuleProviderError(RuntimeError):
    """Raised when an expert-rule provider cannot resolve mechanistic context."""


@dataclass(frozen=True)
class ExpertRuleContext:
    payload: Dict[str, Any]
    source: str
    metadata: Dict[str, Any]


class ExpertRuleProvider(ABC):
    """Abstraction for fetching mechanistic context for expert rules."""

    name = "abstract"

    @abstractmethod
    def resolve(
        self,
        *,
        request: "PredictiveRequest",
        criterion: Dict[str, Any],
        definition: Optional[Dict[str, Any]],
    ) -> ExpertRuleContext:
        """Return mechanistic context for expert-rule evaluation."""


class ExternalExpertRuleProvider(ExpertRuleProvider):
    """Fetch expert-rule context from an optional chemistry/mechanistic backend."""

    name = "external-expert-rule-backend"

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
        criterion: Dict[str, Any],
        definition: Optional[Dict[str, Any]],
    ) -> ExpertRuleContext:
        payload = {
            "chemicalIdentifier": request.chemical_identifier,
            "identifierType": request.identifier_type,
            "rule": criterion.get("rule"),
            "criterion": criterion,
            "applicabilityDomain": {
                "model": (definition or {}).get("model"),
                "version": (definition or {}).get("version"),
            },
            "expertRuleInputs": request.ad_inputs.get("expert_rule")
            or request.ad_inputs.get("expertRule")
            or {},
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
            raise ExpertRuleProviderError(
                f"expert-rule backend returned HTTP {exc.code}: {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise ExpertRuleProviderError(f"expert-rule backend failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise ExpertRuleProviderError(
                "expert-rule backend returned invalid JSON"
            ) from exc

        payload = body.get("result", body)
        if not isinstance(payload, dict):
            raise ExpertRuleProviderError(
                "expert-rule backend returned a non-object payload"
            )

        context = payload.get("ruleContext") or payload.get("rule_context") or payload
        if not isinstance(context, dict):
            raise ExpertRuleProviderError(
                "expert-rule backend response omitted rule context"
            )
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        source = str(payload.get("source") or self.name)
        return ExpertRuleContext(payload=context, source=source, metadata=metadata)


def build_rule_provider_from_env() -> Optional[ExpertRuleProvider]:
    """Build the optional expert-rule provider from environment settings."""
    endpoint = os.environ.get("EPACOMP_AD_RULE_BACKEND_URL")
    if not endpoint:
        return None
    timeout_seconds = float(
        os.environ.get("EPACOMP_AD_RULE_BACKEND_TIMEOUT_SECONDS") or 30.0
    )
    bearer_token = os.environ.get("EPACOMP_AD_RULE_BACKEND_BEARER_TOKEN")
    api_key = os.environ.get("EPACOMP_AD_RULE_BACKEND_API_KEY")
    return ExternalExpertRuleProvider(
        endpoint=endpoint,
        timeout_seconds=timeout_seconds,
        bearer_token=bearer_token,
        api_key=api_key,
    )


__all__ = [
    "ExpertRuleContext",
    "ExpertRuleProvider",
    "ExpertRuleProviderError",
    "ExternalExpertRuleProvider",
    "build_rule_provider_from_env",
]
