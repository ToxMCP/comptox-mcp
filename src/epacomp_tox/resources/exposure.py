import logging
from typing import Any, Dict, List, Optional, Sequence

import ctxpy as ctx
from epacomp_tox.contracts import schema_ref

from .base import BaseResource

logger = logging.getLogger(__name__)


class ExposureResource(BaseResource):
    """MCP resource for EPA CompTox exposure data."""

    @property
    def name(self) -> str:
        return "exposure"

    @property
    def description(self) -> str:
        return "Access to SEEM predictions, CPDat product data, HTTK, MMDB monitoring, and CCD datasets"

    def __init__(self, api_key: str):
        super().__init__(api_key)
        # Increase upstream timeout for slow queries
        UPSTREAM_TIMEOUT = 120.0
        try:
            self.client = ctx.Exposure(x_api_key=api_key, timeout=UPSTREAM_TIMEOUT)
            logger.info(
                f"Successfully initialized ctx.Exposure with timeout={UPSTREAM_TIMEOUT}s"
            )
        except TypeError as e:
            logger.warning(
                f"Could not set timeout for ctx.Exposure (TypeError: {e}). Using default timeout."
            )
            self.client = ctx.Exposure(x_api_key=api_key)

    # ------------------------------------------------------------------
    # Tool catalog
    # ------------------------------------------------------------------
    def get_tools(self) -> List[Dict[str, Any]]:
        tools: List[Dict[str, Any]] = [
            {
                "name": "search_cpdat",
                "description": "Search historical CPDat data (functional use, product use categories, or list presence) for chemicals",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "vocab_name": {
                            "type": "string",
                            "enum": ["fc", "puc", "lpk"],
                            "description": "Vocabulary domain to query: functional use (fc), product use categories (puc), or list presence keywords (lpk)",
                        },
                        "dtxsid": {
                            "type": "string",
                            "description": "Optional single DSSTox ID",
                        },
                        "dtxsids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of DSSTox IDs (max 200 per batch)",
                        },
                    },
                    "required": ["vocab_name"],
                },
            },
            {
                "name": "search_httk",
                "description": "Search for high-throughput toxicokinetics (HTTK) data",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dtxsid": {
                            "type": "string",
                            "description": "Optional single DSSTox ID",
                        },
                        "dtxsids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of DSSTox IDs",
                        },
                    },
                    "required": [],
                },
            },
            {
                "name": "get_cpdat_vocabulary",
                "description": "Return CPDat controlled vocabulary values (functional use, product use categories, or list presence tags)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "vocab_name": {
                            "type": "string",
                            "enum": ["fc", "puc", "lpk"],
                            "description": "Vocabulary domain to list",
                        }
                    },
                    "required": ["vocab_name"],
                },
            },
            {
                "name": "search_qsurs",
                "description": "Retrieve QSUR model functional-use probability predictions",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dtxsid": {
                            "type": "string",
                            "description": "Optional single DSSTox ID",
                        },
                        "dtxsids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of DSSTox IDs",
                        },
                    },
                    "required": [],
                },
            },
            {
                "name": "search_exposures",
                "description": "Backwards-compatible exposure search across pathways/MMDB/SEEM datasets",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "data_type": {
                            "type": "string",
                            "enum": [
                                "pathways",
                                "mmdb-single",
                                "seem",
                                "seem-demographic",
                            ],
                            "description": "Legacy exposure dataset selector",
                        },
                        "dtxsid": {
                            "type": "string",
                            "description": "Optional single DSSTox ID",
                        },
                        "dtxsids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of DSSTox IDs",
                        },
                    },
                    "required": ["data_type"],
                },
            },
        ]

        # Additional granular tools (single-item retrievals)
        tools.extend(
            [
                _single_id_tool(
                    "get_seem_general", "Fetch SEEM general exposure predictions"
                ),
                _batch_id_tool(
                    "batch_get_seem_general",
                    "Batch fetch SEEM general exposure predictions",
                ),
                _single_id_tool(
                    "get_seem_demographic",
                    "Fetch SEEM demographic exposure predictions",
                ),
                _batch_id_tool(
                    "batch_get_seem_demographic",
                    "Batch fetch SEEM demographic exposure predictions",
                ),
                _single_id_tool(
                    "get_exposure_product_data", "Retrieve CPDat product data"
                ),
                _batch_id_tool(
                    "batch_get_exposure_product_data", "Batch fetch CPDat product data"
                ),
                _no_param_tool(
                    "list_exposure_product_puc", "List product use categories (PUC)"
                ),
                _single_id_tool(
                    "get_exposure_list_presence", "Retrieve list presence data"
                ),
                _batch_id_tool(
                    "batch_get_exposure_list_presence", "Batch fetch list presence data"
                ),
                _no_param_tool(
                    "list_exposure_list_presence_tags", "List list-presence tags"
                ),
                _single_id_tool("get_exposure_httk", "Retrieve HTTK data"),
                _batch_id_tool("batch_get_exposure_httk", "Batch fetch HTTK data"),
                _single_id_tool(
                    "get_exposure_functional_use",
                    "Retrieve reported functional use data",
                ),
                _batch_id_tool(
                    "batch_get_exposure_functional_use",
                    "Batch fetch reported functional use data",
                ),
                _single_id_tool(
                    "get_exposure_functional_use_probability",
                    "Retrieve functional use probability predictions",
                ),
                _no_param_tool(
                    "list_exposure_functional_use_categories",
                    "List functional use categories",
                ),
                _single_id_tool(
                    "get_exposure_ccd_puc", "Retrieve CCD Product Use Category data"
                ),
                _single_id_tool(
                    "get_exposure_ccd_production_volume",
                    "Retrieve CCD production volume data",
                ),
                _single_id_tool(
                    "get_exposure_ccd_monitoring_data",
                    "Retrieve CCD biomonitoring data",
                ),
                _single_id_tool(
                    "get_exposure_ccd_keywords", "Retrieve CCD general use keywords"
                ),
                _single_id_tool(
                    "get_exposure_ccd_functional_use",
                    "Retrieve CCD reported functional use data",
                ),
                _single_id_tool(
                    "get_exposure_ccd_chem_weight_fractions",
                    "Retrieve CCD chemical weight fractions data",
                ),
                _str_param_tool(
                    "get_exposure_mmdb_single_sample_by_medium",
                    "medium",
                    "Retrieve MMDB single-sample data filtered by medium",
                ),
                _single_id_tool(
                    "get_exposure_mmdb_single_sample_by_dtxsid",
                    "Retrieve MMDB single-sample data",
                ),
                _no_param_tool(
                    "list_exposure_mmdb_mediums", "List MMDB medium categories"
                ),
                _str_param_tool(
                    "get_exposure_mmdb_aggregate_by_medium",
                    "medium",
                    "Retrieve MMDB aggregate records filtered by medium",
                ),
                _single_id_tool(
                    "get_exposure_mmdb_aggregate_by_dtxsid",
                    "Retrieve MMDB aggregate records",
                ),
            ]
        )

        for tool in tools:
            tool["responseSchemaRef"] = schema_ref(
                "common", "list_generic.response.schema"
            )

            # Ensure outputSchema is populated from the reference
            if "responseSchemaRef" in tool:
                from epacomp_tox.contracts import load_schema

                ref = tool["responseSchemaRef"]
                tool["outputSchema"] = load_schema(ref["namespace"], ref["name"])

        return tools

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------
    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        # Legacy handlers -------------------------------------------------
        if tool_name == "search_cpdat":
            vocab = parameters["vocab_name"]
            identifiers = self._resolve_identifiers(
                parameters.get("dtxsid"),
                parameters.get("dtxsids"),
            )
            return self.search_cpdat(vocab, identifiers)

        if tool_name == "search_httk":
            identifiers = self._resolve_identifiers(
                parameters.get("dtxsid"),
                parameters.get("dtxsids"),
            )
            return self.search_httk(identifiers)

        if tool_name == "get_cpdat_vocabulary":
            return self.get_cpdat_vocabulary(parameters["vocab_name"])

        if tool_name == "search_qsurs":
            identifiers = self._resolve_identifiers(
                parameters.get("dtxsid"),
                parameters.get("dtxsids"),
            )
            return self.search_qsurs(identifiers)

        if tool_name == "search_exposures":
            identifiers = self._resolve_identifiers(
                parameters.get("dtxsid"),
                parameters.get("dtxsids"),
            )
            return self.search_exposures(parameters["data_type"], identifiers)

        # Granular handlers ----------------------------------------------
        handler_map = {
            "get_seem_general": lambda p: self.get_seem_general(p["dtxsid"]),
            "batch_get_seem_general": lambda p: self.batch_get_seem_general(
                p["dtxsids"]
            ),
            "get_seem_demographic": lambda p: self.get_seem_demographic(p["dtxsid"]),
            "batch_get_seem_demographic": lambda p: self.batch_get_seem_demographic(
                p["dtxsids"]
            ),
            "get_exposure_product_data": lambda p: self.get_exposure_product_data(
                p["dtxsid"]
            ),
            "batch_get_exposure_product_data": lambda p: self.batch_get_exposure_product_data(
                p["dtxsids"]
            ),
            "list_exposure_product_puc": lambda p: self.list_exposure_product_puc(),
            "get_exposure_list_presence": lambda p: self.get_exposure_list_presence(
                p["dtxsid"]
            ),
            "batch_get_exposure_list_presence": lambda p: self.batch_get_exposure_list_presence(
                p["dtxsids"]
            ),
            "list_exposure_list_presence_tags": lambda p: self.list_exposure_list_presence_tags(),
            "get_exposure_httk": lambda p: self.get_exposure_httk(p["dtxsid"]),
            "batch_get_exposure_httk": lambda p: self.batch_get_exposure_httk(
                p["dtxsids"]
            ),
            "get_exposure_functional_use": lambda p: self.get_exposure_functional_use(
                p["dtxsid"]
            ),
            "batch_get_exposure_functional_use": lambda p: self.batch_get_exposure_functional_use(
                p["dtxsids"]
            ),
            "get_exposure_functional_use_probability": lambda p: self.get_exposure_functional_use_probability(
                p["dtxsid"]
            ),
            "list_exposure_functional_use_categories": lambda p: self.list_exposure_functional_use_categories(),
            "get_exposure_ccd_puc": lambda p: self.get_exposure_ccd_puc(p["dtxsid"]),
            "get_exposure_ccd_production_volume": lambda p: self.get_exposure_ccd_production_volume(
                p["dtxsid"]
            ),
            "get_exposure_ccd_monitoring_data": lambda p: self.get_exposure_ccd_monitoring_data(
                p["dtxsid"]
            ),
            "get_exposure_ccd_keywords": lambda p: self.get_exposure_ccd_keywords(
                p["dtxsid"]
            ),
            "get_exposure_ccd_functional_use": lambda p: self.get_exposure_ccd_functional_use(
                p["dtxsid"]
            ),
            "get_exposure_ccd_chem_weight_fractions": lambda p: self.get_exposure_ccd_chem_weight_fractions(
                p["dtxsid"]
            ),
            "get_exposure_mmdb_single_sample_by_medium": lambda p: self.get_exposure_mmdb_single_sample_by_medium(
                p["medium"]
            ),
            "get_exposure_mmdb_single_sample_by_dtxsid": lambda p: self.get_exposure_mmdb_single_sample_by_dtxsid(
                p["dtxsid"]
            ),
            "list_exposure_mmdb_mediums": lambda p: self.list_exposure_mmdb_mediums(),
            "get_exposure_mmdb_aggregate_by_medium": lambda p: self.get_exposure_mmdb_aggregate_by_medium(
                p["medium"]
            ),
            "get_exposure_mmdb_aggregate_by_dtxsid": lambda p: self.get_exposure_mmdb_aggregate_by_dtxsid(
                p["dtxsid"]
            ),
        }

        try:
            handler = handler_map[tool_name]
        except KeyError as exc:
            raise ValueError(f"Unknown tool: {tool_name}") from exc
        return handler(parameters)

    # ------------------------------------------------------------------
    # Helper utilities
    # ------------------------------------------------------------------
    def _resolve_identifiers(
        self,
        single: Optional[str],
        multiple: Optional[Sequence[str]],
    ) -> List[str]:
        identifiers: List[str] = []
        if multiple:
            identifiers.extend([item for item in multiple if item])
        if single:
            identifiers.append(single)
        identifiers = [item for item in identifiers if item]
        if not identifiers:
            raise ValueError("At least one DSSTox identifier must be provided.")
        return identifiers

    # ------------------------------------------------------------------
    # Legacy tool implementations
    # ------------------------------------------------------------------
    def search_cpdat(
        self, vocab_name: str, dtxsids: Sequence[str]
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for sid in dtxsids:
            payload = self._with_retry(
                lambda sid=sid: self.client.search_cpdat(vocab_name, sid)
            )
            results.extend(self._ensure_list(payload))
        return results

    def search_httk(self, dtxsids: Sequence[str]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for sid in dtxsids:
            payload = self._with_retry(lambda sid=sid: self.client.search_httk(sid))
            results.extend(self._ensure_list(payload))
        return results

    def get_cpdat_vocabulary(self, vocab_name: str) -> List[Any]:
        payload = self._with_retry(lambda: self.client.get_cpdat_vocabulary(vocab_name))
        return self._ensure_list(payload)

    def search_qsurs(self, dtxsids: Sequence[str]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for sid in dtxsids:
            payload = self._with_retry(lambda sid=sid: self.client.search_qsurs(sid))
            results.extend(self._ensure_list(payload))
        return results

    def search_exposures(self, data_type: str, dtxsids: Sequence[str]) -> List[Any]:
        if not dtxsids:
            raise ValueError("At least one DSSTox identifier must be provided.")
        results: List[Any] = []
        for sid in dtxsids:
            payload = self._with_retry(
                lambda sid=sid: self.client.search_exposures(data_type, sid)
            )
            results.extend(self._ensure_list(payload))
        return results

    # ------------------------------------------------------------------
    # SEEM helpers
    # ------------------------------------------------------------------
    def get_seem_general(self, dtxsid: str) -> List[Dict[str, Any]]:
        result = self._with_retry(lambda: self.client.seem_general(dtxsid))
        return self._ensure_list(result)

    def batch_get_seem_general(self, dtxsids: Sequence[str]) -> List[Any]:
        identifiers = [sid for sid in dtxsids if sid]
        if not identifiers:
            return []
        result = self._with_retry(lambda: self.client.seem_general_batch(identifiers))
        return self._ensure_list(result)

    def get_seem_demographic(self, dtxsid: str) -> List[Dict[str, Any]]:
        result = self._with_retry(lambda: self.client.seem_demographic(dtxsid))
        return self._ensure_list(result)

    def batch_get_seem_demographic(self, dtxsids: Sequence[str]) -> List[Any]:
        identifiers = [sid for sid in dtxsids if sid]
        if not identifiers:
            return []
        result = self._with_retry(
            lambda: self.client.seem_demographic_batch(identifiers)
        )
        return self._ensure_list(result)

    # ------------------------------------------------------------------
    # CPDat product + list presence helpers
    # ------------------------------------------------------------------
    def get_exposure_product_data(self, dtxsid: str) -> List[Dict[str, Any]]:
        result = self._with_retry(lambda: self.client.product_data(dtxsid))
        return self._ensure_list(result)

    def batch_get_exposure_product_data(self, dtxsids: Sequence[str]) -> List[Any]:
        identifiers = [sid for sid in dtxsids if sid]
        if not identifiers:
            return []
        result = self._with_retry(lambda: self.client.product_data_batch(identifiers))
        return self._ensure_list(result)

    def list_exposure_product_puc(self) -> List[Any]:
        result = self._with_retry(self.client.product_data_puc)
        return self._ensure_list(result)

    def get_exposure_list_presence(self, dtxsid: str) -> List[Dict[str, Any]]:
        result = self._with_retry(lambda: self.client.list_presence(dtxsid))
        return self._ensure_list(result)

    def batch_get_exposure_list_presence(self, dtxsids: Sequence[str]) -> List[Any]:
        identifiers = [sid for sid in dtxsids if sid]
        if not identifiers:
            return []
        result = self._with_retry(lambda: self.client.list_presence_batch(identifiers))
        return self._ensure_list(result)

    def list_exposure_list_presence_tags(self) -> List[Any]:
        result = self._with_retry(self.client.list_presence_tags)
        return self._ensure_list(result)

    # ------------------------------------------------------------------
    # HTTK + functional use helpers
    # ------------------------------------------------------------------
    def get_exposure_httk(self, dtxsid: str) -> List[Dict[str, Any]]:
        result = self._with_retry(lambda: self.client.httk(dtxsid))
        return self._ensure_list(result)

    def batch_get_exposure_httk(self, dtxsids: Sequence[str]) -> List[Any]:
        identifiers = [sid for sid in dtxsids if sid]
        if not identifiers:
            return []
        result = self._with_retry(lambda: self.client.httk_batch(identifiers))
        return self._ensure_list(result)

    def get_exposure_functional_use(self, dtxsid: str) -> List[Dict[str, Any]]:
        result = self._with_retry(lambda: self.client.functional_use(dtxsid))
        return self._ensure_list(result)

    def batch_get_exposure_functional_use(self, dtxsids: Sequence[str]) -> List[Any]:
        identifiers = [sid for sid in dtxsids if sid]
        if not identifiers:
            return []
        result = self._with_retry(lambda: self.client.functional_use_batch(identifiers))
        return self._ensure_list(result)

    def get_exposure_functional_use_probability(
        self, dtxsid: str
    ) -> List[Dict[str, Any]]:
        result = self._with_retry(
            lambda: self.client.functional_use_probability(dtxsid)
        )
        return self._ensure_list(result)

    def list_exposure_functional_use_categories(self) -> List[Any]:
        result = self._with_retry(self.client.functional_use_categories)
        return self._ensure_list(result)

    # ------------------------------------------------------------------
    # CCD helpers
    # ------------------------------------------------------------------
    def get_exposure_ccd_puc(self, dtxsid: str) -> List[Dict[str, Any]]:
        result = self._with_retry(lambda: self.client.ccd_puc(dtxsid))
        return self._ensure_list(result)

    def get_exposure_ccd_production_volume(self, dtxsid: str) -> List[Dict[str, Any]]:
        result = self._with_retry(lambda: self.client.ccd_production_volume(dtxsid))
        return self._ensure_list(result)

    def get_exposure_ccd_monitoring_data(self, dtxsid: str) -> List[Dict[str, Any]]:
        result = self._with_retry(lambda: self.client.ccd_monitoring_data(dtxsid))
        return self._ensure_list(result)

    def get_exposure_ccd_keywords(self, dtxsid: str) -> List[Dict[str, Any]]:
        result = self._with_retry(lambda: self.client.ccd_keywords(dtxsid))
        return self._ensure_list(result)

    def get_exposure_ccd_functional_use(self, dtxsid: str) -> List[Dict[str, Any]]:
        result = self._with_retry(lambda: self.client.ccd_functional_use(dtxsid))
        return self._ensure_list(result)

    def get_exposure_ccd_chem_weight_fractions(
        self, dtxsid: str
    ) -> List[Dict[str, Any]]:
        result = self._with_retry(lambda: self.client.ccd_chem_weight_fractions(dtxsid))
        return self._ensure_list(result)

    # ------------------------------------------------------------------
    # MMDB helpers
    # ------------------------------------------------------------------
    def get_exposure_mmdb_single_sample_by_medium(
        self, medium: str
    ) -> List[Dict[str, Any]]:
        result = self._with_retry(
            lambda: self.client.mmdb_single_sample_by_medium(medium)
        )
        return self._ensure_list(result)

    def get_exposure_mmdb_single_sample_by_dtxsid(
        self, dtxsid: str
    ) -> List[Dict[str, Any]]:
        result = self._with_retry(
            lambda: self.client.mmdb_single_sample_by_dtxsid(dtxsid)
        )
        return self._ensure_list(result)

    def list_exposure_mmdb_mediums(self) -> List[Any]:
        result = self._with_retry(self.client.mmdb_mediums)
        return self._ensure_list(result)

    def get_exposure_mmdb_aggregate_by_medium(
        self, medium: str
    ) -> List[Dict[str, Any]]:
        result = self._with_retry(lambda: self.client.mmdb_aggregate_by_medium(medium))
        return self._ensure_list(result)

    def get_exposure_mmdb_aggregate_by_dtxsid(
        self, dtxsid: str
    ) -> List[Dict[str, Any]]:
        result = self._with_retry(lambda: self.client.mmdb_aggregate_by_dtxsid(dtxsid))
        return self._ensure_list(result)


# ----------------------------------------------------------------------
# Utility helpers for tool definitions
# ----------------------------------------------------------------------
def _single_id_tool(name: str, description: str) -> Dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": {
                "dtxsid": {
                    "type": "string",
                    "description": "DSSTox Substance Identifier",
                }
            },
            "required": ["dtxsid"],
        },
    }


def _batch_id_tool(name: str, description: str) -> Dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": {
                "dtxsids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "description": "List of DSSTox Substance Identifiers",
                }
            },
            "required": ["dtxsids"],
        },
    }


def _no_param_tool(name: str, description: str) -> Dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "parameters": {"type": "object", "properties": {}},
    }


def _str_param_tool(name: str, field: str, description: str) -> Dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": {
                field: {
                    "type": "string",
                    "description": field.replace("_", " ").capitalize(),
                }
            },
            "required": [field],
        },
    }
