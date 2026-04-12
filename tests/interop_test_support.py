from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Sequence

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from epacomp_tox.resources.interop import InteropResource

SCHEMAS_DIR = Path(__file__).resolve().parents[1] / "schemas"


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def _schema_registry() -> Registry:
    registry = Registry()
    for path in sorted(SCHEMAS_DIR.glob("*.json")):
        schema = _load_json(path)
        schema_id = schema.get("$id")
        if schema_id:
            registry = registry.with_resource(schema_id, Resource.from_contents(schema))
    return registry


def validate_portable_schema(schema_name: str, instance: Dict[str, Any]) -> None:
    schema = _load_json(SCHEMAS_DIR / schema_name)
    Draft202012Validator(schema, registry=_schema_registry()).validate(instance)


class StubResource:
    def __init__(self, name: str) -> None:
        self.name = name
        self._last_metadata = {"resource": name, "requestId": f"{name}-request"}

    def get_last_metadata(self) -> Dict[str, Any]:
        return dict(self._last_metadata)


class StubChemicalResource(StubResource):
    def __init__(self) -> None:
        super().__init__("chemical")

    def search_chemical(self, query: str, search_type: str) -> List[Dict[str, Any]]:
        assert search_type == "equals"
        return [
            {
                "dtxsid": "DTXSID7020182",
                "preferredName": "Bisphenol A",
                "casrn": "80-05-7",
                "inchikey": "IWEXDIRZYOAJPZ-UHFFFAOYSA-N",
                "smiles": "CC(C)(C1=CC=C(C=C1)O)C2=CC=C(C=C2)O",
                "synonyms": ["BPA", "Bisphenol-A"],
            }
        ]

    def get_chemical_details(
        self, identifier: str, id_type: str, subset: str = "default"
    ) -> Dict[str, Any]:
        return {
            "dtxsid": "DTXSID7020182",
            "preferredName": "Bisphenol A",
            "casrn": "80-05-7",
            "smiles": "CC(C)(C1=CC=C(C=C1)O)C2=CC=C(C=C2)O",
            "synonyms": ["BPA", "Bisphenol-A"],
        }

    def resolve_chemical_identifier(
        self,
        *,
        identifier: str,
        identifier_type: str | None = None,
        allow_fallback: bool = False,
        max_candidates: int = 5,
    ) -> Dict[str, Any]:
        return {
            "status": "resolved",
            "inputIdentifier": identifier,
            "inputType": identifier_type or "casrn",
            "canonicalDtxsid": "DTXSID7020182",
            "preferredName": "Bisphenol A",
            "casrn": "80-05-7",
            "searchModeUsed": "equals",
            "candidateCount": 1,
            "candidates": [
                {
                    "dtxsid": "DTXSID7020182",
                    "preferredName": "Bisphenol A",
                    "casrn": "80-05-7",
                }
            ],
            "warnings": [],
        }


class StubHazardResource(StubResource):
    def __init__(self) -> None:
        super().__init__("hazard")

    def get_hazard_toxval(self, dtxsid: str) -> List[Dict[str, Any]]:
        return [{"effect": "NOAEL", "value": 40, "unit": "mg/kg-day"}]

    def get_hazard_adme_ivive(self, dtxsid: str) -> List[Dict[str, Any]]:
        return [
            {
                "intrinsicClearance": 0.91,
                "parameter": "CLint",
                "unit": "uL/min/10^6 cells",
                "assay": "hepatocyte",
            }
        ]


class StubExposureResource(StubResource):
    def __init__(self) -> None:
        super().__init__("exposure")

    def search_cpdat(
        self, query_type: str, values: Sequence[str]
    ) -> List[Dict[str, Any]]:
        return [{"productUseCategory": "food-contact", "name": values[0]}]

    def get_seem_general(self, dtxsid: str) -> List[Dict[str, Any]]:
        return [{"medianExposure": 0.12, "unit": "mg/kg-day"}]

    def get_exposure_httk(self, dtxsid: str) -> List[Dict[str, Any]]:
        return [
            {
                "fractionUnboundPlasma": 0.07,
                "intrinsicClearance": 1.2,
                "parameter": "CLint",
                "unit": "L/h/kg",
            }
        ]

    def get_exposure_mmdb_aggregate_by_dtxsid(
        self, dtxsid: str
    ) -> List[Dict[str, Any]]:
        return [{"studyCount": 3, "endpoint": "plasma_concentration"}]

    def search_qsurs(self, values: Sequence[str]) -> List[Dict[str, Any]]:
        return [{"useDescriptor": "thermal-paper", "probability": 0.83}]


class StubBioactivityResource(StubResource):
    def __init__(self) -> None:
        super().__init__("bioactivity")

    def get_bioactivity_aed(self, dtxsid: str) -> List[Dict[str, Any]]:
        return [
            {
                "aeid": "123",
                "aedVal": 6.0,
                "aedType": "administered_equivalent_dose",
                "aedValUnit": "mg/kg-day",
                "httkModel": "3compartment",
                "httkVersion": "3.0",
            }
        ]

    def get_bioactivity_summary_by_dtxsid(self, dtxsid: str) -> List[Dict[str, Any]]:
        return [
            {
                "aeid": "123",
                "assayName": "PPAR activation assay",
                "targetName": "PPARG",
                "geneSymbol": "PPARG",
                "targetFamily": "nuclear receptor",
                "activityDirection": "activation",
                "ac50": 3.2,
                "unit": "uM",
                "hitcall": 1,
            },
            {
                "aeid": "456",
                "assayName": "AhR reporter assay",
                "targetName": "AHR",
                "geneSymbol": "AHR",
                "targetFamily": "transcription factor",
                "assayComponent": "reporter",
                "ac50": 12.5,
                "unit": "uM",
                "hitCall": False,
            },
        ]

    def get_bioactivity_aop(self, lookup_type: str, aeid: str) -> List[Dict[str, Any]]:
        assert lookup_type == "toxcast-aeid"
        rows = {
            "123": [
                {
                    "aopId": "AOP:42",
                    "aopTitle": "Liver steatosis",
                    "keyEventId": "KE:123",
                    "eventType": "molecular_initiating_event",
                    "eventLabel": "PPARG activation",
                    "relationship": "linked_via_toxcast_aeid",
                    "evidenceDirection": "supports",
                    "confidence": 0.8,
                }
            ],
            "456": [
                {
                    "aopId": "AOP:77",
                    "aopTitle": "Hepatic stress signaling",
                    "eventType": "key_event",
                    "eventLabel": "AHR activation",
                    "mappingScore": 0.55,
                }
            ],
        }
        return rows.get(aeid, [])


class StubMetadataResource(StubResource):
    def __init__(self) -> None:
        super().__init__("metadata")

    def execute_tool(
        self, tool_name: str, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        assert tool_name == "metadata_get_model_card"
        return {
            "modelCards": [
                {
                    "card": {
                        "modelDetails": {
                            "name": "HTTK PBPK Surrogate",
                            "version": "1.0",
                            "description": "Toxicokinetic context model for screening PBPK setup.",
                            "modelType": "PBPK",
                        },
                        "intendedUse": {
                            "limitations": ["Use only for screening contexts."],
                            "warnings": ["Does not perform PBPK simulation itself."],
                        },
                        "oecdValidationPrinciples": {
                            "definedEndpoint": {"description": "internal dose metrics"}
                        },
                    }
                },
                {
                    "card": {
                        "modelDetails": {
                            "name": "Generic QSAR Model",
                            "version": "0.9",
                            "description": "Not a kinetic model.",
                            "modelType": "QSAR",
                        },
                        "oecdValidationPrinciples": {
                            "definedEndpoint": {"description": "acute toxicity"}
                        },
                    }
                },
            ]
        }


def build_interop_resource() -> InteropResource:
    return InteropResource(
        api_key="fake",
        chemical_resource=StubChemicalResource(),
        bioactivity_resource=StubBioactivityResource(),
        exposure_resource=StubExposureResource(),
        hazard_resource=StubHazardResource(),
        metadata_resource=StubMetadataResource(),
    )


def sanitize_aop_handoff(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "chemicalRef": payload["chemicalRef"],
        "lookupMode": payload["lookupMode"],
        "mappings": payload["mappings"],
        "supportingAssays": payload["supportingAssays"],
        "confidence": {
            "score": payload["confidence"]["score"],
            "band": payload["confidence"]["band"],
        },
        "sourceTools": [
            source["toolName"] for source in payload["provenance"]["sources"]
        ],
    }


def sanitize_pbpk_handoff(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "chemicalIdentityRef": {
            "dtxsid": payload["chemicalIdentityRef"]["dtxsid"],
            "preferredName": payload["chemicalIdentityRef"]["preferredName"],
            "casrn": payload["chemicalIdentityRef"].get("casrn"),
        },
        "httkSlice": {
            "recordCount": payload["httkSlice"]["recordCount"],
            "sourceTool": payload["httkSlice"]["sourceTool"],
            "selectedMetrics": payload["httkSlice"].get("selectedMetrics", {}),
        },
        "hazardAdmeIviveSlice": {
            "recordCount": payload["hazardAdmeIviveSlice"]["recordCount"],
            "sourceTool": payload["hazardAdmeIviveSlice"]["sourceTool"],
            "selectedMetrics": payload["hazardAdmeIviveSlice"].get(
                "selectedMetrics", {}
            ),
        },
        "exposureHints": payload["exposureHints"],
        "modelCardRefs": payload["modelCardRefs"],
        "handoffTarget": payload["handoffTarget"],
        "sourceTools": [
            source["toolName"] for source in payload["provenance"]["sources"]
        ],
    }
