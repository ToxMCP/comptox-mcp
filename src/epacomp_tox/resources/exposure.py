from typing import Dict, List, Any, Optional
import ctxpy as ctx
from .base import BaseResource

class ExposureResource(BaseResource):
    """
    MCP resource for EPA CompTox exposure data.
    
    Provides access to chemical exposure data, CPDat, and QSUR models.
    """
    
    @property
    def name(self) -> str:
        return "exposure"
    
    @property
    def description(self) -> str:
        return "Access to chemical exposure data, CPDat, and QSUR models"
    
    def __init__(self, api_key: str):
        """
        Initialize the exposure resource.
        
        Args:
            api_key: EPA CompTox API key.
        """
        super().__init__(api_key)
        self.client = ctx.Exposure(x_api_key=api_key)
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Get a list of tools provided by this resource.
        
        Returns:
            List of tool definitions.
        """
        return [
            {
                "name": "search_cpdat",
                "description": "Search for chemical product and use data from CPDat",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "vocab_name": {
                            "type": "string",
                            "description": "Vocabulary name: fc (function categories), puc (product use categories), or lpk (list presence keywords)",
                            "enum": ["fc", "puc", "lpk"]
                        },
                        "dtxsid": {
                            "type": "string",
                            "description": "Chemical identifier (DTXSID)"
                        }
                    },
                    "required": ["vocab_name", "dtxsid"]
                }
            },
            {
                "name": "search_httk",
                "description": "Search for high-throughput toxicokinetics data",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dtxsid": {
                            "type": "string",
                            "description": "Chemical identifier (DTXSID)"
                        }
                    },
                    "required": ["dtxsid"]
                }
            },
            {
                "name": "get_cpdat_vocabulary",
                "description": "Get controlled vocabulary from CPDat",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "vocab_name": {
                            "type": "string",
                            "description": "Vocabulary name: fc (function categories), puc (product use categories), or lpk (list presence keywords)",
                            "enum": ["fc", "puc", "lpk"]
                        }
                    },
                    "required": ["vocab_name"]
                }
            },
            {
                "name": "search_qsurs",
                "description": "Search for functional use predictions from QSUR models",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dtxsid": {
                            "type": "string",
                            "description": "Chemical identifier (DTXSID)"
                        }
                    },
                    "required": ["dtxsid"]
                }
            },
            {
                "name": "search_exposures",
                "description": "Search for exposure pathway predictions or SEEM framework estimates",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "data_type": {
                            "type": "string",
                            "description": "Type of exposure data: pathways or seem",
                            "enum": ["pathways", "seem"]
                        },
                        "dtxsid": {
                            "type": "string",
                            "description": "Chemical identifier (DTXSID)"
                        }
                    },
                    "required": ["data_type", "dtxsid"]
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
        if tool_name == "search_cpdat":
            return self.search_cpdat(
                vocab_name=parameters["vocab_name"],
                dtxsid=parameters["dtxsid"]
            )
        elif tool_name == "search_httk":
            return self.search_httk(
                dtxsid=parameters["dtxsid"]
            )
        elif tool_name == "get_cpdat_vocabulary":
            return self.get_cpdat_vocabulary(
                vocab_name=parameters["vocab_name"]
            )
        elif tool_name == "search_qsurs":
            return self.search_qsurs(
                dtxsid=parameters["dtxsid"]
            )
        elif tool_name == "search_exposures":
            return self.search_exposures(
                data_type=parameters["data_type"],
                dtxsid=parameters["dtxsid"]
            )
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
    
    def search_cpdat(self, vocab_name: str, dtxsid: str) -> List[Dict[str, Any]]:
        """
        Search for chemical product and use data from CPDat.
        
        Args:
            vocab_name: Vocabulary name (fc, puc, lpk).
            dtxsid: Chemical identifier.
            
        Returns:
            List of matching data.
        """
        return self._with_retry(lambda: self.client.search_cpdat(vocab_name=vocab_name, dtxsid=dtxsid))
    
    def search_httk(self, dtxsid: str) -> Dict[str, Any]:
        """
        Search for high-throughput toxicokinetics data.
        
        Args:
            dtxsid: Chemical identifier.
            
        Returns:
            HTTK data.
        """
        return self._with_retry(lambda: self.client.search_httk(dtxsid=dtxsid))
    
    def get_cpdat_vocabulary(self, vocab_name: str) -> List[Dict[str, Any]]:
        """
        Get controlled vocabulary from CPDat.
        
        Args:
            vocab_name: Vocabulary name (fc, puc, lpk).
            
        Returns:
            List of vocabulary terms.
        """
        return self._with_retry(lambda: self.client.get_cpdat_vocabulary(vocab_name=vocab_name))
    
    def search_qsurs(self, dtxsid: str) -> Dict[str, Any]:
        """
        Search for functional use predictions from QSUR models.
        
        Args:
            dtxsid: Chemical identifier.
            
        Returns:
            QSUR predictions.
        """
        return self._with_retry(lambda: self.client.search_qsurs(dtxsid=dtxsid))
    
    def search_exposures(self, data_type: str, dtxsid: str) -> Dict[str, Any]:
        """
        Search for exposure pathway predictions or SEEM framework estimates.
        
        Args:
            data_type: Type of exposure data (pathways or seem).
            dtxsid: Chemical identifier.
            
        Returns:
            Exposure data.
        """
        return self._with_retry(lambda: self.client.search_exposures(by=data_type, dtxsid=dtxsid))
