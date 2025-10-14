from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod

class BaseResource(ABC):
    """
    Base class for all MCP resources.
    
    A resource represents a collection of related data and functionality
    from the EPA CompTox APIs.
    """
    
    def __init__(self, api_key: str):
        """
        Initialize the resource.
        
        Args:
            api_key: EPA CompTox API key.
        """
        self.api_key = api_key
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Get the resource name."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Get the resource description."""
        pass
    
    @abstractmethod
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Get a list of tools provided by this resource.
        
        Returns:
            List of tool definitions.
        """
        pass
    
    def has_tool(self, tool_name: str) -> bool:
        """
        Check if this resource provides the given tool.
        
        Args:
            tool_name: Name of the tool to check.
            
        Returns:
            True if the tool is provided by this resource, False otherwise.
        """
        return any(tool["name"] == tool_name for tool in self.get_tools())
    
    @abstractmethod
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
        pass
