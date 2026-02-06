from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence

from ..predictive.base import ADCheckResult, PredictiveRequest, PredictiveServiceBase
from .ctx_data import CtxDataAssembler
from .evidence import EvidenceSynthesizer
from .identifiers import IdentifierResolver
from .predictive import PredictiveCoordinator
from .workflow import GenRAOrchestrator

OFFLINE_SCENARIOS = [
    "acute_toxicity",
    "exposure_prioritization",
    "genra_read_across",
]


class _OfflineChemicalResource:
    def __init__(self) -> None:
        self._metadata: Dict[str, Any] = {}

    def search_chemical(self, query: str, search_type: str) -> list[dict[str, Any]]:
        self._metadata = {"status": 200}
        return [
            {
                "dtxsid": "DTXSID0000001",
                "preferredName": "Offline Example",
                "casrn": "50-00-0",
            }
        ]

    def get_chemical_details(
        self, identifier: str, id_type: str, subset: str = "default"
    ) -> dict[str, Any]:
        self._metadata = {"status": 200}
        return {
            "dtxsid": "DTXSID0000001",
            "preferredName": "Offline Example",
            "casrn": "50-00-0",
            "synonyms": ["Formaldehyde", "Methanal"],
        }

    def get_last_metadata(self) -> Dict[str, Any]:
        return dict(self._metadata)


class _OfflineHazardResource:
    def __init__(self) -> None:
        self._metadata: Dict[str, Any] = {}

    def search_hazard(
        self, data_type: str, dtxsid: str, summary: bool = True
    ) -> list[dict[str, Any]]:
        self._metadata = {"status": 200}
        return [{"endpoint": "Acute toxicity", "value": "LD50", "source": "Offline"}]

    def get_last_metadata(self) -> Dict[str, Any]:
        return dict(self._metadata)


class _OfflineExposureResource:
    def __init__(self) -> None:
        self._metadata: Dict[str, Any] = {}

    def search_httk(self, dtxsids: Sequence[str]) -> list[dict[str, Any]]:
        self._metadata = {"status": 200}
        return [{"kmp": 1.2, "unit": "1/hr"}]

    def search_cpdat(
        self, vocab_name: str, dtxsids: Sequence[str]
    ) -> list[dict[str, Any]]:
        self._metadata = {"status": 200}
        return [{"vocab": vocab_name, "label": "Consumer product"}]

    def search_qsurs(self, dtxsids: Sequence[str]) -> list[dict[str, Any]]:
        self._metadata = {"status": 200}
        return [{"probability": 0.42}]

    def search_exposures(
        self, data_type: str, dtxsids: Sequence[str]
    ) -> list[dict[str, Any]]:
        self._metadata = {"status": 200}
        return [{"dataset": data_type, "value": "offline"}]

    def get_last_metadata(self) -> Dict[str, Any]:
        return dict(self._metadata)


class _OfflineCheminformaticsResource:
    def __init__(self) -> None:
        self._metadata: Dict[str, Any] = {}

    def search_toxprints(self, chemical: str) -> dict[str, Any]:
        self._metadata = {"status": 200}
        return {"toxprints": ["FP_001", "FP_057"]}

    def get_last_metadata(self) -> Dict[str, Any]:
        return dict(self._metadata)


class OfflinePredictiveService(PredictiveServiceBase):
    """Predictive service stub returning deterministic GenRA-like results."""

    def __init__(self) -> None:
        super().__init__(
            config={
                "name": "Offline GenRA",
                "version": "0.1",
                "ad_model_name": "Offline GenRA",
            }
        )

    def _predict_impl(self, request: PredictiveRequest) -> Dict[str, Any]:
        return {
            "prediction": "Read-across suggests low concern.",
            "confidence": 0.82,
        }

    def _check_ad_impl(self, request: PredictiveRequest) -> ADCheckResult:
        return ADCheckResult(in_domain=True, confidence=0.85, details={"analogues": 4})

    def _build_metadata(
        self, request: PredictiveRequest, ad_result: ADCheckResult
    ) -> Dict[str, Any]:
        metadata = super()._build_metadata(request, ad_result)
        metadata.update(
            {
                "analogueCoverage": 0.88,
                "evidenceQuality": 0.74,
                "predictiveAgreement": ad_result.confidence,
            }
        )
        return metadata


def build_offline_orchestrator(
    *,
    persistence_dir: Optional[Path] = None,
    clock: Optional[Callable[[], str]] = None,
) -> GenRAOrchestrator:
    """Construct an orchestrator wired with offline stub resources."""
    resolver = IdentifierResolver(
        chemical_resource=_OfflineChemicalResource(), cache_ttl=0
    )
    assembler = CtxDataAssembler(
        hazard_resource=_OfflineHazardResource(),
        exposure_resource=_OfflineExposureResource(),
        cheminformatics_resource=_OfflineCheminformaticsResource(),
        include_toxprints=True,
        cache_ttl=0,
    )
    predictive_service = OfflinePredictiveService()
    coordinator = PredictiveCoordinator({"offline_genra": predictive_service})
    return GenRAOrchestrator(
        identifier_resolver=resolver,
        ctx_data_assembler=assembler,
        predictive_coordinator=coordinator,
        persistence_dir=persistence_dir,
        evidence_synthesizer=EvidenceSynthesizer(),
        clock=clock or (lambda: ""),
    )


__all__ = [
    "OFFLINE_SCENARIOS",
    "build_offline_orchestrator",
    "OfflinePredictiveService",
]
