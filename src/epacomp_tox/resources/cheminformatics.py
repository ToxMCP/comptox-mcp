from typing import Dict, List, Any, Optional
import ctxpy as ctx
from .base import BaseResource

class CheminformaticsResource(BaseResource):
    """
    MCP resource for EPA CompTox cheminformatics tools.
    
    Provides access to ToxPrint chemotypes and other cheminformatics tools.
    """
    
    @property
    def name(self) -> str:
        return "cheminformatics"
    
    @property
    def description(self) -> str:
        return "Access to ToxPrint chemotypes and other cheminformatics tools"
    
    def __init__(self, api_key: str):
        """
        Initialize the cheminformatics resource.
        
        Args:
            api_key: EPA CompTox API key.
        """
        super().__init__(api_key)
        # No specific client for cheminformatics, using functions directly
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Get a list of tools provided by this resource.
        
        Returns:
            List of tool definitions.
        """
        return [
            {
                "name": "search_toxprints",
                "description": "Search for ToxPrint chemotypes for a chemical",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "chemical": {
                            "type": "string",
                            "description": "Chemical identifier (DTXSID, DTXCID, or SMILES)"
                        }
                    },
                    "required": ["chemical"]
                }
            },
            {
                "name": "batch_search_toxprints",
                "description": "Search for ToxPrint chemotypes for multiple chemicals",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "chemicals": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": "List of chemical identifiers (DTXSIDs, DTXCIDs, or SMILES)"
                        }
                    },
                    "required": ["chemicals"]
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
        if tool_name == "search_toxprints":
            return self.search_toxprints(
                chemical=parameters["chemical"]
            )
        elif tool_name == "batch_search_toxprints":
            return self.batch_search_toxprints(
                chemicals=parameters["chemicals"]
            )
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
    
    def search_toxprints(self, chemical: str) -> Dict[str, Any]:
        """
        Search for ToxPrint chemotypes for a chemical.
        
        Args:
            chemical: Chemical identifier (DTXSID, DTXCID, or SMILES).
            
        Returns:
            ToxPrint chemotypes.
        """
        from epacomp_tox.validators import to_serializable
        results = self._with_retry(lambda: ctx.search_toxprints(chemical=chemical))
        return to_serializable(results)
    
    def batch_search_toxprints(self, chemicals: List[str]) -> Dict[str, Any]:
        """
        Search for ToxPrint chemotypes for multiple chemicals.
        
        Args:
            chemicals: List of chemical identifiers (DTXSIDs, DTXCIDs, or SMILES).
            
        Returns:
            ToxPrint chemotypes for multiple chemicals.
        """
        from epacomp_tox.validators import to_serializable
        results = self._with_retry(lambda: ctx.search_toxprints(chemical=chemicals))
        return to_serializable(results)
