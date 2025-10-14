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
                "name": "get_chemical_details",
                "description": "Get detailed information about a chemical",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "Chemical identifier (DTXSID or DTXCID)"
                        },
                        "id_type": {
                            "type": "string",
                            "description": "Type of identifier",
                            "enum": ["dtxsid", "dtxcid"]
                        }
                    },
                    "required": ["id", "id_type"]
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
                            "enum": ["dtxcid", "formula", "mass"]
                        },
                        "query": {
                            "type": "string",
                            "description": "Search term for dtxcid or formula"
                        },
                        "mass_start": {
                            "type": "number",
                            "description": "Start of mass range for mass search"
                        },
                        "mass_end": {
                            "type": "number",
                            "description": "End of mass range for mass search"
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
                search_type=parameters["search_type"]
            )
        elif tool_name == "get_chemical_details":
            return self.get_chemical_details(
                id=parameters["id"],
                id_type=parameters["id_type"]
            )
        elif tool_name == "search_msready":
            search_type = parameters["search_type"]
            if search_type == "mass":
                return self.search_msready_mass(
                    start=parameters.get("mass_start"),
                    end=parameters.get("mass_end")
                )
            else:
                return self.search_msready(
                    search_type=search_type,
                    query=parameters.get("query")
                )
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
    
    def search_chemical(self, query: str, search_type: str) -> List[Dict[str, Any]]:
        """
        Search for chemicals by name, CAS-RN, or other identifiers.
        
        Args:
            query: Search term.
            search_type: Type of search (equals, starts-with, contains).
            
        Returns:
            List of matching chemicals.
        """
        return self._with_retry(lambda: self.client.search(by=search_type, word=query))
    
    def get_chemical_details(self, id: str, id_type: str) -> Dict[str, Any]:
        """
        Get detailed information about a chemical.
        
        Args:
            id: Chemical identifier.
            id_type: Type of identifier (dtxsid or dtxcid).
            
        Returns:
            Chemical details.
        """
        return self._with_retry(lambda: self.client.details(by=id_type, word=id))
    
    def search_msready(self, search_type: str, query: str) -> List[Dict[str, Any]]:
        """
        Search for chemicals by MS-ready properties.
        
        Args:
            search_type: Type of MS-ready search (dtxcid or formula).
            query: Search term.
            
        Returns:
            List of matching chemicals.
        """
        return self._with_retry(lambda: self.client.msready(by=search_type, word=query))
    
    def search_msready_mass(self, start: float, end: float) -> List[Dict[str, Any]]:
        """
        Search for chemicals by mass range.
        
        Args:
            start: Start of mass range.
            end: End of mass range.
            
        Returns:
            List of matching chemicals.
        """
        return self._with_retry(lambda: self.client.msready(by="mass", start=start, end=end))
