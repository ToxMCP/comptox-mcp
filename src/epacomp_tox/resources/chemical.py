import base64
import logging
from typing import Any, Dict, List, Optional

import ctxpy as ctx

from epacomp_tox.contracts import schema_ref
from epacomp_tox.validators import to_serializable

from .base import BaseResource

logger = logging.getLogger(__name__)

class ChemicalResource(BaseResource):
    """
    MCP resource for EPA CompTox chemical data.
    
    Provides access to chemical structures, nomenclature, IDs, and properties.
    """
    
    @property
    def name(self) -> str:
        return "chemical"
    
    @property
    def description(self) -> str:
        return "Access to chemical structures, nomenclature, IDs, and properties"
    
    def __init__(self, api_key: str):
        """
        Initialize the chemical resource.
        
        Args:
            api_key: EPA CompTox API key.
        """
        super().__init__(api_key)
        
        # --- START MODIFICATION: Increase Upstream Timeout ---
        # The default timeout is too short for complex queries.
        # Increase it significantly (e.g., 120 seconds).
        UPSTREAM_TIMEOUT = 120.0

        try:
            # Attempt to initialize the client with the increased timeout.
            # This assumes the ctxpy library accepts a 'timeout' argument.
            self.client = ctx.Chemical(x_api_key=api_key, timeout=UPSTREAM_TIMEOUT)
            logger.info(f"Successfully initialized ctx.Chemical with timeout={UPSTREAM_TIMEOUT}s")

        except TypeError as e:
            # If ctxpy does not accept the 'timeout' argument, it raises a TypeError.
            # Fall back to the original initialization and log a warning.
            logger.warning(
                f"Could not set timeout for ctx.Chemical (TypeError: {e}). Using default timeout. "
                "Timeouts may still occur for slow queries. Check ctxpy documentation/version."
            )
            self.client = ctx.Chemical(x_api_key=api_key)
        # --- END MODIFICATION ---
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Get a list of tools provided by this resource.
        
        Returns:
            List of tool definitions.
        """
        tools: List[Dict[str, Any]] = [
            {
                "name": "search_chemical",
                "description": "Search for chemicals by name, CAS-RN, or other identifiers",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search term"
                        },
                        "search_type": {
                            "type": "string",
                            "description": "Search type: equals, starts-with, or contains",
                            "enum": ["equals", "starts-with", "contains"]
                        }
                    },
                    "required": ["query", "search_type"]
                }
            },
            {
                "name": "batch_search_chemical",
                "description": "Batch search for chemicals using a list of identifiers",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "identifiers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Identifiers to search (DTXSIDs, CASRNs, names, etc.)"
                        }
                    },
                    "required": ["identifiers"]
                }
            },
            {
                "name": "get_chemical_details",
                "description": "Get detailed information about a chemical",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "identifier": {
                            "type": "string",
                            "description": "Chemical identifier (DTXSID or DTXCID)"
                        },
                        "id_type": {
                            "type": "string",
                            "description": "Type of identifier",
                            "enum": ["dtxsid", "dtxcid"]
                        },
                        "subset": {
                            "type": "string",
                            "description": "Optional subset selector for details",
                            "enum": ["default", "all", "details", "identifiers", "structures", "nta"],
                            "default": "default"
                        }
                    },
                    "required": ["identifier", "id_type"]
                }
            },
            {
                "name": "batch_get_chemical_details",
                "description": "Get detailed information about multiple chemicals",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "identifiers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of chemical identifiers"
                        },
                        "id_type": {
                            "type": "string",
                            "description": "Type of identifier",
                            "enum": ["dtxsid", "dtxcid"]
                        },
                        "subset": {
                            "type": "string",
                            "description": "Optional subset selector for details",
                            "enum": ["default", "all", "details", "identifiers", "structures", "nta"],
                            "default": "default"
                        }
                    },
                    "required": ["identifiers", "id_type"]
                }
            },
            {
                "name": "search_msready",
                "description": "Search for chemicals by MS-ready properties",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "search_type": {
                            "type": "string",
                            "description": "Type of MS-ready search",
                            "enum": ["dtxcid", "formula", "mass-range"]
                        },
                        "query": {
                            "type": "string",
                            "description": "Search term for dtxcid or formula"
                        },
                        "mass_start": {
                            "type": "number",
                            "description": "Start of mass range for mass-range search"
                        },
                        "mass_end": {
                            "type": "number",
                            "description": "End of mass range for mass-range search"
                        }
                    },
                    "required": ["search_type"]
                }
            }
        ]

        # Property endpoints are not available in the current ctxpy client; excluded to avoid runtime 500s.
        tools.extend(
            [
                {
                    "name": "get_chemical_fate_summary",
                    "description": "Retrieve environmental fate summary for a chemical",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "dtxsid": {"type": "string", "description": "DSSTox Substance Identifier"},
                            "property_name": {
                                "type": "string",
                                "description": "Optional fate property filter",
                            },
                        },
                        "required": ["dtxsid"],
                    },
                },
                {
                    "name": "get_chemical_fate_details",
                    "description": "Retrieve detailed environmental fate data for a chemical",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "dtxsid": {"type": "string", "description": "DSSTox Substance Identifier"}
                        },
                        "required": ["dtxsid"],
                    },
                },
                {
                    "name": "get_chemical_extra_data",
                    "description": "Fetch extra chemical data (functional use, use cases, etc.)",
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
                },
                {
                    "name": "opsin_convert_name",
                    "description": "Convert a systematic name using OPSIN",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Systematic IUPAC name"},
                            "output_format": {
                                "type": "string",
                                "enum": ["smiles", "inchikey", "inchi"],
                                "description": "Desired representation",
                            },
                        },
                        "required": ["name", "output_format"],
                    },
                },
                {
                    "name": "indigo_convert_molfile",
                    "description": "Convert a molfile using Indigo toolkit endpoints",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "molfile": {"type": "string", "description": "Molfile contents (V2000/V3000)"},
                            "output_format": {
                                "type": "string",
                                "enum": [
                                    "smiles",
                                    "inchikey",
                                    "inchi",
                                    "mol_v2000",
                                    "mol_v3000",
                                    "mol_weight",
                                    "canonical_smiles",
                                ],
                                "description": "Desired transformation",
                            },
                        },
                        "required": ["molfile", "output_format"],
                    },
                },
            ]
        )

        schema_map = {
            "search_chemical": ("chemical", "search_chemical.response.schema"),
            "batch_search_chemical": ("chemical", "search_chemical.response.schema"),
            "get_chemical_details": ("common", "object.response.schema"),
            "batch_get_chemical_details": ("common", "list_generic.response.schema"),
            "search_msready": ("common", "list_generic.response.schema"),
            "get_chemical_fate_summary": ("common", "object.response.schema"),
            "get_chemical_fate_details": ("common", "object.response.schema"),
            "get_chemical_extra_data": ("common", "list_generic.response.schema"),
            "opsin_convert_name": ("chemical", "opsin_convert.response.schema"),
            "indigo_convert_molfile": ("chemical", "indigo_convert.response.schema"),
        }

        for tool in tools:
            schema_info = schema_map.get(tool["name"])
            if schema_info:
                tool["responseSchemaRef"] = schema_ref(*schema_info)
            
            # Ensure outputSchema is populated from the reference
            if "responseSchemaRef" in tool:
                from epacomp_tox.contracts import load_schema
                ref = tool["responseSchemaRef"]
                tool["outputSchema"] = load_schema(ref["namespace"], ref["name"])
                
        return tools
    
    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        """
        Execute a tool with the given parameters.
        
        Args:
            tool_name: Name of the tool to execute.
            parameters: Parameters for the tool.
            
        Returns:
            Tool execution result.
            
        Raises:
            ValueError: If the tool is not found or parameters are invalid.
        """
        if tool_name == "search_chemical":
            return self.search_chemical(
                query=parameters["query"],
                search_type=parameters["search_type"],
            )
        if tool_name == "batch_search_chemical":
            return self.batch_search_chemical(
                identifiers=parameters["identifiers"],
            )
        if tool_name == "get_chemical_details":
            return self.get_chemical_details(
                identifier=parameters["identifier"],
                id_type=parameters["id_type"],
                subset=parameters.get("subset", "default"),
            )
        if tool_name == "batch_get_chemical_details":
            return self.batch_get_chemical_details(
                identifiers=parameters["identifiers"],
                id_type=parameters["id_type"],
                subset=parameters.get("subset", "default"),
            )
        if tool_name == "search_msready":
            return self.search_msready(
                search_type=parameters["search_type"],
                query=parameters.get("query"),
                mass_start=parameters.get("mass_start"),
                mass_end=parameters.get("mass_end"),
            )
        if tool_name == "get_chemical_fate_summary":
            return self.get_chemical_fate_summary(
                dtxsid=parameters["dtxsid"],
                property_name=parameters.get("property_name"),
            )
        if tool_name == "get_chemical_fate_details":
            return self.get_chemical_fate_details(parameters["dtxsid"])
        if tool_name == "get_chemical_extra_data":
            return self.get_chemical_extra_data(parameters["dtxsids"])
        if tool_name == "opsin_convert_name":
            return self.opsin_convert_name(
                name=parameters["name"],
                output_format=parameters["output_format"],
            )
        if tool_name == "indigo_convert_molfile":
            return self.indigo_convert_molfile(
                molfile=parameters["molfile"],
                output_format=parameters["output_format"],
            )
        raise ValueError(f"Unknown tool: {tool_name}")
    
    def search_chemical(self, query: str, search_type: str) -> List[Dict[str, Any]]:
        """Search for chemicals by name, CAS-RN, or other identifiers."""
        result = self._with_retry(lambda: self.client.search(by=search_type, word=query))
        return self._ensure_list(result)

    def batch_search_chemical(self, identifiers: List[str]) -> List[Dict[str, Any]]:
        """Batch search for multiple chemical identifiers."""
        identifiers = [item for item in identifiers if item]
        if not identifiers:
            return []
        result = self._with_retry(lambda: self.client.search(by="batch", word=identifiers))
        return self._ensure_list(result)

    def get_chemical_details(self, identifier: str, id_type: str, subset: str = "default") -> Dict[str, Any]:
        """Get detailed information about a single chemical."""
        result = self._with_retry(
            lambda: self.client.details(by=id_type, word=identifier, subset=subset)
        )
        return self._ensure_object(result)

    def batch_get_chemical_details(
        self, identifiers: List[str], id_type: str, subset: str = "default"
    ) -> List[Dict[str, Any]]:
        """Get detailed information about multiple chemicals."""
        identifiers = [item for item in identifiers if item]
        if not identifiers:
            return []
        result = self._with_retry(
            lambda: self.client.details(by="batch", word=identifiers, subset=subset)
        )
        return self._ensure_list(result)

    def search_msready(
        self,
        search_type: str,
        query: Optional[str] = None,
        mass_start: Optional[float] = None,
        mass_end: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Search for chemicals by MS-ready properties or mass range."""
        normalized = search_type.strip().lower()
        kwargs = {}
        if normalized == "mass-range":
            if mass_start is not None:
                kwargs["start"] = mass_start
            if mass_end is not None:
                kwargs["end"] = mass_end
            result = self._with_retry(
                lambda: self.client.msready(by="mass", **kwargs)
            )
        else:
            if query is not None:
                kwargs["word"] = query
            result = self._with_retry(lambda: self.client.msready(by=search_type, **kwargs))
        return self._ensure_list(result)

    def _raise_properties_unavailable(self, tool_name: str) -> None:
        """Helper to surface a clear error when property endpoints are unavailable."""
        raise NotImplementedError(
            f"Chemical property tool '{tool_name}' is disabled: ctxpy client does not expose property endpoints."
        )

    def get_chemical_property_summary(self, dtxsid: str, property_name: Optional[str] = None) -> Any:
        self._raise_properties_unavailable("get_chemical_property_summary")

    def get_chemical_predicted_properties(self, dtxsid: str) -> List[Dict[str, Any]]:
        self._raise_properties_unavailable("get_chemical_predicted_properties")

    def batch_get_chemical_predicted_properties(self, dtxsids: List[str]) -> List[Dict[str, Any]]:
        self._raise_properties_unavailable("batch_get_chemical_predicted_properties")

    def get_chemical_predicted_properties_by_range(
        self, property_id: str, start: float, end: float
    ) -> List[Dict[str, Any]]:
        self._raise_properties_unavailable("get_chemical_predicted_properties_by_range")

    def get_chemical_experimental_properties(self, dtxsid: str) -> List[Dict[str, Any]]:
        self._raise_properties_unavailable("get_chemical_experimental_properties")

    def batch_get_chemical_experimental_properties(self, dtxsids: List[str]) -> List[Dict[str, Any]]:
        self._raise_properties_unavailable("batch_get_chemical_experimental_properties")

    def get_chemical_experimental_properties_by_range(
        self, property_name: str, start: float, end: float
    ) -> List[Dict[str, Any]]:
        self._raise_properties_unavailable("get_chemical_experimental_properties_by_range")

    def list_chemical_property_names(self, property_type: str) -> List[str]:
        self._raise_properties_unavailable("list_chemical_property_names")

    def get_chemical_fate_summary(self, dtxsid: str, property_name: Optional[str] = None) -> Any:
        kwargs = {"dtxsid": dtxsid}
        if property_name is not None:
            kwargs["prop_name"] = property_name

        result = self._with_retry(
            lambda: self.client.fate_summary(**kwargs)
        )
        return to_serializable(result)

    def get_chemical_fate_details(self, dtxsid: str) -> Any:
        result = self._with_retry(lambda: self.client.fate_details(dtxsid))
        return to_serializable(result)

    def get_chemical_extra_data(self, dtxsids: List[str]) -> List[Any]:
        identifiers = [sid for sid in dtxsids if sid]
        if not identifiers:
            return []
        result = self._with_retry(lambda: self.client.extra_data_batch(identifiers))
        return self._ensure_list(result)

    def check_chemical_ghs_links(self, source: str, dtxsids: List[str]) -> Dict[str, Any]:
        identifiers = [sid for sid in dtxsids if sid]
        if not identifiers:
            return {"source": source, "results": []}
        result = self._with_retry(lambda: self.client.ghs_check_batch(source, identifiers))
        return {
            "source": source,
            "results": self._ensure_list(result),
        }

    def opsin_convert_name(self, name: str, output_format: str) -> Dict[str, Any]:
        result = self._with_retry(lambda: self.client.opsin_convert(name, output=output_format))
        return {
            "name": name,
            "outputFormat": output_format,
            "value": to_serializable(result),
        }

    def indigo_convert_molfile(self, molfile: str, output_format: str) -> Dict[str, Any]:
        result = self._with_retry(
            lambda: self.client.indigo_convert(molfile, output=output_format)
        )
        converted = to_serializable(result)
        return {
            "outputFormat": output_format,
            "value": converted,
        }

    def get_chemical_structure_file(
        self,
        identifier_type: str,
        identifier: str,
        file_format: str,
        image_format: Optional[str] = None,
    ) -> Dict[str, Any]:
        kwargs = {
            "identifier_type": identifier_type,
            "identifier": identifier,
            "file_format": file_format,
        }
        if image_format is not None:
            kwargs["image_format"] = image_format

        payload = self._with_retry(
            lambda: self.client.structure_file(**kwargs)
        )
        # ... (rest of the method remains the same)
        metadata = self.get_last_metadata()
        content_type = metadata.get("content_type") if metadata else None

        if isinstance(payload, bytes):
            # Ensure base64 is imported if needed
            import base64 
            data = base64.b64encode(payload).decode("ascii")
            encoding = "base64"
        else:
            data = to_serializable(payload)
            encoding = "utf-8"
        
        response: Dict[str, Any] = {
            "identifier": identifier,
            "identifierType": identifier_type,
            "fileFormat": file_format,
            "encoding": encoding,
            "data": data,
            "length": len(payload) if isinstance(payload, (bytes, str)) else None,
        }
        if content_type:
            response["contentType"] = content_type
        if file_format.lower() == "image":
            response["imageFormat"] = (image_format or "PNG").upper()
        return response
