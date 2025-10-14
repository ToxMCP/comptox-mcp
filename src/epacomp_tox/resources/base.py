from typing import Dict, List, Any, Optional, Callable
from abc import ABC, abstractmethod
import time
import random

DEFAULT_RETRIES = int(os.environ.get("CTX_RETRY_ATTEMPTS", 3)) if 'os' in globals() else 3
DEFAULT_BASE_DELAY = float(os.environ.get("CTX_RETRY_BASE", 0.5)) if 'os' in globals() else 0.5

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

    def _with_retry(self, fn: Callable[[], Any], *, retries: int = DEFAULT_RETRIES, base_delay: float = DEFAULT_BASE_DELAY) -> Any:
        """
        Call a function with basic exponential backoff and jitter on transient errors.

        Retries on generic Exceptions to avoid tight coupling to underlying HTTP client types.
        """
        attempt = 0
        while True:
            try:
                return fn()
            except Exception as e:
                attempt += 1
                if attempt > retries:
                    raise
                # Exponential backoff with jitter
                sleep_for = base_delay * (2 ** (attempt - 1))
                sleep_for = sleep_for * (0.8 + random.random() * 0.4)
                time.sleep(sleep_for)
    
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
