import os
from typing import Dict, List, Optional, Union, Any

class MCPServer:
    """
    Model Context Protocol (MCP) server for EPA CompTox data.
    
    This server exposes EPA CompTox data through a standardized MCP interface,
    allowing LLM agents to interact with chemical, exposure, hazard, and other
    toxicology data.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the MCP server.
        
        Args:
            api_key: EPA CompTox API key. If not provided, will attempt to use
                    environment variable EPA_COMPTOX_API_KEY.
        """
        # Resolve API key with multiple env fallbacks for compatibility
        # Preferred: CTX_API_KEY; fallback: EPA_COMPTOX_API_KEY; finally: ctx_x_api_key (ctx-python convention)
        self.api_key = (
            api_key
            or os.environ.get("CTX_API_KEY")
            or os.environ.get("EPA_COMPTOX_API_KEY")
            or os.environ.get("ctx_x_api_key")
        )
        if not self.api_key:
            raise ValueError(
                "CTX API key is required. Set CTX_API_KEY (preferred) or EPA_COMPTOX_API_KEY, "
                "or pass api_key to MCPServer."
            )

        # Configure base URL for ctx-python based on env
        # Preferred: CTX_API_BASE_URL (defaults to new comptox server). Optional legacy toggle via CTX_USE_LEGACY.
        use_legacy = str(os.environ.get("CTX_USE_LEGACY", "0")).strip() in ("1", "true", "True")
        default_base = "https://comptox.epa.gov/ctx-api"
        legacy_base = "https://api-ccte.epa.gov"
        base_url = os.environ.get("CTX_API_BASE_URL", default_base)
        if use_legacy:
            base_url = legacy_base

        # Expose values for ctx-python which reads these envs when instantiated
        os.environ.setdefault("ctx_api_host", base_url)
        # default accept header used by ctx APIs
        os.environ.setdefault("ctx_api_accept", "application/json")
        # key also exposed for ctx-python CLIs if needed
        os.environ.setdefault("ctx_x_api_key", self.api_key)
        
        # Initialize resources
        self.resources = self._initialize_resources()
        
    def _initialize_resources(self) -> Dict[str, Any]:
        """Initialize and return all available resources."""
        from .resources.chemical import ChemicalResource
        from .resources.exposure import ExposureResource
        from .resources.hazard import HazardResource
        from .resources.chemical_list import ChemicalListResource
        from .resources.cheminformatics import CheminformaticsResource
        
        return {
            "chemical": ChemicalResource(self.api_key),
            "exposure": ExposureResource(self.api_key),
            "hazard": HazardResource(self.api_key),
            "chemical_list": ChemicalListResource(self.api_key),
            "cheminformatics": CheminformaticsResource(self.api_key),
        }
    
    def get_resources(self) -> List[Dict[str, str]]:
        """
        Get a list of all available resources.
        
        Returns:
            List of resource information dictionaries.
        """
        return [
            {
                "name": name,
                "description": resource.description,
                "url": f"/resources/{name}"
            }
            for name, resource in self.resources.items()
        ]
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Get a list of all available tools for LLM agents.
        
        Returns:
            List of tool definitions.
        """
        tools = []
        for resource in self.resources.values():
            tools.extend(resource.get_tools())
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
            ValueError: If the tool is not found.
        """
        for resource in self.resources.values():
            if resource.has_tool(tool_name):
                return resource.execute_tool(tool_name, parameters)
        
        raise ValueError(f"Tool '{tool_name}' not found.")
