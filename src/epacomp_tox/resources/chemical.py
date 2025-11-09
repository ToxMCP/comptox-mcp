import base64
from typing import Any, Dict, List, Optional

import ctxpy as ctx

from epacomp_tox.contracts import schema_ref
from epacomp_tox.validators import to_serializable

from .base import BaseResource

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
        self.client = ctx.Chemical(x_api_key=api_key)
    
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

        tools.extend(
            [
                {
                    "name": "get_chemical_property_summary",
                    "description": "Retrieve physicochemical property summary for a chemical",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "dtxsid": {"type": "string", "description": "DSSTox Substance Identifier"},
                            "property_name": {
                                "type": "string",
                                "description": "Optional property name filter",
                            },
                        },
                        "required": ["dtxsid"],
                    },
                },
                {
                    "name": "get_chemical_predicted_properties",
                    "description": "Get predicted properties for a single chemical",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "dtxsid": {"type": "string", "description": "DSSTox Substance Identifier"}
                        },
                        "required": ["dtxsid"],
                    },
                },
                {
                    "name": "batch_get_chemical_predicted_properties",
                    "description": "Batch fetch predicted properties for chemicals",
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
                    "name": "get_chemical_predicted_properties_by_range",
                    "description": "Get predicted properties filtered by property ID and range",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "property_id": {"type": "string", "description": "Predicted property identifier"},
                            "start": {"type": "number", "description": "Range start (inclusive)"},
                            "end": {"type": "number", "description": "Range end (inclusive)"},
                        },
                        "required": ["property_id", "start", "end"],
                    },
                },
                {
                    "name": "get_chemical_experimental_properties",
                    "description": "Get experimental properties for a single chemical",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "dtxsid": {"type": "string", "description": "DSSTox Substance Identifier"}
                        },
                        "required": ["dtxsid"],
                    },
                },
                {
                    "name": "batch_get_chemical_experimental_properties",
                    "description": "Batch fetch experimental properties for chemicals",
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
                    "name": "get_chemical_experimental_properties_by_range",
                    "description": "Get experimental properties filtered by property name and range",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "property_name": {"type": "string", "description": "Experimental property name"},
                            "start": {"type": "number", "description": "Range start (inclusive)"},
                            "end": {"type": "number", "description": "Range end (inclusive)"},
                        },
                        "required": ["property_name", "start", "end"],
                    },
                },
                {
                    "name": "list_chemical_property_names",
                    "description": "List predicted or experimental property names",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "property_type": {
                                "type": "string",
                                "enum": ["predicted", "experimental"],
                                "description": "Property domain to list",
                            }
                        },
                        "required": ["property_type"],
                    },
                },
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
                    "name": "check_chemical_ghs_links",
                    "description": "Check if chemicals have GHS classifications in Wikipedia or PubChem",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "source": {
                                "type": "string",
                                "enum": ["wikipedia", "pubchem"],
                                "description": "Upstream data source",
                            },
                            "dtxsids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "minItems": 1,
                                "description": "List of DSSTox Substance Identifiers",
                            },
                        },
                        "required": ["source", "dtxsids"],
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
                {
                    "name": "get_chemical_structure_file",
                    "description": "Download structure files or images for a chemical identifier",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "identifier_type": {
                                "type": "string",
                                "enum": ["dtxsid", "dtxcid", "gsid", "smiles"],
                                "description": "Identifier category",
                            },
                            "identifier": {
                                "type": "string",
                                "description": "Identifier value or SMILES string",
                            },
                            "file_format": {
                                "type": "string",
                                "enum": ["mol", "mrv", "image"],
                                "description": "Desired file type",
                            },
                            "image_format": {
                                "type": "string",
                                "enum": ["PNG", "SVG"],
                                "description": "Image format (when file_format is image)",
                            },
                        },
                        "required": ["identifier_type", "identifier", "file_format"],
                    },
                },
            ]
        )

        schema_map = {
            "search_chemical": ("common", "list_generic.response.schema"),
            "batch_search_chemical": ("common", "list_generic.response.schema"),
            "get_chemical_details": ("common", "object.response.schema"),
            "batch_get_chemical_details": ("common", "list_generic.response.schema"),
            "search_msready": ("common", "list_generic.response.schema"),
            "get_chemical_property_summary": ("common", "object.response.schema"),
            "get_chemical_predicted_properties": ("common", "list_generic.response.schema"),
            "batch_get_chemical_predicted_properties": ("common", "list_generic.response.schema"),
            "get_chemical_predicted_properties_by_range": ("common", "list_generic.response.schema"),
            "get_chemical_experimental_properties": ("common", "list_generic.response.schema"),
            "batch_get_chemical_experimental_properties": ("common", "list_generic.response.schema"),
            "get_chemical_experimental_properties_by_range": ("common", "list_generic.response.schema"),
            "list_chemical_property_names": ("common", "list_generic.response.schema"),
            "get_chemical_fate_summary": ("common", "object.response.schema"),
            "get_chemical_fate_details": ("common", "object.response.schema"),
            "get_chemical_extra_data": ("common", "list_generic.response.schema"),
            "check_chemical_ghs_links": ("chemical", "ghs_links.response.schema"),
            "opsin_convert_name": ("chemical", "opsin_convert.response.schema"),
            "indigo_convert_molfile": ("chemical", "indigo_convert.response.schema"),
            "get_chemical_structure_file": ("chemical", "structure_file.response.schema"),
        }
        for tool in tools:
            schema_info = schema_map.get(tool["name"])
            if schema_info:
                tool["responseSchemaRef"] = schema_ref(*schema_info)
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
        if tool_name == "get_chemical_property_summary":
            return self.get_chemical_property_summary(
                dtxsid=parameters["dtxsid"],
                property_name=parameters.get("property_name"),
            )
        if tool_name == "get_chemical_predicted_properties":
            return self.get_chemical_predicted_properties(parameters["dtxsid"])
        if tool_name == "batch_get_chemical_predicted_properties":
            return self.batch_get_chemical_predicted_properties(parameters["dtxsids"])
        if tool_name == "get_chemical_predicted_properties_by_range":
            return self.get_chemical_predicted_properties_by_range(
                property_id=parameters["property_id"],
                start=parameters["start"],
                end=parameters["end"],
            )
        if tool_name == "get_chemical_experimental_properties":
            return self.get_chemical_experimental_properties(parameters["dtxsid"])
        if tool_name == "batch_get_chemical_experimental_properties":
            return self.batch_get_chemical_experimental_properties(parameters["dtxsids"])
        if tool_name == "get_chemical_experimental_properties_by_range":
            return self.get_chemical_experimental_properties_by_range(
                property_name=parameters["property_name"],
                start=parameters["start"],
                end=parameters["end"],
            )
        if tool_name == "list_chemical_property_names":
            return self.list_chemical_property_names(parameters["property_type"])
        if tool_name == "get_chemical_fate_summary":
            return self.get_chemical_fate_summary(
                dtxsid=parameters["dtxsid"],
                property_name=parameters.get("property_name"),
            )
        if tool_name == "get_chemical_fate_details":
            return self.get_chemical_fate_details(parameters["dtxsid"])
        if tool_name == "get_chemical_extra_data":
            return self.get_chemical_extra_data(parameters["dtxsids"])
        if tool_name == "check_chemical_ghs_links":
            return self.check_chemical_ghs_links(
                source=parameters["source"],
                dtxsids=parameters["dtxsids"],
            )
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
        if tool_name == "get_chemical_structure_file":
            return self.get_chemical_structure_file(
                identifier_type=parameters["identifier_type"],
                identifier=parameters["identifier"],
                file_format=parameters["file_format"],
                image_format=parameters.get("image_format"),
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
        if normalized == "mass-range":
            result = self._with_retry(
                lambda: self.client.msready(by="mass", start=mass_start, end=mass_end)
            )
        else:
            result = self._with_retry(lambda: self.client.msready(by=search_type, word=query))
        return self._ensure_list(result)

    def get_chemical_property_summary(self, dtxsid: str, property_name: Optional[str]) -> Any:
        result = self._with_retry(
            lambda: self.client.property_summary(dtxsid=dtxsid, prop_name=property_name)
        )
        return to_serializable(result)

    def get_chemical_predicted_properties(self, dtxsid: str) -> List[Dict[str, Any]]:
        result = self._with_retry(lambda: self.client.property_predicted_by_dtxsid(dtxsid))
        return self._ensure_list(result)

    def batch_get_chemical_predicted_properties(self, dtxsids: List[str]) -> List[Dict[str, Any]]:
        identifiers = [sid for sid in dtxsids if sid]
        if not identifiers:
            return []
        result = self._with_retry(lambda: self.client.property_predicted_batch(identifiers))
        return self._ensure_list(result)

    def get_chemical_predicted_properties_by_range(
        self, property_id: str, start: float, end: float
    ) -> List[Dict[str, Any]]:
        result = self._with_retry(
            lambda: self.client.property_predicted_by_range(property_id, start, end)
        )
        return self._ensure_list(result)

    def get_chemical_experimental_properties(self, dtxsid: str) -> List[Dict[str, Any]]:
        result = self._with_retry(lambda: self.client.property_experimental_by_dtxsid(dtxsid))
        return self._ensure_list(result)

    def batch_get_chemical_experimental_properties(self, dtxsids: List[str]) -> List[Dict[str, Any]]:
        identifiers = [sid for sid in dtxsids if sid]
        if not identifiers:
            return []
        result = self._with_retry(lambda: self.client.property_experimental_batch(identifiers))
        return self._ensure_list(result)

    def get_chemical_experimental_properties_by_range(
        self, property_name: str, start: float, end: float
    ) -> List[Dict[str, Any]]:
        result = self._with_retry(
            lambda: self.client.property_experimental_by_range(property_name, start, end)
        )
        return self._ensure_list(result)

    def list_chemical_property_names(self, property_type: str) -> List[str]:
        normalized = property_type.strip().lower()
        if normalized == "predicted":
            result = self._with_retry(self.client.property_predicted_names)
        elif normalized == "experimental":
            result = self._with_retry(self.client.property_experimental_names)
        else:
            raise ValueError("property_type must be 'predicted' or 'experimental'")
        return self._ensure_list(result)

    def get_chemical_fate_summary(self, dtxsid: str, property_name: Optional[str]) -> Any:
        result = self._with_retry(
            lambda: self.client.fate_summary(dtxsid=dtxsid, prop_name=property_name)
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
        image_format: Optional[str],
    ) -> Dict[str, Any]:
        payload = self._with_retry(
            lambda: self.client.structure_file(
                identifier_type=identifier_type,
                identifier=identifier,
                file_format=file_format,
                image_format=image_format,
            )
        )
        metadata = self.get_last_metadata()
        content_type = metadata.get("content_type") if metadata else None

        if isinstance(payload, bytes):
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
