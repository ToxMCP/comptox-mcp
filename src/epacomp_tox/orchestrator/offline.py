from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence

from epacomp_tox.resources.interop import InteropResource

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
    name = "chemical"

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
    name = "hazard"

    def __init__(self) -> None:
        self._metadata: Dict[str, Any] = {}

    def search_hazard(
        self, data_type: str, dtxsid: str, summary: bool = True
    ) -> list[dict[str, Any]]:
        self._metadata = {"status": 200}
        return [{"endpoint": "Acute toxicity", "value": "LD50", "source": "Offline"}]

    def get_hazard_toxval(self, dtxsid: str) -> list[dict[str, Any]]:
        self._metadata = {"status": 200}
        return [{"endpoint": "Acute toxicity", "value": 1.1, "unit": "log_mg_kg"}]

    def get_hazard_toxref(
        self, dataset: str, lookup_type: str, value: str
    ) -> list[dict[str, Any]]:
        self._metadata = {"status": 200}
        return [
            {
                "dataset": dataset,
                "lookupType": lookup_type,
                "dtxsid": value,
                "endpoint": "Acute toxicity",
                "value": 1.0,
                "unit": "log_mg_kg",
                "source": "Offline ToxRefDB",
            }
        ]

    def get_hazard_cancer_summary(self, dtxsid: str) -> list[dict[str, Any]]:
        self._metadata = {"status": 200}
        return [
            {
                "endpoint": "Cancer",
                "value": "No clear signal",
                "source": "Offline cancer summary",
            }
        ]

    def get_hazard_genetox_summary(self, dtxsid: str) -> list[dict[str, Any]]:
        self._metadata = {"status": 200}
        return [
            {
                "endpoint": "Genotoxicity",
                "value": "Negative",
                "source": "Offline genetox summary",
            }
        ]

    def get_hazard_adme_ivive(self, dtxsid: str) -> list[dict[str, Any]]:
        self._metadata = {"status": 200}
        return [{"intrinsicClearance": 0.91, "parameter": "CLint", "unit": "L/h/kg"}]

    def get_hazard_iris(self, dtxsid: str) -> list[dict[str, Any]]:
        self._metadata = {"status": 200}
        return [
            {
                "endpoint": "Reference dose",
                "value": 0.01,
                "unit": "mg/kg-day",
                "source": "Offline IRIS",
            }
        ]

    def get_hazard_pprtv(self, dtxsid: str) -> list[dict[str, Any]]:
        self._metadata = {"status": 200}
        return [
            {
                "endpoint": "Screening value",
                "value": 0.02,
                "unit": "mg/kg-day",
                "source": "Offline PPRTV",
            }
        ]

    def get_hazard_hawc(self, dtxsid: str) -> list[dict[str, Any]]:
        self._metadata = {"status": 200}
        return [
            {
                "endpoint": "Study evaluation",
                "value": "Included",
                "source": "Offline HAWC",
            }
        ]

    def get_last_metadata(self) -> Dict[str, Any]:
        return dict(self._metadata)


class _OfflineExposureResource:
    name = "exposure"

    def __init__(self) -> None:
        self._metadata: Dict[str, Any] = {}

    def search_httk(self, dtxsids: Sequence[str]) -> list[dict[str, Any]]:
        self._metadata = {"status": 200}
        return [{"kmp": 1.2, "unit": "1/hr"}]

    def get_exposure_httk(self, dtxsid: str) -> list[dict[str, Any]]:
        self._metadata = {"status": 200}
        return [
            {
                "fractionUnboundPlasma": 0.07,
                "intrinsicClearance": 1.2,
                "parameter": "CLint",
                "unit": "L/h/kg",
            }
        ]

    def search_cpdat(
        self, vocab_name: str, dtxsids: Sequence[str]
    ) -> list[dict[str, Any]]:
        self._metadata = {"status": 200}
        return [{"vocab": vocab_name, "label": "Consumer product"}]

    def get_seem_general(self, dtxsid: str) -> list[dict[str, Any]]:
        self._metadata = {"status": 200}
        return [{"medianExposure": 0.12, "unit": "mg/kg-day"}]

    def search_qsurs(self, dtxsids: Sequence[str]) -> list[dict[str, Any]]:
        self._metadata = {"status": 200}
        return [{"probability": 0.42}]

    def get_exposure_mmdb_aggregate_by_dtxsid(
        self, dtxsid: str
    ) -> list[dict[str, Any]]:
        self._metadata = {"status": 200}
        return [{"studyCount": 2, "endpoint": "plasma_concentration"}]

    def search_exposures(
        self, data_type: str, dtxsids: Sequence[str]
    ) -> list[dict[str, Any]]:
        self._metadata = {"status": 200}
        return [{"dataset": data_type, "value": "offline"}]

    def get_last_metadata(self) -> Dict[str, Any]:
        return dict(self._metadata)


class _OfflineCheminformaticsResource:
    name = "cheminformatics"

    def __init__(self) -> None:
        self._metadata: Dict[str, Any] = {}

    def search_toxprints(self, chemical: str) -> dict[str, Any]:
        self._metadata = {"status": 200}
        return {"toxprints": ["FP_001", "FP_057"]}

    def get_last_metadata(self) -> Dict[str, Any]:
        return dict(self._metadata)


class _OfflineBioactivityResource:
    name = "bioactivity"

    def __init__(self) -> None:
        self._metadata: Dict[str, Any] = {}

    def get_bioactivity_summary_by_dtxsid(self, dtxsid: str) -> list[dict[str, Any]]:
        self._metadata = {"status": 200}
        return [
            {
                "aeid": "123",
                "assayName": "Offline PPAR assay",
                "targetName": "PPARG",
                "geneSymbol": "PPARG",
                "activityDirection": "activation",
                "ac50": 3.2,
                "unit": "uM",
                "hitcall": 1,
            }
        ]

    def get_bioactivity_aop(self, lookup_type: str, aeid: str) -> list[dict[str, Any]]:
        self._metadata = {"status": 200}
        return [
            {
                "aopId": "AOP:42",
                "aopTitle": "Offline liver steatosis",
                "eventType": "molecular_initiating_event",
                "eventLabel": "PPARG activation",
                "confidence": 0.8,
            }
        ]

    def get_last_metadata(self) -> Dict[str, Any]:
        return dict(self._metadata)


class _OfflineMetadataResource:
    name = "metadata"

    def __init__(self) -> None:
        self._metadata: Dict[str, Any] = {}

    def execute_tool(
        self, tool_name: str, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        self._metadata = {"status": 200}
        if tool_name != "metadata_get_model_card":
            raise ValueError(f"Unsupported tool: {tool_name}")
        return {
            "modelCards": [
                {
                    "card": {
                        "modelDetails": {
                            "name": "Offline HTTK Context",
                            "version": "0.1",
                            "modelType": "PBPK",
                        },
                        "intendedUse": {
                            "limitations": ["Offline model-card placeholder."],
                            "warnings": [],
                        },
                        "oecdValidationPrinciples": {
                            "definedEndpoint": {
                                "description": "internal dose metrics",
                            }
                        },
                    }
                }
            ]
        }

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
        self,
        request: PredictiveRequest,
        ad_result: ADCheckResult,
        prediction_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        metadata = super()._build_metadata(request, ad_result, prediction_payload)
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
    bioactivity_resource = _OfflineBioactivityResource()
    resolver = IdentifierResolver(
        chemical_resource=_OfflineChemicalResource(), cache_ttl=0
    )
    assembler = CtxDataAssembler(
        hazard_resource=_OfflineHazardResource(),
        exposure_resource=_OfflineExposureResource(),
        cheminformatics_resource=_OfflineCheminformaticsResource(),
        bioactivity_resource=bioactivity_resource,
        include_toxprints=True,
        cache_ttl=0,
    )
    interop_resource = InteropResource(
        api_key="offline",
        chemical_resource=_OfflineChemicalResource(),
        bioactivity_resource=bioactivity_resource,
        exposure_resource=_OfflineExposureResource(),
        hazard_resource=_OfflineHazardResource(),
        metadata_resource=_OfflineMetadataResource(),
    )
    predictive_service = OfflinePredictiveService()
    coordinator = PredictiveCoordinator({"offline_genra": predictive_service})
    return GenRAOrchestrator(
        identifier_resolver=resolver,
        ctx_data_assembler=assembler,
        predictive_coordinator=coordinator,
        persistence_dir=persistence_dir,
        evidence_synthesizer=EvidenceSynthesizer(),
        interop_resource=interop_resource,
        clock=clock or (lambda: ""),
    )


__all__ = [
    "OFFLINE_SCENARIOS",
    "build_offline_orchestrator",
    "OfflinePredictiveService",
]
