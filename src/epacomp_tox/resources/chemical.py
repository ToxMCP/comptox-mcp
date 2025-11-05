from typing import Dict, List, Any, Optional
import ctxpy as ctx
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
        return [
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
