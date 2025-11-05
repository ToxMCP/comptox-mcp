from typing import Any, Dict, List, Optional, Sequence
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
                            "description": "Vocabulary name: fc (functional use), puc (product use categories), or lpk (list presence keywords)",
                            "enum": ["fc", "puc", "lpk"]
                        },
                        "dtxsid": {
                            "type": "string",
                            "description": "Chemical identifier (DTXSID)"
                        },
                        "dtxsids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of DTXSIDs for batch queries"
                        }
                    },
                    "required": ["vocab_name"]
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
                        },
                        "dtxsids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of DTXSIDs for batch queries"
                        }
                    },
                    "required": []
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
                            "description": "Vocabulary name: fc (functional use categories), puc (product use categories), or lpk (list presence keywords)",
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
                        },
                        "dtxsids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of DTXSIDs for batch queries"
                        }
                    },
                    "required": []
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
                            "description": "Exposure dataset to query: pathways (MMDB aggregate), mmdb-single, seem (SEEM general), or seem-demographic",
                            "enum": ["pathways", "mmdb-single", "seem", "seem-demographic"]
                        },
                        "dtxsid": {
                            "type": "string",
                            "description": "Chemical identifier (DTXSID)"
                        },
                        "dtxsids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of DTXSIDs for batch queries"
                        }
                    },
                    "required": ["data_type"]
                }
            }
        ]

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
            raise ValueError("At least one DTXSID must be provided.")
        return identifiers
    
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
            identifiers = self._resolve_identifiers(
                parameters.get("dtxsid"),
                parameters.get("dtxsids"),
            )
            return self.search_cpdat(
                vocab_name=parameters["vocab_name"],
                dtxsids=identifiers,
            )
        if tool_name == "search_httk":
            identifiers = self._resolve_identifiers(
                parameters.get("dtxsid"),
                parameters.get("dtxsids"),
            )
            return self.search_httk(dtxsids=identifiers)
        if tool_name == "get_cpdat_vocabulary":
            return self.get_cpdat_vocabulary(
                vocab_name=parameters["vocab_name"]
            )
        if tool_name == "search_qsurs":
            identifiers = self._resolve_identifiers(
                parameters.get("dtxsid"),
                parameters.get("dtxsids"),
            )
            return self.search_qsurs(dtxsids=identifiers)
        if tool_name == "search_exposures":
            identifiers = self._resolve_identifiers(
                parameters.get("dtxsid"),
                parameters.get("dtxsids"),
            )
            return self.search_exposures(
                data_type=parameters["data_type"],
                dtxsids=identifiers,
            )
        raise ValueError(f"Unknown tool: {tool_name}")
    
    def search_cpdat(self, vocab_name: str, dtxsids: Sequence[str]) -> List[Dict[str, Any]]:
        """
        Search for chemical product and use data from CPDat.
        
        Args:
            vocab_name: Vocabulary name (fc, puc, lpk).
            dtxsids: Chemical identifier(s).
            
        Returns:
            List of matching data.
        """
        if not dtxsids:
            raise ValueError("At least one DTXSID must be provided.")

        results: List[Dict[str, Any]] = []
        for sid in dtxsids:
            payload = self._with_retry(
                lambda sid=sid: self.client.search_cpdat(vocab_name=vocab_name, dtxsid=sid)
            )
            results.extend(self._ensure_list(payload))
        return results
    
    def search_httk(self, dtxsids: Sequence[str]) -> List[Dict[str, Any]]:
        """
        Search for high-throughput toxicokinetics data.
        
        Args:
            dtxsids: Chemical identifier(s).
            
        Returns:
            HTTK data.
        """
        if not dtxsids:
            raise ValueError("At least one DTXSID must be provided.")

        results: List[Dict[str, Any]] = []
        for sid in dtxsids:
            payload = self._with_retry(lambda sid=sid: self.client.search_httk(dtxsid=sid))
            results.extend(self._ensure_list(payload))
        return results
    
    def get_cpdat_vocabulary(self, vocab_name: str) -> List[Dict[str, Any]]:
        """
        Get controlled vocabulary from CPDat.
        
        Args:
            vocab_name: Vocabulary name (fc, puc, lpk).
            
        Returns:
            List of vocabulary terms.
        """
        payload = self._with_retry(lambda: self.client.get_cpdat_vocabulary(vocab_name=vocab_name))
        return self._ensure_list(payload)
    
    def search_qsurs(self, dtxsids: Sequence[str]) -> List[Dict[str, Any]]:
        """
        Search for functional use predictions from QSUR models.
        
        Args:
            dtxsids: Chemical identifier(s).
            
        Returns:
            QSUR predictions.
        """
        if not dtxsids:
            raise ValueError("At least one DTXSID must be provided.")

        results: List[Dict[str, Any]] = []
        for sid in dtxsids:
            payload = self._with_retry(lambda sid=sid: self.client.search_qsurs(dtxsid=sid))
            results.extend(self._ensure_list(payload))
        return results
    
    def search_exposures(self, data_type: str, dtxsids: Sequence[str]) -> List[Dict[str, Any]]:
        """
        Search for exposure pathway predictions or SEEM framework estimates.
        
        Args:
            data_type: Exposure dataset selector (pathways, mmdb-single, seem, or seem-demographic).
            dtxsids: Chemical identifier(s).
            
        Returns:
            Exposure data.
        """
        if not dtxsids:
            raise ValueError("At least one DTXSID must be provided.")

        results: List[Dict[str, Any]] = []
        for sid in dtxsids:
            payload = self._with_retry(lambda sid=sid: self.client.search_exposures(by=data_type, dtxsid=sid))
            results.extend(self._ensure_list(payload))
        return results
