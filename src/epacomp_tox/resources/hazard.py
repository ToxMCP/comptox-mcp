from typing import Dict, List, Any, Optional
import ctxpy as ctx
from .base import BaseResource

class HazardResource(BaseResource):
    """
    MCP resource for EPA CompTox hazard data.
    
    Provides access to human and ecotoxicology data from ToxValDB.
    """
    
    @property
    def name(self) -> str:
        return "hazard"
    
    @property
    def description(self) -> str:
        return "Access to human and ecotoxicology data from ToxValDB"
    
    def __init__(self, api_key: str):
        """
        Initialize the hazard resource.
        
        Args:
            api_key: EPA CompTox API key.
        """
        super().__init__(api_key)
        self.client = ctx.Hazard(x_api_key=api_key)
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Get a list of tools provided by this resource.
        
        Returns:
            List of tool definitions.
        """
        return [
            {
                "name": "search_hazard",
                "description": "Search for chemical hazard data from ToxValDB",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "data_type": {
                            "type": "string",
                            "description": "Type of hazard data: all, human, eco, skin-eye, cancer, or genetox",
                            "enum": ["all", "human", "eco", "skin-eye", "cancer", "genetox"]
                        },
                        "dtxsid": {
                            "type": "string",
                            "description": "Chemical identifier (DTXSID)"
                        },
                        "summary": {
                            "type": "boolean",
                            "description": "Whether to return summary data only (default: true)",
                            "default": True
                        }
                    },
                    "required": ["data_type", "dtxsid"]
                }
            },
            {
                "name": "batch_search_hazard",
                "description": "Search for hazard data for multiple chemicals",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "data_type": {
                            "type": "string",
                            "description": "Type of hazard data: all, human, eco, skin-eye, cancer, or genetox",
                            "enum": ["all", "human", "eco", "skin-eye", "cancer", "genetox"]
                        },
                        "dtxsids": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": "List of chemical identifiers (DTXSIDs)"
                        },
                        "summary": {
                            "type": "boolean",
                            "description": "Whether to return summary data only (default: true)",
                            "default": True
                        }
                    },
                    "required": ["data_type", "dtxsids"]
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
        if tool_name == "search_hazard":
            return self.search_hazard(
                data_type=parameters["data_type"],
                dtxsid=parameters["dtxsid"],
                summary=parameters.get("summary", True)
            )
        elif tool_name == "batch_search_hazard":
            return self.batch_search_hazard(
                data_type=parameters["data_type"],
                dtxsids=parameters["dtxsids"],
                summary=parameters.get("summary", True)
            )
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
    
    def search_hazard(self, data_type: str, dtxsid: str, summary: bool = True) -> List[Dict[str, Any]]:
        """
        Search for chemical hazard data from ToxValDB.
        
        Args:
            data_type: Type of hazard data (all, human, eco, skin-eye, cancer, genetox).
            dtxsid: Chemical identifier.
            summary: Whether to return summary data only.
            
        Returns:
            List of hazard data.
        """
        return self._with_retry(lambda: self.client.search(by=data_type, dtxsid=dtxsid, summary=summary))
    
    def batch_search_hazard(self, data_type: str, dtxsids: List[str], summary: bool = True) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search for hazard data for multiple chemicals.
        
        Args:
            data_type: Type of hazard data (all, human, eco, skin-eye, cancer, genetox).
            dtxsids: List of chemical identifiers.
            summary: Whether to return summary data only.
            
        Returns:
            Dictionary mapping DTXSIDs to hazard data.
        """
        return self._with_retry(lambda: self.client.batch_search(by=data_type, dtxsid=dtxsids, summary=summary))
