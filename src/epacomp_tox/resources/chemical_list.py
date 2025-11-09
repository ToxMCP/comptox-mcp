from typing import Any, Dict, List

import ctxpy as ctx

from epacomp_tox.contracts import schema_ref

from .base import BaseResource

class ChemicalListResource(BaseResource):
    """
    MCP resource for EPA CompTox chemical lists.
    
    Provides access to chemical lists and collections.
    """
    
    @property
    def name(self) -> str:
        return "chemical_list"
    
    @property
    def description(self) -> str:
        return "Access to chemical lists and collections"
    
    def __init__(self, api_key: str):
        """
        Initialize the chemical list resource.
        
        Args:
            api_key: EPA CompTox API key.
        """
        super().__init__(api_key)
        self.client = ctx.ChemicalList(x_api_key=api_key)
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Get a list of tools provided by this resource.
        
        Returns:
            List of tool definitions.
        """
        tools: List[Dict[str, Any]] = [
            {
                "name": "get_public_list_names",
                "description": "Get names of available public chemical lists",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "get_full_list",
                "description": "Get all chemicals in a specific list",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "list_name": {
                            "type": "string",
                            "description": "Name of the chemical list"
                        }
                    },
                    "required": ["list_name"]
                }
            }
        ]
        schema_map = {
            "get_public_list_names": ("common", "list_generic.response.schema"),
            "get_full_list": ("common", "list_generic.response.schema"),
        }
        for tool in tools:
            namespace, name = schema_map[tool["name"]]
            tool["responseSchemaRef"] = schema_ref(namespace, name)
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
        if tool_name == "get_public_list_names":
            return self.get_public_list_names()
        elif tool_name == "get_full_list":
            return self.get_full_list(
                list_name=parameters["list_name"]
            )
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
    
    def get_public_list_names(self) -> List[str]:
        """
        Get names of available public chemical lists.
        
        Returns:
            List of chemical list names.
        """
        result = self._with_retry(lambda: self.client.public_list_names())
        return self._ensure_list(result)
    
    def get_full_list(self, list_name: str) -> List[Dict[str, Any]]:
        """
        Get all chemicals in a specific list.
        
        Args:
            list_name: Name of the chemical list.
            
        Returns:
            List of chemicals.
        """
        result = self._with_retry(lambda: self.client.get_full_list(list_name=list_name))
        return self._ensure_list(result)
