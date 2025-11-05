from typing import Dict, List, Any, Optional, Callable
from abc import ABC, abstractmethod
import time
import random
from ctxpy import CtxApiError
from epacomp_tox.config import get_retry_config
from epacomp_tox.validators import ensure_list, ensure_object, to_serializable

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
        self._last_metadata: Dict[str, Any] = {}

    def _with_retry(self, fn: Callable[[], Any], *, retries: Optional[int] = None, base_delay: Optional[float] = None) -> Any:
        """
        Call a function with basic exponential backoff and jitter on transient errors.

        Retries on generic Exceptions to avoid tight coupling to underlying HTTP client types.
        """
        if retries is None or base_delay is None:
            r, b = get_retry_config()
            retries = retries if retries is not None else r
            base_delay = base_delay if base_delay is not None else b
        attempt = 0
        while True:
            try:
                result = fn()
                self._capture_last_metadata()
                return result
            except CtxApiError as exc:
                self._last_metadata = {
                    "status": exc.status,
                    "request_id": exc.request_id,
                    "rate_limit": exc.rate_limit,
                    "retry_after": exc.retry_after,
                }
                attempt += 1
                if attempt > retries or not exc.retryable:
                    raise
                sleep_for = base_delay * (2 ** (attempt - 1))
                sleep_for = sleep_for * (0.8 + random.random() * 0.4)
                time.sleep(sleep_for)
            except Exception as e:
                attempt += 1
                if attempt > retries:
                    raise
                # Exponential backoff with jitter
                sleep_for = base_delay * (2 ** (attempt - 1))
                sleep_for = sleep_for * (0.8 + random.random() * 0.4)
                time.sleep(sleep_for)

    def _ensure_list(self, value: Any) -> List[Any]:
        """Normalize value into a list that is JSON-serializable."""
        serialized = to_serializable(value)
        return ensure_list(serialized)

    def _ensure_object(self, value: Any, *, allow_list: bool = False) -> Dict[str, Any]:
        """Normalize value into a mapping; optionally wrap list responses."""
        serialized = to_serializable(value)
        return ensure_object(serialized, allow_list=allow_list)

    def _capture_last_metadata(self) -> None:
        client = getattr(self, "client", None)
        if client is not None and hasattr(client, "last_metadata"):
            self._last_metadata = client.last_metadata

    def get_last_metadata(self) -> Dict[str, Any]:
        """Return metadata captured from the most recent CTX API call."""
        return self._last_metadata
    
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
