import json
import os
import time
from datetime import datetime, timezone
from importlib import metadata
from typing import Any, Dict, List, Optional, Tuple

from ctxpy import CtxApiError, RateLimitInfo
from pydantic import ValidationError

from epacomp_tox import audit
from epacomp_tox.config import configure_ctx_env, get_api_key, get_base_url
from epacomp_tox.settings import settings
from epacomp_tox.health import check_ctx_health
from epacomp_tox.contracts import SchemaValidationError, validate_payload
from epacomp_tox.tools.registry import ToolRegistry
from epacomp_tox.validators import to_serializable

class MCPServer:
    """
    Model Context Protocol (MCP) server for EPA CompTox data.
    
    This server exposes EPA CompTox data through a standardized MCP interface,
    allowing LLM agents to interact with chemical, exposure, hazard, and other
    toxicology data.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        validate_health: bool = False,
        transport_options: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the MCP server.
        
        Args:
            api_key: EPA CompTox API key. If not provided, will attempt to use
                    environment variable EPA_COMPTOX_API_KEY.
            validate_health: When True, perform a connectivity check against the CTX API
                during initialization and raise if the API is unreachable.
        """
        # Resolve API key and configure ctx-python environment
        self.api_key = api_key or get_api_key()
        self.base_url = get_base_url()
        configure_ctx_env(api_key=self.api_key, base_url=self.base_url)

        self._last_health: Optional[Dict[str, Any]] = None
        if validate_health:
            self._last_health = check_ctx_health(
                api_key=self.api_key,
                base_url=self.base_url,
            )

        self.transport_options = self._resolve_transport_options(transport_options)
        self._sessions: Dict[str, Dict[str, Any]] = {}

        # Initialize resources
        self.resources = self._initialize_resources()
        self.tool_registry = ToolRegistry()
        for resource in self.resources.values():
            self.tool_registry.register_resource(resource)
        
    def _initialize_resources(self) -> Dict[str, Any]:
        """Initialize and return all available resources."""
        from .resources.bioactivity import BioactivityResource
        from .resources.chemical import ChemicalResource
        from .resources.exposure import ExposureResource
        from .resources.hazard import HazardResource
        from .resources.metadata import MetadataResource
        from .resources.chemical_list import ChemicalListResource
        from .resources.cheminformatics import CheminformaticsResource
        
        return {
            "chemical": ChemicalResource(self.api_key),
            "bioactivity": BioactivityResource(self.api_key),
            "exposure": ExposureResource(self.api_key),
            "hazard": HazardResource(self.api_key),
            "chemical_list": ChemicalListResource(self.api_key),
            "cheminformatics": CheminformaticsResource(self.api_key),
            "metadata": MetadataResource(self.api_key),
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

    def check_health(self, *, timeout: float = 5.0) -> Dict[str, Any]:
        """Run a connectivity check against the configured CTX API base."""
        self._last_health = check_ctx_health(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=timeout,
        )
        return self._last_health
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Get a list of all available tools for LLM agents.
        
        Returns:
            List of tool definitions.
        """
        return self.tool_registry.list_definitions()
    
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
                result = resource.execute_tool(tool_name, parameters)
                registration = self.tool_registry.get_registration(tool_name)
                if registration.response_schema_ref:
                    namespace, name = registration.response_schema_ref
                    try:
                        validate_payload(result, namespace=namespace, name=name)
                    except SchemaValidationError as exc:
                        raise SchemaValidationError(
                            f"Tool '{tool_name}' response failed schema validation: {exc}"
                        ) from exc
                return result
        
        raise ValueError(f"Tool '{tool_name}' not found.")

    def get_server_info(self) -> Dict[str, str]:
        """Return MCP server metadata for handshake responses."""
        return {
            "name": "epa-comp-tox-mcp",
            "title": "EPA CompTox MCP Server",
            "version": self._resolve_version(),
        }

    def get_transport_options(self) -> Dict[str, Any]:
        """Expose transport configuration (heartbeat, handshake timeouts, etc.)."""
        return dict(self.transport_options)

    def list_tools(self, *, cursor: Optional[str] = None, limit: Optional[int] = None) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Return MCP-compliant tool definitions.

        Cursor is currently ignored because the catalog fits in a single response.
        """
        tools: List[Dict[str, Any]] = []
        for registration in self.tool_registry:
            normalised = self._normalise_tool_definition(
                resource_name=registration.annotations.get("resource", ""),
                tool={
                    "name": registration.name,
                    "title": registration.name,
                    "description": registration.description,
                    "inputSchema": registration.input_schema,
                    "outputSchema": registration.output_schema,
                    "annotations": registration.annotations,
                },
            )
            tools.append(normalised)
        start_index = self._decode_cursor(cursor)
        end_index = start_index + limit if limit and limit > 0 else None
        page = tools[start_index:end_index]
        next_cursor: Optional[str] = None
        if end_index is not None and end_index < len(tools):
            next_cursor = str(end_index)
        return page, next_cursor

    def list_resources(self, *, cursor: Optional[str] = None, limit: Optional[int] = None) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Return MCP-compliant resource descriptors for discovery.
        """
        resources: List[Dict[str, Any]] = []
        for name, resource in self.resources.items():
            resources.append(
                {
                    "uri": f"resource://{name}",
                    "name": name,
                    "title": resource.description,
                    "description": resource.description,
                    "mimeType": "application/json",
                    "annotations": {
                        "audience": ["assistant"],
                        "resource": name,
                    },
                }
            )
        start_index = self._decode_cursor(cursor)
        end_index = start_index + limit if limit and limit > 0 else None
        page = resources[start_index:end_index]
        next_cursor: Optional[str] = None
        if end_index is not None and end_index < len(resources):
            next_cursor = str(end_index)
        return page, next_cursor

    def call_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        *,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a tool and format the response for MCP clients.
        """
        start = time.perf_counter()
        correlation_id = None
        session_id = None
        client_info: Optional[Dict[str, Any]] = None
        if context:
            correlation_id = context.get("correlationId") or context.get("sessionId")
            session_id = context.get("sessionId")
            client_info = context.get("clientInfo")

        try:
            registration = self.tool_registry.get_registration(tool_name)
        except KeyError:
            self._emit_audit_event(
                tool_name=tool_name,
                status="not_found",
                duration_ms=(time.perf_counter() - start) * 1000,
                correlation_id=correlation_id,
                session_id=session_id,
                client_info=client_info,
                params=parameters,
            )
            raise ValueError(f"Unknown tool: {tool_name}")

        resource = registration.resource

        try:
            validated_params = registration.parameters_model.model_validate(parameters or {})
            payload = self._invoke_resource(
                resource,
                tool_name,
                validated_params.model_dump(exclude_none=True),
                context=context,
            )
            structured = to_serializable(payload)
            metadata = self._format_metadata(resource.get_last_metadata())
            session_metadata = self._format_session_context(context)
            combined_metadata: Dict[str, Any] = {}
            if metadata:
                combined_metadata.update(metadata)
            if session_metadata:
                combined_metadata["session"] = session_metadata
            result: Dict[str, Any] = {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(structured, indent=2, default=str),
                        "annotations": {"audience": ["assistant"]},
                    }
                ],
                "structuredContent": {
                    "data": structured,
                    **({"metadata": combined_metadata} if combined_metadata else {}),
                },
                "isError": False,
            }
            self._emit_audit_event(
                tool_name=tool_name,
                status="success",
                duration_ms=(time.perf_counter() - start) * 1000,
                correlation_id=correlation_id,
                session_id=session_id,
                client_info=client_info,
                resource_name=registration.annotations.get("resource"),
                params=validated_params.model_dump(exclude_none=True),
            )
            return result
        except ValidationError as exc:
            self._emit_audit_event(
                tool_name=tool_name,
                status="invalid_params",
                duration_ms=(time.perf_counter() - start) * 1000,
                correlation_id=correlation_id,
                session_id=session_id,
                client_info=client_info,
                resource_name=registration.annotations.get("resource"),
                params=parameters,
                error=str(exc),
            )
            raise ValueError(f"Invalid parameters for tool '{tool_name}': {exc}") from exc
        except CtxApiError as exc:
            metadata = self._format_metadata(resource.get_last_metadata())
            session_metadata = self._format_session_context(context)
            error_payload = {
                "message": str(exc),
                "status": exc.status,
                "detail": exc.detail,
                "requestId": exc.request_id,
                "retryAfter": exc.retry_after,
            }
            if metadata or session_metadata:
                merged: Dict[str, Any] = {}
                if metadata:
                    merged.update(metadata)
                if session_metadata:
                    merged["session"] = session_metadata
                error_payload["metadata"] = merged
            self._emit_audit_event(
                tool_name=tool_name,
                status="error",
                duration_ms=(time.perf_counter() - start) * 1000,
                correlation_id=correlation_id,
                session_id=session_id,
                client_info=client_info,
                resource_name=registration.annotations.get("resource"),
                params=validated_params.model_dump(exclude_none=True),
                error=str(exc),
                error_code=exc.status,
            )
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Tool call failed: {exc}",
                        "annotations": {"audience": ["assistant"]},
                    }
                ],
                "structuredContent": error_payload,
                "isError": True,
            }
        except Exception as exc:
            self._emit_audit_event(
                tool_name=tool_name,
                status="error",
                duration_ms=(time.perf_counter() - start) * 1000,
                correlation_id=correlation_id,
                session_id=session_id,
                client_info=client_info,
                resource_name=registration.annotations.get("resource"),
                params=parameters,
                error=str(exc),
            )
            raise

    def _emit_audit_event(
        self,
        *,
        tool_name: str,
        status: str,
        duration_ms: float,
        correlation_id: Optional[str],
        session_id: Optional[str],
        client_info: Optional[Dict[str, Any]],
        resource_name: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        error_code: Optional[int] = None,
    ) -> None:
        event: Dict[str, Any] = {
            "type": "tool_execution",
            "tool": tool_name,
            "status": status,
            "duration_ms": round(duration_ms, 3),
        }
        if correlation_id:
            event["correlation_id"] = correlation_id
        if session_id:
            event["session_id"] = session_id
        if client_info:
            event["client_info"] = client_info
        if resource_name:
            event["resource"] = resource_name
        if params is not None:
            try:
                event["params"] = json.loads(json.dumps(params, default=str))
            except Exception:
                event["params"] = str(params)
        if error:
            event["error"] = error
        if error_code is not None:
            event["error_code"] = error_code
        audit.emit(event)

    def _invoke_resource(
        self,
        resource: Any,
        tool_name: str,
        parameters: Dict[str, Any],
        *,
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        execute_tool = getattr(resource, "execute_tool")
        try:
            from inspect import signature

            sig = signature(execute_tool)
            if "context" in sig.parameters:
                return execute_tool(tool_name, parameters, context=context)
        except (ImportError, ValueError):  # pragma: no cover - defensive
            pass
        return execute_tool(tool_name, parameters)

    def _find_resource(self, tool_name: str):
        for resource in self.resources.values():
            if resource.has_tool(tool_name):
                return resource
        return None

    @staticmethod
    def _resolve_version() -> str:
        try:
            return metadata.version("epacomp_tox")
        except metadata.PackageNotFoundError:
            return os.environ.get("EPACOMP_TOX_VERSION", "0.0.0-dev")

    @staticmethod
    def _format_metadata(metadata: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not metadata:
            return None
        formatted: Dict[str, Any] = {}
        for key, value in metadata.items():
            if isinstance(value, RateLimitInfo):
                formatted[key] = {
                    "limit": value.limit,
                    "remaining": value.remaining,
                    "reset": value.reset,
                }
            else:
                formatted[key] = value
        return formatted or None

    @staticmethod
    def _normalise_tool_definition(*, resource_name: str, tool: Dict[str, Any]) -> Dict[str, Any]:
        input_schema = tool.get("inputSchema") or tool.get("parameters") or {"type": "object"}
        output_schema = tool.get("outputSchema")
        normalised: Dict[str, Any] = {
            "name": tool["name"],
            "title": tool.get("title") or tool["name"],
            "description": tool.get("description", ""),
            "inputSchema": input_schema,
            "annotations": {
                "resource": resource_name,
            },
        }
        if output_schema:
            normalised["outputSchema"] = output_schema
        return normalised

    @staticmethod
    def _decode_cursor(cursor: Optional[str]) -> int:
        if cursor is None:
            return 0
        try:
            value = int(cursor)
            return max(0, value)
        except (TypeError, ValueError):
            return 0

    def register_session(
        self,
        session_id: str,
        *,
        client_capabilities: Dict[str, Any],
        client_info: Optional[Dict[str, Any]] = None,
        authentication: Optional[Dict[str, Any]] = None,
        negotiated_capabilities: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Track active session metadata for observability and governance."""
        self._sessions[session_id] = {
            "createdAt": datetime.now(tz=timezone.utc).isoformat(),
            "clientCapabilities": client_capabilities,
            "negotiatedCapabilities": negotiated_capabilities or {},
            "clientInfo": client_info or {},
            "authentication": authentication or {},
            "lastActivity": datetime.now(tz=timezone.utc).isoformat(),
            "status": "active",
        }

    def update_session_activity(self, session_id: str) -> None:
        if session_id in self._sessions:
            self._sessions[session_id]["lastActivity"] = datetime.now(tz=timezone.utc).isoformat()

    def unregister_session(self, session_id: str, *, reason: Optional[str] = None) -> None:
        if session_id in self._sessions:
            session = self._sessions[session_id]
            session["closedAt"] = datetime.now(tz=timezone.utc).isoformat()
            if reason:
                session["closeReason"] = reason
            session["status"] = "closed"

    @staticmethod
    def _resolve_transport_options(override: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Resolve heartbeat and handshake settings from configuration and overrides."""
        base_options = settings.transport
        options = {
            "heartbeat_timeout": base_options.heartbeat_timeout,
            "handshake_timeout": base_options.handshake_timeout,
        }
        if override:
            for key, value in override.items():
                if key in options and isinstance(value, (int, float)):
                    options[key] = int(value)
        return options

    @staticmethod
    def _format_session_context(context: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not context:
            return None
        session_view: Dict[str, Any] = {}
        session_id = context.get("sessionId")
        if session_id:
            session_view["sessionId"] = session_id
        client_info = context.get("clientInfo")
        if client_info:
            session_view["clientInfo"] = client_info
        negotiated = context.get("negotiatedCapabilities")
        if negotiated:
            session_view["negotiatedCapabilities"] = negotiated
        client_caps = context.get("clientCapabilities")
        if client_caps:
            session_view["clientCapabilities"] = client_caps
        authentication = context.get("authentication")
        if authentication:
            session_view["authentication"] = authentication
        return session_view or None

    def get_transport_metrics(self) -> Dict[str, Any]:
        """Summarize negotiated capability flags for observability consumers."""
        summary: Dict[str, Any] = {
            "sessions": {"active": 0, "closed": 0},
            "capabilities": {"all": {}, "active": {}},
        }

        def accumulate(
            bucket: Dict[str, Dict[str, int]],
            capabilities: Optional[Dict[str, Any]],
        ) -> None:
            if not capabilities:
                return
            for section, values in capabilities.items():
                if not isinstance(values, dict):
                    continue
                for key, value in values.items():
                    if isinstance(value, bool):
                        metric_key = f"{section}.{key}"
                        counts = bucket.setdefault(metric_key, {"enabled": 0, "disabled": 0})
                        if value:
                            counts["enabled"] += 1
                        else:
                            counts["disabled"] += 1

        for session in self._sessions.values():
            status = session.get("status", "active")
            if status == "active":
                summary["sessions"]["active"] += 1
            else:
                summary["sessions"]["closed"] += 1

            negotiated = session.get("negotiatedCapabilities")
            accumulate(summary["capabilities"]["all"], negotiated)
            if status == "active":
                accumulate(summary["capabilities"]["active"], negotiated)

        return summary
