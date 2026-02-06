import logging
from typing import Any, Dict, List, Optional

import ctxpy as ctx
from epacomp_tox.contracts import schema_ref
from epacomp_tox.validators import to_serializable

from .base import BaseResource

logger = logging.getLogger(__name__)


class BioactivityResource(BaseResource):
    """MCP resource exposing CTX Bioactivity endpoints."""

    @property
    def name(self) -> str:
        return "bioactivity"

    @property
    def description(self) -> str:
        return "Access to ToxCast/Tox21 bioactivity data, assays, models, and AOP crosswalks"

    def __init__(self, api_key: str):
        super().__init__(api_key)

        # Increase upstream timeout for slow queries
        UPSTREAM_TIMEOUT = 120.0
        try:
            self.client = ctx.Bioactivity(x_api_key=api_key, timeout=UPSTREAM_TIMEOUT)
            logger.info(
                f"Successfully initialized ctx.Bioactivity with timeout={UPSTREAM_TIMEOUT}s"
            )
        except TypeError as e:
            logger.warning(
                f"Could not set timeout for ctx.Bioactivity (TypeError: {e}). Using default timeout."
            )
            self.client = ctx.Bioactivity(x_api_key=api_key)

    def get_tools(self) -> List[Dict[str, Any]]:
        tools: List[Dict[str, Any]] = [
            {
                "name": "search_bioactivity_terms",
                "description": "Search bioactivity terms by prefix, exact match, or substring",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "search_type": {
                            "type": "string",
                            "enum": ["equals", "starts-with", "contains"],
                            "description": "Search mode to use",
                        },
                        "value": {
                            "type": "string",
                            "description": "Term to search for",
                        },
                    },
                    "required": ["search_type", "value"],
                },
            },
            {
                "name": "get_bioactivity_summary_by_dtxsid",
                "description": "Fetch bioactivity summary data for a chemical",
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
            },
            {
                "name": "get_bioactivity_summary_by_aeid",
                "description": "Fetch bioactivity summary data for an assay endpoint ID (AEID)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "aeid": {
                            "type": "string",
                            "description": "Assay endpoint identifier",
                        }
                    },
                    "required": ["aeid"],
                },
            },
            {
                "name": "get_bioactivity_summary_by_tissue",
                "description": "Fetch bioactivity summary data for a chemical in a specific tissue",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dtxsid": {
                            "type": "string",
                            "description": "DSSTox Substance Identifier",
                        },
                        "tissue": {
                            "type": "string",
                            "description": "Tissue of origin (e.g., liver)",
                        },
                    },
                    "required": ["dtxsid", "tissue"],
                },
            },
            {
                "name": "get_bioactivity_data",
                "description": "Retrieve detailed bioactivity data for a single identifier",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "identifier_type": {
                            "type": "string",
                            "enum": ["spid", "m4id", "dtxsid", "aeid"],
                            "description": "Identifier category",
                        },
                        "identifier": {
                            "type": "string",
                            "description": "Identifier value",
                        },
                        "projection": {
                            "type": "string",
                            "description": "Optional projection (e.g., toxcast-summary-plot)",
                        },
                    },
                    "required": ["identifier_type", "identifier"],
                },
            },
            {
                "name": "batch_get_bioactivity_data",
                "description": "Batch fetch bioactivity data for multiple identifiers",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "identifier_type": {
                            "type": "string",
                            "enum": ["spid", "m4id", "dtxsid", "aeid"],
                            "description": "Identifier category",
                        },
                        "identifiers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "description": "Identifiers to request (max 200 per batch)",
                        },
                    },
                    "required": ["identifier_type", "identifiers"],
                },
            },
            {
                "name": "get_bioactivity_aed",
                "description": "Retrieve Activity Exposure Distribution (AED) data for a chemical",
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
            },
            {
                "name": "batch_get_bioactivity_aed",
                "description": "Batch retrieve AED data for multiple chemicals",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dtxsids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "description": "DSSTox IDs to request (max 200 per batch)",
                        }
                    },
                    "required": ["dtxsids"],
                },
            },
            {
                "name": "get_bioactivity_assay",
                "description": "Retrieve assay annotations or lists (by AEID, gene, single-concentration, or all)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "mode": {
                            "type": "string",
                            "enum": ["all", "aeid", "gene", "single-concentration"],
                            "description": "Assay query type",
                        },
                        "aeid": {
                            "type": "string",
                            "description": "Assay endpoint ID (required for aeid and single-concentration modes)",
                        },
                        "gene_symbol": {
                            "type": "string",
                            "description": "Gene symbol (required for gene mode)",
                        },
                    },
                    "required": ["mode"],
                },
            },
            {
                "name": "batch_get_bioactivity_assay_annotations",
                "description": "Batch retrieve assay annotations for AEIDs",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "aeids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "description": "List of assay endpoint IDs",
                        }
                    },
                    "required": ["aeids"],
                },
            },
            {
                "name": "get_bioactivity_assay_count",
                "description": "Return the total count of available assays",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "get_bioactivity_assay_chemicals",
                "description": "Get chemicals associated with an assay endpoint",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "aeid": {
                            "type": "string",
                            "description": "Assay endpoint ID",
                        }
                    },
                    "required": ["aeid"],
                },
            },
            {
                "name": "get_bioactivity_aop",
                "description": "Retrieve adverse outcome pathway mappings",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "lookup_type": {
                            "type": "string",
                            "enum": ["toxcast-aeid", "event-number", "entrez-gene-id"],
                            "description": "AOP lookup type",
                        },
                        "identifier": {
                            "type": "string",
                            "description": "Identifier value matching the lookup type",
                        },
                    },
                    "required": ["lookup_type", "identifier"],
                },
            },
            {
                "name": "get_bioactivity_analytical_qc",
                "description": "Retrieve analytical QC data for a chemical",
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
            },
        ]

        list_schema = schema_ref("common", "list_generic.response.schema")
        schema_map = {
            "get_bioactivity_assay": ("common", "object_or_list.response.schema"),
            "get_bioactivity_assay_count": ("common", "object.response.schema"),
        }
        for tool in tools:
            schema_info = schema_map.get(tool["name"])
            if schema_info:
                tool["responseSchemaRef"] = schema_ref(*schema_info)
            else:
                tool["responseSchemaRef"] = list_schema

            # Ensure outputSchema is populated from the reference
            if "responseSchemaRef" in tool:
                from epacomp_tox.contracts import load_schema

                ref = tool["responseSchemaRef"]
                tool["outputSchema"] = load_schema(ref["namespace"], ref["name"])

        return tools

    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        if tool_name == "search_bioactivity_terms":
            return self.search_bioactivity_terms(
                search_type=parameters["search_type"],
                value=parameters["value"],
            )
        if tool_name == "get_bioactivity_summary_by_dtxsid":
            return self.get_bioactivity_summary_by_dtxsid(parameters["dtxsid"])
        if tool_name == "get_bioactivity_summary_by_aeid":
            return self.get_bioactivity_summary_by_aeid(parameters["aeid"])
        if tool_name == "get_bioactivity_summary_by_tissue":
            return self.get_bioactivity_summary_by_tissue(
                dtxsid=parameters["dtxsid"],
                tissue=parameters["tissue"],
            )
        if tool_name == "get_bioactivity_data":
            return self.get_bioactivity_data(
                identifier_type=parameters["identifier_type"],
                identifier=parameters["identifier"],
                projection=parameters.get("projection"),
            )
        if tool_name == "batch_get_bioactivity_data":
            return self.batch_get_bioactivity_data(
                identifier_type=parameters["identifier_type"],
                identifiers=parameters["identifiers"],
            )
        if tool_name == "get_bioactivity_aed":
            return self.get_bioactivity_aed(parameters["dtxsid"])
        if tool_name == "batch_get_bioactivity_aed":
            return self.batch_get_bioactivity_aed(parameters["dtxsids"])
        if tool_name == "get_bioactivity_assay":
            return self.get_bioactivity_assay(
                mode=parameters["mode"],
                aeid=parameters.get("aeid"),
                gene_symbol=parameters.get("gene_symbol"),
            )
        if tool_name == "batch_get_bioactivity_assay_annotations":
            return self.batch_get_bioactivity_assay_annotations(parameters["aeids"])
        if tool_name == "get_bioactivity_assay_count":
            return self.get_bioactivity_assay_count()
        if tool_name == "get_bioactivity_assay_chemicals":
            return self.get_bioactivity_assay_chemicals(parameters["aeid"])
        if tool_name == "get_bioactivity_aop":
            return self.get_bioactivity_aop(
                lookup_type=parameters["lookup_type"],
                identifier=parameters["identifier"],
            )
        if tool_name == "get_bioactivity_analytical_qc":
            return self.get_bioactivity_analytical_qc(parameters["dtxsid"])
        raise ValueError(f"Unknown tool: {tool_name}")

    # Tool implementations -------------------------------------------------

    def search_bioactivity_terms(self, search_type: str, value: str) -> List[Any]:
        result = self._with_retry(lambda: self.client.search(search_type, value))
        return self._ensure_list(result)

    def get_bioactivity_models(
        self, dtxsid: str, model: Optional[str] = None
    ) -> List[Any]:
        kwargs = {"dtxsid": dtxsid}
        if model is not None:
            kwargs["model"] = model
            result = self._with_retry(
                lambda: self.client.models_by_dtxsid_and_name(**kwargs)
            )
        else:
            result = self._with_retry(lambda: self.client.models_by_dtxsid(**kwargs))
        return self._ensure_list(result)

    def get_bioactivity_summary_by_dtxsid(self, dtxsid: str) -> List[Any]:
        result = self._with_retry(lambda: self.client.data_summary_by_dtxsid(dtxsid))
        return self._ensure_list(result)

    def get_bioactivity_summary_by_aeid(self, aeid: str) -> List[Any]:
        result = self._with_retry(lambda: self.client.data_summary_by_aeid(aeid))
        return self._ensure_list(result)

    def get_bioactivity_summary_by_tissue(self, dtxsid: str, tissue: str) -> List[Any]:
        result = self._with_retry(
            lambda: self.client.data_summary_by_tissue(dtxsid, tissue)
        )
        return self._ensure_list(result)

    def get_bioactivity_data(
        self,
        identifier_type: str,
        identifier: str,
        projection: Optional[str] = None,
    ) -> List[Any]:
        norm = identifier_type.strip().lower()
        kwargs = {"identifier": identifier}
        if projection is not None:
            kwargs["projection"] = projection

        if norm == "spid":
            result = self._with_retry(
                lambda: self.client.data_by_spid(kwargs["identifier"])
            )
        elif norm == "m4id":
            result = self._with_retry(
                lambda: self.client.data_by_m4id(kwargs["identifier"])
            )
        elif norm == "dtxsid":
            result = self._with_retry(lambda: self.client.data_by_dtxsid(**kwargs))
        elif norm == "aeid":
            result = self._with_retry(lambda: self.client.data_by_aeid(**kwargs))
        else:
            raise ValueError(
                "identifier_type must be one of spid, m4id, dtxsid, or aeid"
            )
        return self._ensure_list(result)

    def batch_get_bioactivity_data(
        self, identifier_type: str, identifiers: List[str]
    ) -> List[Any]:
        clean = [value for value in identifiers if value]
        if not clean:
            return []
        result = self._with_retry(
            lambda: self.client.data_batch(identifier_type, clean)
        )
        return self._ensure_list(result)

    def get_bioactivity_aed(self, dtxsid: str) -> List[Any]:
        result = self._with_retry(lambda: self.client.aed_by_dtxsid(dtxsid))
        return self._ensure_list(result)

    def batch_get_bioactivity_aed(self, dtxsids: List[str]) -> List[Any]:
        clean = [value for value in dtxsids if value]
        if not clean:
            return []
        result = self._with_retry(lambda: self.client.aed_batch(clean))
        return self._ensure_list(result)

    def get_bioactivity_assay(
        self,
        mode: str,
        aeid: Optional[str] = None,
        gene_symbol: Optional[str] = None,
    ) -> Any:
        normalized = mode.strip().lower()
        kwargs = {}
        if normalized == "all":
            result = self._with_retry(self.client.assays_all)
        elif normalized == "aeid":
            if aeid is None:
                raise ValueError("aeid is required when mode='aeid'")
            kwargs["aeid"] = aeid
            result = self._with_retry(lambda: self.client.assay_by_aeid(**kwargs))
        elif normalized == "single-concentration":
            if aeid is None:
                raise ValueError("aeid is required when mode='single-concentration'")
            kwargs["aeid"] = aeid
            result = self._with_retry(
                lambda: self.client.assay_single_conc_by_aeid(**kwargs)
            )
        elif normalized == "gene":
            if gene_symbol is None:
                raise ValueError("gene_symbol is required when mode='gene'")
            kwargs["gene_symbol"] = gene_symbol
            result = self._with_retry(lambda: self.client.assay_by_gene(**kwargs))
        else:
            raise ValueError(
                "mode must be one of all, aeid, single-concentration, or gene"
            )
        return to_serializable(result)

    def batch_get_bioactivity_assay_annotations(self, aeids: List[str]) -> List[Any]:
        clean = [value for value in aeids if value]
        if not clean:
            return []
        result = self._with_retry(lambda: self.client.assay_batch(clean))
        return self._ensure_list(result)

    def get_bioactivity_assay_count(self) -> Any:
        result = self._with_retry(self.client.assay_count)
        return to_serializable(result)

    def get_bioactivity_assay_chemicals(self, aeid: str) -> List[Any]:
        result = self._with_retry(lambda: self.client.assay_chemicals_by_aeid(aeid))
        return self._ensure_list(result)

    def get_bioactivity_aop(self, lookup_type: str, identifier: str) -> List[Any]:
        norm = lookup_type.strip().lower()
        if norm == "toxcast-aeid":
            result = self._with_retry(
                lambda: self.client.aop_by_toxcast_aeid(identifier)
            )
        elif norm == "event-number":
            result = self._with_retry(
                lambda: self.client.aop_by_event_number(identifier)
            )
        elif norm == "entrez-gene-id":
            result = self._with_retry(
                lambda: self.client.aop_by_entrez_gene(identifier)
            )
        else:
            raise ValueError(
                "lookup_type must be one of toxcast-aeid, event-number, or entrez-gene-id"
            )
        return self._ensure_list(result)

    def get_bioactivity_analytical_qc(self, dtxsid: str) -> List[Any]:
        result = self._with_retry(lambda: self.client.analytical_qc_by_dtxsid(dtxsid))
        return self._ensure_list(result)
