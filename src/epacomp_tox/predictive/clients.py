from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from epacomp_tox.predictive.base import ADCheckResult, PredictiveRequest


class PredictiveClient(ABC):
    """Minimal client interface for predictive services."""

    @abstractmethod
    def predict(self, request: PredictiveRequest) -> dict[str, Any]:
        """Execute model prediction."""

    @abstractmethod
    def check_applicability_domain(self, request: PredictiveRequest) -> ADCheckResult:
        """Evaluate applicability domain for the request."""
