from typing import Any, Dict, List
import logging

import ctxpy as ctx

from epacomp_tox.contracts import schema_ref
from .base import BaseResource

logger = logging.getLogger(__name__)


class HazardResource(BaseResource):
    """MCP resource exposing CTX hazard datasets (ToxValDB, ToxRefDB, cancer, genetox, ADME/IVIVE, IRIS, PPRTV, HAWC)."""

    _DATA_TYPE_ENUM = [
        "all",
        "hazard",
        "toxval",
        "human",
        "eco",
        "skin-eye",
        "cancer",
        "genetox",
        "adme",
        "toxref",
        "iris",
        "pprtv",
        "hawc",
    ]

    @staticmethod
    def _schema(name: str) -> Dict[str, str]:
        return schema_ref("common", name)

    @property
    def name(self) -> str:
        return "hazard"

    @property
    def description(self) -> str:
        return (
            "Access to hazard datasets from the CTX APIs, including ToxValDB, ToxRefDB, cancer, "
            "genetox, ADME/IVIVE, IRIS, PPRTV, and HAWC link mappers."
        )

    def __init__(self, api_key: str):
        super().__init__(api_key)
        # Increase upstream timeout for slow queries
        UPSTREAM_TIMEOUT = 120.0
        try:
            self.client = ctx.Hazard(x_api_key=api_key, timeout=UPSTREAM_TIMEOUT)
            logger.info(f"Successfully initialized ctx.Hazard with timeout={UPSTREAM_TIMEOUT}s")
        except TypeError as e:
            logger.warning(
                f"Could not set timeout for ctx.Hazard (TypeError: {e}). Using default timeout."
            )
            self.client = ctx.Hazard(x_api_key=api_key)

    def _clean_identifiers(self, identifiers: List[str]) -> List[str]:
        return [
            value.strip()
            for value in identifiers
            if isinstance(value, str) and value.strip()
        ]

    def get_tools(self) -> List[Dict[str, Any]]:
        tools: List[Dict[str, Any]] = [
            {
                "name": "search_hazard",
                "description": "Search for hazard data by DTXSID across ToxValDB, ToxRefDB, cancer, genetox, ADME/IVIVE, IRIS, PPRTV, or HAWC datasets.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "data_type": {
                            "type": "string",
                            "description": "Hazard dataset to query.",
                            "enum": self._DATA_TYPE_ENUM,
                        },
                        "dtxsid": {
                            "type": "string",
                            "description": "Chemical identifier (DTXSID).",
                        },
                        "summary": {
                            "type": "boolean",
                            "description": "Whether to request summary (vs. detailed) data when supported.",
                            "default": True,
                        },
                    },
                    "required": ["data_type", "dtxsid"],
                },
            },
            {
                "name": "batch_search_hazard",
                "description": "Batch hazard lookup for multiple DTXSIDs for the selected dataset.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "data_type": {
                            "type": "string",
                            "description": "Hazard dataset to query.",
                            "enum": self._DATA_TYPE_ENUM,
                        },
                        "dtxsids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "description": "List of chemical identifiers (DTXSIDs).",
                        },
                        "summary": {
                            "type": "boolean",
                            "description": "Whether to request summary (vs. detailed) data when supported.",
                            "default": True,
                        },
                    },
                    "required": ["data_type", "dtxsids"],
                },
            },
            {
                "name": "get_hazard_toxval",
                "description": "Retrieve full ToxValDB hazard data for a single chemical.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dtxsid": {
                            "type": "string",
                            "description": "Chemical identifier (DTXSID).",
                        }
                    },
                    "required": ["dtxsid"],
                },
            },
            {
                "name": "batch_get_hazard_toxval",
                "description": "Retrieve ToxValDB hazard data for multiple chemicals.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dtxsids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "description": "Chemical identifiers (DTXSIDs).",
                        }
                    },
                    "required": ["dtxsids"],
                },
            },
            {
                "name": "get_hazard_skin_eye",
                "description": "Retrieve skin and eye hazard data for a single chemical.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dtxsid": {"type": "string", "description": "Chemical identifier (DTXSID)."}
                    },
                    "required": ["dtxsid"],
                },
            },
            {
                "name": "batch_get_hazard_skin_eye",
                "description": "Retrieve skin and eye hazard data for multiple chemicals.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dtxsids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "description": "Chemical identifiers (DTXSIDs).",
                        }
                    },
                    "required": ["dtxsids"],
                },
            },
            {
                "name": "get_hazard_cancer_summary",
                "description": "Retrieve cancer hazard summary for a single chemical.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dtxsid": {"type": "string", "description": "Chemical identifier (DTXSID)."}
                    },
                    "required": ["dtxsid"],
                },
            },
            {
                "name": "batch_get_hazard_cancer_summary",
                "description": "Retrieve cancer hazard summary for multiple chemicals.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dtxsids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "description": "Chemical identifiers (DTXSIDs).",
                        }
                    },
                    "required": ["dtxsids"],
                },
            },
            {
                "name": "get_hazard_genetox_summary",
                "description": "Retrieve genotoxicity summary data for a chemical.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dtxsid": {"type": "string", "description": "Chemical identifier (DTXSID)."}
                    },
                    "required": ["dtxsid"],
                },
            },
            {
                "name": "batch_get_hazard_genetox_summary",
                "description": "Retrieve genotoxicity summary data for multiple chemicals.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dtxsids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "description": "Chemical identifiers (DTXSIDs).",
                        }
                    },
                    "required": ["dtxsids"],
                },
            },
            {
                "name": "get_hazard_genetox_details",
                "description": "Retrieve genotoxicity detailed data for a chemical.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dtxsid": {"type": "string", "description": "Chemical identifier (DTXSID)."}
                    },
                    "required": ["dtxsid"],
                },
            },
            {
                "name": "batch_get_hazard_genetox_details",
                "description": "Retrieve genotoxicity detailed data for multiple chemicals.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dtxsids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "description": "Chemical identifiers (DTXSIDs).",
                        }
                    },
                    "required": ["dtxsids"],
                },
            },
            {
                "name": "get_hazard_adme_ivive",
                "description": "Retrieve ADME/IVIVE hazard data for a chemical.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dtxsid": {"type": "string", "description": "Chemical identifier (DTXSID)."}
                    },
                    "required": ["dtxsid"],
                },
            },
            {
                "name": "get_hazard_pprtv",
                "description": "Retrieve PPRTV hazard data for a chemical.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dtxsid": {"type": "string", "description": "Chemical identifier (DTXSID)."}
                    },
                    "required": ["dtxsid"],
                },
            },
            {
                "name": "get_hazard_iris",
                "description": "Retrieve IRIS hazard data for a chemical.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dtxsid": {"type": "string", "description": "Chemical identifier (DTXSID)."}
                    },
                    "required": ["dtxsid"],
                },
            },
            {
                "name": "get_hazard_hawc",
                "description": "Retrieve HAWC link mapper data for a chemical.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dtxsid": {"type": "string", "description": "Chemical identifier (DTXSID)."}
                    },
                    "required": ["dtxsid"],
                },
            },
            {
                "name": "get_hazard_toxref",
                "description": "Retrieve ToxRefDB data (summary, data, effects, or observations) by DTXSID, study ID, or study type.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dataset": {
                            "type": "string",
                            "enum": ["summary", "data", "effects", "observations"],
                            "description": "ToxRefDB dataset to query.",
                        },
                        "lookup_type": {
                            "type": "string",
                            "enum": ["dtxsid", "study-id", "study-type"],
                            "description": "Lookup mode for the query.",
                        },
                        "value": {
                            "type": "string",
                            "description": "Identifier corresponding to the selected lookup type.",
                        },
                    },
                    "required": ["dataset", "lookup_type", "value"],
                },
            },
            {
                "name": "batch_get_hazard_toxref",
                "description": "Batch retrieve ToxRefDB data by DTXSID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dtxsids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "description": "Chemical identifiers (DTXSIDs).",
                        }
                    },
                    "required": ["dtxsids"],
                },
            },
        ]
        for tool in tools:
            schema_name = (
                "mapping_list_generic.response.schema"
                if tool["name"] == "batch_search_hazard"
                else "list_generic.response.schema"
            )
            tool["responseSchemaRef"] = self._schema(schema_name)
            
            # Ensure outputSchema is populated from the reference
            if "responseSchemaRef" in tool:
                from epacomp_tox.contracts import load_schema
                ref = tool["responseSchemaRef"]
                tool["outputSchema"] = load_schema(ref["namespace"], ref["name"])
                
        return tools

    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        handlers = {
            "search_hazard": lambda params: self.search_hazard(
                data_type=params["data_type"],
                dtxsid=params["dtxsid"],
                summary=params.get("summary", True),
            ),
            "batch_search_hazard": lambda params: self.batch_search_hazard(
                data_type=params["data_type"],
                dtxsids=params["dtxsids"],
                summary=params.get("summary", True),
            ),
            "get_hazard_toxval": lambda params: self.get_hazard_toxval(params["dtxsid"]),
            "batch_get_hazard_toxval": lambda params: self.batch_get_hazard_toxval(params["dtxsids"]),
            "get_hazard_skin_eye": lambda params: self.get_hazard_skin_eye(params["dtxsid"]),
            "batch_get_hazard_skin_eye": lambda params: self.batch_get_hazard_skin_eye(params["dtxsids"]),
            "get_hazard_cancer_summary": lambda params: self.get_hazard_cancer_summary(params["dtxsid"]),
            "batch_get_hazard_cancer_summary": lambda params: self.batch_get_hazard_cancer_summary(params["dtxsids"]),
            "get_hazard_genetox_summary": lambda params: self.get_hazard_genetox_summary(params["dtxsid"]),
            "batch_get_hazard_genetox_summary": lambda params: self.batch_get_hazard_genetox_summary(params["dtxsids"]),
            "get_hazard_genetox_details": lambda params: self.get_hazard_genetox_details(params["dtxsid"]),
            "batch_get_hazard_genetox_details": lambda params: self.batch_get_hazard_genetox_details(params["dtxsids"]),
            "get_hazard_adme_ivive": lambda params: self.get_hazard_adme_ivive(params["dtxsid"]),
            "get_hazard_pprtv": lambda params: self.get_hazard_pprtv(params["dtxsid"]),
            "get_hazard_iris": lambda params: self.get_hazard_iris(params["dtxsid"]),
            "get_hazard_hawc": lambda params: self.get_hazard_hawc(params["dtxsid"]),
            "get_hazard_toxref": lambda params: self.get_hazard_toxref(
                dataset=params["dataset"],
                lookup_type=params["lookup_type"],
                value=params["value"],
            ),
            "batch_get_hazard_toxref": lambda params: self.batch_get_hazard_toxref(params["dtxsids"]),
        }

        try:
            handler = handlers[tool_name]
        except KeyError as exc:  # pragma: no cover - defensive
            raise ValueError(f"Unknown tool: {tool_name}") from exc
        return handler(parameters)

    def search_hazard(self, data_type: str, dtxsid: str, summary: bool = True) -> List[Dict[str, Any]]:
        """
        Search hazard datasets for a chemical.

        Args:
            data_type: Hazard dataset to query (all, hazard, toxval, human, eco, skin-eye, cancer, genetox, adme, toxref, iris, pprtv, hawc).
            dtxsid: Chemical identifier (DTXSID).
            summary: Whether to request summary data when the API supports a detail toggle.

        Returns:
            List of hazard data records.
        """
        result = self._with_retry(
            lambda: self.client.search(by=data_type, dtxsid=dtxsid, summary=summary)
        )
        return self._ensure_list(result)

    def batch_search_hazard(
        self,
        data_type: str,
        dtxsids: List[str],
        summary: bool = True,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search hazard datasets for multiple chemicals.

        Args:
            data_type: Hazard dataset to query.
            dtxsids: List of DTXSIDs.
            summary: Whether to request summary data when supported.

        Returns:
            Mapping of DTXSID to hazard records.
        """
        cleaned = self._clean_identifiers(dtxsids)
        if not cleaned:
            return {}
        payload = self._with_retry(
            lambda: self.client.batch_search(by=data_type, dtxsid=cleaned, summary=summary)
        )
        normalized = self._ensure_object(payload)
        return {key: self._ensure_list(value) for key, value in normalized.items()}

    def get_hazard_toxval(self, dtxsid: str) -> List[Dict[str, Any]]:
        payload = self._with_retry(lambda: self.client.toxval(dtxsid=dtxsid))
        return self._ensure_list(payload)

    def batch_get_hazard_toxval(self, dtxsids: List[str]) -> List[Dict[str, Any]]:
        cleaned = self._clean_identifiers(dtxsids)
        if not cleaned:
            return []
        payload = self._with_retry(lambda: self.client.toxval_batch(dtxsids=cleaned))
        return self._ensure_list(payload)

    def get_hazard_skin_eye(self, dtxsid: str) -> List[Dict[str, Any]]:
        payload = self._with_retry(lambda: self.client.skin_eye(dtxsid=dtxsid))
        return self._ensure_list(payload)

    def batch_get_hazard_skin_eye(self, dtxsids: List[str]) -> List[Dict[str, Any]]:
        cleaned = self._clean_identifiers(dtxsids)
        if not cleaned:
            return []
        payload = self._with_retry(lambda: self.client.skin_eye_batch(dtxsids=cleaned))
        return self._ensure_list(payload)

    def get_hazard_cancer_summary(self, dtxsid: str) -> List[Dict[str, Any]]:
        payload = self._with_retry(lambda: self.client.cancer_summary(dtxsid=dtxsid))
        return self._ensure_list(payload)

    def batch_get_hazard_cancer_summary(self, dtxsids: List[str]) -> List[Dict[str, Any]]:
        cleaned = self._clean_identifiers(dtxsids)
        if not cleaned:
            return []
        payload = self._with_retry(lambda: self.client.cancer_summary_batch(dtxsids=cleaned))
        return self._ensure_list(payload)

    def get_hazard_genetox_summary(self, dtxsid: str) -> List[Dict[str, Any]]:
        payload = self._with_retry(lambda: self.client.genetox_summary(dtxsid=dtxsid))
        return self._ensure_list(payload)

    def batch_get_hazard_genetox_summary(self, dtxsids: List[str]) -> List[Dict[str, Any]]:
        cleaned = self._clean_identifiers(dtxsids)
        if not cleaned:
            return []
        payload = self._with_retry(lambda: self.client.genetox_summary_batch(dtxsids=cleaned))
        return self._ensure_list(payload)

    def get_hazard_genetox_details(self, dtxsid: str) -> List[Dict[str, Any]]:
        payload = self._with_retry(lambda: self.client.genetox_details(dtxsid=dtxsid))
        return self._ensure_list(payload)

    def batch_get_hazard_genetox_details(self, dtxsids: List[str]) -> List[Dict[str, Any]]:
        cleaned = self._clean_identifiers(dtxsids)
        if not cleaned:
            return []
        payload = self._with_retry(lambda: self.client.genetox_details_batch(dtxsids=cleaned))
        return self._ensure_list(payload)

    def get_hazard_adme_ivive(self, dtxsid: str) -> List[Dict[str, Any]]:
        payload = self._with_retry(lambda: self.client.adme_ivive(dtxsid=dtxsid))
        return self._ensure_list(payload)

    def get_hazard_pprtv(self, dtxsid: str) -> List[Dict[str, Any]]:
        payload = self._with_retry(lambda: self.client.pprtv(dtxsid=dtxsid))
        return self._ensure_list(payload)

    def get_hazard_iris(self, dtxsid: str) -> List[Dict[str, Any]]:
        payload = self._with_retry(lambda: self.client.iris(dtxsid=dtxsid))
        return self._ensure_list(payload)

    def get_hazard_hawc(self, dtxsid: str) -> List[Dict[str, Any]]:
        payload = self._with_retry(lambda: self.client.hawc(dtxsid=dtxsid))
        return self._ensure_list(payload)

    def get_hazard_toxref(self, dataset: str, lookup_type: str, value: str) -> List[Dict[str, Any]]:
        payload = self._with_retry(
            lambda: self.client.toxref(dataset=dataset, lookup=lookup_type, value=value)
        )
        return self._ensure_list(payload)

    def batch_get_hazard_toxref(self, dtxsids: List[str]) -> List[Dict[str, Any]]:
        cleaned = self._clean_identifiers(dtxsids)
        if not cleaned:
            return []
        payload = self._with_retry(lambda: self.client.toxref_batch(dtxsids=cleaned))
        return self._ensure_list(payload)
