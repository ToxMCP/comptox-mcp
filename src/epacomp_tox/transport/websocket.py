from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from copy import deepcopy
from functools import partial
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Gauge,
    generate_latest,
)

from epacomp_tox import audit
from epacomp_tox.server import MCPServer
from epacomp_tox.settings import settings
from epacomp_tox.transport.common import (
    PRIMARY_PROTOCOL_VERSION,
    SUPPORTED_PROTOCOL_VERSIONS,
)
from epacomp_tox.transport.http import router as http_router
from epacomp_tox.validators import to_serializable

logger = logging.getLogger(__name__)

DEFAULT_SERVER_CAPABILITIES: Dict[str, Any] = {
    "tools": {"listChanged": False, "streams": True, "cancel": True},
    "resources": {"listChanged": False, "subscribe": False},
    "logging": {},
}

CANCELLED_ERROR_CODE = -32800
CAPABILITY_NOT_NEGOTIATED_ERROR_CODE = -32004


class AuditMiddleware:
    """ASGI middleware that adds request IDs, security headers, and audit events."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        correlation_id = str(uuid.uuid4())
        scope.setdefault("state", {})["correlation_id"] = correlation_id
        start = time.perf_counter()
        status_code: Optional[int] = None
        captured_exc: Optional[BaseException] = None

        async def send_wrapper(message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers = [
                    (name, value)
                    for name, value in headers
                    if name.lower() != b"x-request-id"
                ]
                header_names = {name.lower() for name, _ in headers}

                if b"x-content-type-options" not in header_names:
                    headers.append((b"x-content-type-options", b"nosniff"))
                if b"x-frame-options" not in header_names:
                    headers.append((b"x-frame-options", b"DENY"))

                headers.append((b"x-request-id", correlation_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except BaseException as exc:
            captured_exc = exc
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            if status_code is None:
                status_code = (
                    499 if isinstance(captured_exc, asyncio.CancelledError) else 500
                )
            audit.emit(
                {
                    "type": "http_request",
                    "correlation_id": correlation_id,
                    "method": scope.get("method"),
                    "path": scope.get("path"),
                    "status_code": status_code,
                    "duration_ms": round(duration_ms, 3),
                }
            )


def _coerce_value(value: Any) -> Any:
    """Coerce string query values to bool/int/float when possible."""
    if not isinstance(value, str):
        return value

    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"

    try:
        return int(value)
    except ValueError:
        pass

    try:
        return float(value)
    except ValueError:
        pass

    return value


def _coerce_query_params(parsed_query: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten parse_qs output and coerce value types, with helpful defaults."""
    coerced: Dict[str, Any] = {}
    for key, values in parsed_query.items():
        if len(values) == 1:
            coerced[key] = _coerce_value(values[0])
        else:
            coerced[key] = [_coerce_value(v) for v in values]

    # COMPAT: accept "search" as an alias for "query"
    if "query" not in coerced and "search" in coerced:
        coerced["query"] = coerced.get("search")

    # COMPAT: default search_type when a query/search is provided
    if "query" in coerced and "search_type" not in coerced:
        coerced["search_type"] = "contains"

    return coerced


def _extract_legacy_tool(uri: str) -> tuple[Optional[str], Dict[str, Any]]:
    """
    Extract tool name and args from legacy resource URIs.

    Supports:
      - resource://<resource>/tool/<tool_name>?k=v
      - resource://<resource>/<tool_name>?k=v
    """
    from urllib.parse import parse_qs, urlparse

    parsed = urlparse(uri)
    segments = [segment for segment in parsed.path.split("/") if segment]

    tool_name: Optional[str] = None
    if len(segments) >= 2 and segments[0] == "tool":
        tool_name = segments[1]
    elif len(segments) == 1:
        tool_name = segments[0]

    return tool_name, _coerce_query_params(
        parse_qs(parsed.query, keep_blank_values=True)
    )


class ToolExecutionError(Exception):
    """Exception raised when tool execution fails prior to MCP response."""

    def __init__(
        self, *, code: int, message: str, data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data or {}


class MCPWebSocketSession:
    """Manage a single MCP WebSocket session and JSON-RPC message loop."""

    def __init__(self, websocket: WebSocket, server: MCPServer):
        self.websocket = websocket
        self.server = server
        self.initialized = False
        self.protocol_version: Optional[str] = None
        self.session_id = str(uuid.uuid4())
        options = server.get_transport_options()
        self.heartbeat_timeout = options.get("heartbeat_timeout", 120)
        self.handshake_timeout = options.get("handshake_timeout", 30)
        self.last_activity = time.monotonic()
        self.client_capabilities: Dict[str, Any] = {}
        self.negotiated_capabilities: Dict[str, Any] = deepcopy(
            DEFAULT_SERVER_CAPABILITIES
        )
        self.client_info: Dict[str, Any] = {}
        self.authentication: Dict[str, Any] = {}
        self._close_reason = "disconnect"
        self.active_requests: Dict[str, Dict[str, Any]] = {}
        self._streams_enabled = True
        self._cancellation_enabled = True

    async def run(self) -> None:
        """Run the main receive loop handling JSON-RPC messages."""
        await self.websocket.accept()
        try:
            while True:
                try:
                    message = await asyncio.wait_for(
                        self.websocket.receive_text(), timeout=self._receive_timeout()
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        "Heartbeat timeout closing session %s", self.session_id
                    )
                    await self._send_error(
                        None,
                        code=-32002,
                        message="Heartbeat timeout - connection closed by server",
                    )
                    await self.websocket.close(code=4408)
                    self._close_reason = "timeout"
                    break
                self._mark_activity()
                await self._handle_message(message)
        except WebSocketDisconnect:
            logger.debug("WebSocket disconnected (session %s)", self.session_id)
            self._close_reason = "client_disconnect"
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception(
                "Unhandled error in MCP WebSocket session %s", self.session_id
            )
            await self._send_error(None, code=-32603, message="Internal server error")
            await self.websocket.close()
            self._close_reason = f"error:{exc.__class__.__name__}"
        finally:
            self.server.unregister_session(self.session_id, reason=self._close_reason)

    async def _handle_message(self, raw_message: str) -> None:
        try:
            payload = json.loads(raw_message)
        except json.JSONDecodeError:
            await self._send_error(None, code=-32700, message="Parse error")
            return

        if not isinstance(payload, dict):
            await self._send_error(None, code=-32600, message="Invalid request")
            return

        if payload.get("jsonrpc") != "2.0":
            await self._send_error(
                payload.get("id"), code=-32600, message="Invalid JSON-RPC version"
            )
            return

        method = payload.get("method")
        message_id = payload.get("id")
        params = payload.get("params", {})

        if not self.initialized:
            if method != "initialize":
                await self._send_error(
                    message_id,
                    code=-32001,
                    message="Server not yet initialized. Call initialize first.",
                )
                return
            await self._handle_initialize(message_id, params)
            return

        if method == "tools/list":
            await self._handle_tools_list(message_id, params)
        elif method == "resources/list":
            await self._handle_resources_list(message_id, params)
        elif method == "tools/call":
            await self._handle_tools_call(message_id, params)
        elif method == "resources/read":
            await self._handle_resources_read(message_id, params)
        elif method == "tools/cancel":
            await self._handle_tools_cancel(message_id, params)
        elif method == "ping":
            await self._handle_ping(message_id, params)
        elif method == "notifications/cancel":
            await self._handle_tools_cancel(None, params)
        else:
            if message_id is not None:
                await self._send_error(
                    message_id, code=-32601, message=f"Method not found: {method}"
                )

    @staticmethod
    def _merge_capabilities(client_caps: Dict[str, Any]) -> Dict[str, Any]:
        """Intersect server defaults with client-declared capabilities."""
        negotiated = deepcopy(DEFAULT_SERVER_CAPABILITIES)
        for section, client_section in (client_caps or {}).items():
            server_section = negotiated.get(section)
            if not isinstance(server_section, dict) or not isinstance(
                client_section, dict
            ):
                continue
            for key, server_value in list(server_section.items()):
                if isinstance(server_value, bool):
                    requested = client_section.get(key)
                    if requested is False:
                        server_section[key] = False
                    elif requested is True or requested is None:
                        server_section[key] = bool(server_value)
                    else:
                        server_section[key] = bool(server_value)
                elif isinstance(server_value, dict):
                    server_section[key] = deepcopy(server_value)
        return negotiated

    async def _handle_initialize(self, message_id: Any, params: Dict[str, Any]) -> None:
        requested_version = params.get("protocolVersion")
        if requested_version and requested_version not in SUPPORTED_PROTOCOL_VERSIONS:
            await self._send_error(
                message_id,
                code=-32602,
                message="Unsupported protocol version",
                data={
                    "supported": SUPPORTED_PROTOCOL_VERSIONS,
                    "requested": requested_version,
                },
            )
            return

        self.protocol_version = requested_version or PRIMARY_PROTOCOL_VERSION
        self.initialized = True
        self.client_capabilities = params.get("capabilities") or {}
        self.negotiated_capabilities = self._merge_capabilities(
            self.client_capabilities
        )
        self._streams_enabled = bool(
            self.negotiated_capabilities.get("tools", {}).get("streams", False)
        )
        self._cancellation_enabled = bool(
            self.negotiated_capabilities.get("tools", {}).get("cancel", False)
        )
        self.client_info = params.get("clientInfo") or {}
        self.authentication = params.get("authentication") or {}
        transport_settings = self.server.get_transport_options()
        heartbeat_override = params.get("heartbeatIntervalMs")
        if isinstance(heartbeat_override, (int, float)) and heartbeat_override > 0:
            # Convert ms -> seconds while respecting server minimum.
            self.heartbeat_timeout = max(
                transport_settings.get("heartbeat_timeout", self.heartbeat_timeout),
                int(heartbeat_override / 1000),
            )
        self.server.register_session(
            self.session_id,
            client_capabilities=self.client_capabilities,
            client_info=self.client_info,
            authentication=self.authentication,
            negotiated_capabilities=self.negotiated_capabilities,
        )
        server_info = self.server.get_server_info()
        result = {
            "protocolVersion": self.protocol_version,
            "capabilities": deepcopy(self.negotiated_capabilities),
            "serverInfo": server_info,
            "instructions": "Use tools/list to discover available CTX tools, then tools/call to invoke them.",
            "sessionId": self.session_id,
            "transport": {
                "heartbeatMs": self.heartbeat_timeout * 1000,
                "handshakeTimeoutMs": self.handshake_timeout * 1000,
            },
        }
        logger.info(
            "Initialized MCP session %s protocol=%s client=%s",
            self.session_id,
            self.protocol_version,
            self.client_info.get("name") or "unknown",
        )
        await self._send({"jsonrpc": "2.0", "id": message_id, "result": result})
        await self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    async def _handle_tools_list(self, message_id: Any, params: Dict[str, Any]) -> None:
        if message_id is None:
            return
        cursor = params.get("cursor")
        limit = params.get("limit")
        limit_value = int(limit) if isinstance(limit, (int, float)) else None
        if limit_value is not None and limit_value <= 0:
            limit_value = None
        tools, next_cursor = self.server.list_tools(cursor=cursor, limit=limit_value)
        await self._send(
            {
                "jsonrpc": "2.0",
                "id": message_id,
                "result": {"tools": tools, "nextCursor": next_cursor},
            }
        )

    async def _handle_resources_list(
        self, message_id: Any, params: Dict[str, Any]
    ) -> None:
        if message_id is None:
            return
        cursor = params.get("cursor")
        limit = params.get("limit")
        limit_value = int(limit) if isinstance(limit, (int, float)) else None
        if limit_value is not None and limit_value <= 0:
            limit_value = None
        resources, next_cursor = self.server.list_resources(
            cursor=cursor, limit=limit_value
        )
        await self._send(
            {
                "jsonrpc": "2.0",
                "id": message_id,
                "result": {"resources": resources, "nextCursor": next_cursor},
            }
        )

    async def _handle_resources_read(
        self, message_id: Any, params: Dict[str, Any]
    ) -> None:
        if message_id is None:
            return
        if not isinstance(params, dict):
            await self._send_error(
                message_id,
                code=-32602,
                message="resources/read params must be an object",
            )
            return

        uri = params.get("uri")
        if not isinstance(uri, str) or not uri.startswith("resource://"):
            await self._send_error(
                message_id, code=-32602, message="Invalid or missing resource URI"
            )
            return

        # 1) Explicit tool name + arguments tunneled through resources/read
        tool_name_param = params.get("name")
        tool_args_param = params.get("arguments") or params.get("parameters")
        if isinstance(tool_name_param, str):
            arguments = tool_args_param if isinstance(tool_args_param, dict) else {}
            await self._handle_tools_call(
                message_id, {"name": tool_name_param, "arguments": arguments}
            )
            return

        # 2) Legacy URI forms (with or without /tool/ segment)
        legacy_tool_name, legacy_args = _extract_legacy_tool(uri)
        if legacy_tool_name:
            await self._handle_tools_call(
                message_id, {"name": legacy_tool_name, "arguments": legacy_args}
            )
            return

        # 3) Query-string based inference (resource://<resource>?q=...)
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(uri)
        resource_name = parsed.netloc or ""
        if parsed.query:
            inferred_tool = {
                "chemical": "search_chemical",
                "hazard": "search_hazard",
                "exposure": "search_exposure",
                "bioactivity": "search_bioactivity",
                "chemical_list": "search_chemical_list",
                "prioritization": "prioritize_risk_signals",
            }.get(resource_name)

            if inferred_tool:
                arguments = _coerce_query_params(
                    parse_qs(parsed.query, keep_blank_values=True)
                )
                try:
                    await self._handle_tools_call(
                        message_id, {"name": inferred_tool, "arguments": arguments}
                    )
                except Exception as exc:  # pragma: no cover - defensive
                    await self._send_error(
                        message_id, code=-32602, message=f"Tool execution failed: {exc}"
                    )
                return

            available_tools = [
                t["name"]
                for t in self.server.tool_registry.list_definitions()
                if t.get("annotations", {}).get("resource") == resource_name
            ]
            await self._send_error(
                message_id,
                code=-32602,
                message=(
                    f"Cannot infer tool for resource '{resource_name}'. Available tools: {', '.join(available_tools)}. "
                    "Use tools/call with an explicit tool name."
                ),
            )
            return

        # 4) Standard resource description
        resource_name = parsed.netloc or uri.replace("resource://", "").split("?")[0]
        if resource_name not in self.server.resources:
            await self._send_error(
                message_id, code=-32601, message=f"Resource not found: {resource_name}"
            )
            return
        resource = self.server.resources[resource_name]
        await self._send(
            {
                "jsonrpc": "2.0",
                "id": message_id,
                "result": {
                    "contents": [
                        {
                            "uri": uri,
                            "mimeType": "application/json",
                            "text": json.dumps(
                                {
                                    "name": resource_name,
                                    "description": resource.description,
                                    "tools": [
                                        tool
                                        for tool in self.server.tool_registry.list_definitions()
                                        if tool.get("annotations", {}).get("resource")
                                        == resource_name
                                    ],
                                },
                                indent=2,
                            ),
                        }
                    ]
                },
            }
        )

    async def _handle_tools_call(self, message_id: Any, params: Dict[str, Any]) -> None:
        if message_id is None:
            return
        name = params.get("name")
        arguments = params.get("arguments", {})
        if not name:
            await self._send_error(
                message_id, code=-32602, message="Tool name is required"
            )
            return
        if not isinstance(arguments, dict):
            await self._send_error(
                message_id, code=-32602, message="Tool arguments must be an object"
            )
            return
        request_id = params.get("requestId") or str(uuid.uuid4())
        timeout_ms = params.get("timeoutMs")
        timeout_seconds: Optional[float] = None
        if isinstance(timeout_ms, (int, float)) and timeout_ms > 0:
            timeout_seconds = max(0.001, timeout_ms / 1000.0)

        task = asyncio.create_task(
            self._run_tool_request(
                name=name,
                arguments=arguments,
                request_id=request_id,
                timeout=timeout_seconds,
                message_id=message_id,
                context=self._session_context(),
            )
        )
        self.active_requests[request_id] = {"task": task, "message_id": message_id}

    async def _handle_tools_cancel(
        self, message_id: Any, params: Dict[str, Any]
    ) -> None:
        request_id = params.get("requestId")
        if not request_id:
            if message_id is not None:
                await self._send_error(
                    message_id, code=-32602, message="requestId is required"
                )
            return
        if not self._cancellation_enabled:
            if message_id is not None:
                await self._send_error(
                    message_id,
                    code=CAPABILITY_NOT_NEGOTIATED_ERROR_CODE,
                    message="Cancellation not negotiated for this session",
                    data={"requestId": request_id},
                )
            else:
                logger.debug(
                    "Cancellation request ignored for session %s; capability not negotiated",
                    self.session_id,
                )
            return
        entry = self.active_requests.get(request_id)
        if entry is None:
            if message_id is not None:
                await self._send(
                    {
                        "jsonrpc": "2.0",
                        "id": message_id,
                        "result": {"status": "not_found", "requestId": request_id},
                    }
                )
            return
        task = entry.get("task")
        if task is None:
            self.active_requests.pop(request_id, None)
            if message_id is not None:
                await self._send(
                    {
                        "jsonrpc": "2.0",
                        "id": message_id,
                        "result": {"status": "not_found", "requestId": request_id},
                    }
                )
            return
        if task.done():
            self.active_requests.pop(request_id, None)
            if message_id is not None:
                await self._send(
                    {
                        "jsonrpc": "2.0",
                        "id": message_id,
                        "result": {"status": "not_found", "requestId": request_id},
                    }
                )
            return
        task.cancel()
        if message_id is not None:
            await self._send(
                {
                    "jsonrpc": "2.0",
                    "id": message_id,
                    "result": {"status": "cancelled", "requestId": request_id},
                }
            )

    async def _handle_ping(self, message_id: Any, params: Dict[str, Any]) -> None:
        """Respond to ping requests to keep the connection alive."""
        if message_id is None:
            return
        payload = {
            "jsonrpc": "2.0",
            "id": message_id,
            "result": {"timestamp": time.time()},
        }
        await self._send(payload)

    async def _send(self, payload: Dict[str, Any]) -> None:
        await self.websocket.send_text(json.dumps(payload, default=_json_default))

    async def _send_error(
        self,
        message_id: Any,
        *,
        code: int,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        error: Dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        response = {"jsonrpc": "2.0", "error": error}
        if message_id is not None:
            response["id"] = message_id
        await self._send(response)

    def _receive_timeout(self) -> float:
        return (
            self.handshake_timeout if not self.initialized else self.heartbeat_timeout
        )

    def _mark_activity(self) -> None:
        self.last_activity = time.monotonic()
        self.server.update_session_activity(self.session_id)

    async def _run_tool_request(
        self,
        *,
        name: str,
        arguments: Dict[str, Any],
        request_id: str,
        timeout: Optional[float],
        message_id: Any,
        context: Dict[str, Any],
    ) -> None:
        try:
            result = await self._execute_tool(
                name=name,
                arguments=arguments,
                request_id=request_id,
                timeout=timeout,
                context=context,
            )
        except asyncio.CancelledError:
            await self._send_error(
                message_id,
                code=CANCELLED_ERROR_CODE,
                message="Tool call cancelled",
                data={"requestId": request_id},
            )
            return
        except ToolExecutionError as exc:
            await self._send_error(
                message_id,
                code=exc.code,
                message=exc.message,
                data={**exc.data, "requestId": request_id},
            )
            return
        else:
            response_payload = {**result, "requestId": request_id}
            await self._send(
                {"jsonrpc": "2.0", "id": message_id, "result": response_payload}
            )
        finally:
            # Remove request record regardless of completion status
            self.active_requests.pop(request_id, None)

    async def _execute_tool(
        self,
        *,
        name: str,
        arguments: Dict[str, Any],
        request_id: str,
        timeout: Optional[float],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        start_time = time.monotonic()
        await self._emit_event(
            "events/log",
            {
                "sessionId": self.session_id,
                "requestId": request_id,
                "level": "info",
                "message": f"Invoking tool '{name}'",
                "timestamp": time.time(),
            },
        )
        try:
            result = await self._run_tool_call(
                name=name,
                arguments=arguments,
                timeout=timeout,
                context=context,
            )
        except asyncio.CancelledError:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            await self._emit_event(
                "events/error",
                {
                    "sessionId": self.session_id,
                    "requestId": request_id,
                    "message": "Tool call cancelled",
                    "code": CANCELLED_ERROR_CODE,
                },
            )
            await self._emit_event(
                "events/end",
                {
                    "sessionId": self.session_id,
                    "requestId": request_id,
                    "status": "cancelled",
                    "durationMs": duration_ms,
                },
            )
            raise
        except ToolExecutionError as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            payload = {
                "sessionId": self.session_id,
                "requestId": request_id,
                "message": exc.message,
                "code": exc.code,
            }
            if exc.data:
                payload["data"] = exc.data
            await self._emit_event("events/error", payload)
            await self._emit_event(
                "events/end",
                {
                    "sessionId": self.session_id,
                    "requestId": request_id,
                    "status": "error",
                    "durationMs": duration_ms,
                },
            )
            raise
        else:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            await self._emit_event(
                "events/result",
                {
                    "sessionId": self.session_id,
                    "requestId": request_id,
                    "result": {
                        "structuredContent": result.get("structuredContent"),
                        "content": result.get("content"),
                        "isError": result.get("isError", False),
                    },
                },
            )
            await self._emit_event(
                "events/log",
                {
                    "sessionId": self.session_id,
                    "requestId": request_id,
                    "level": "info",
                    "message": f"Tool '{name}' completed",
                    "timestamp": time.time(),
                },
            )
            await self._emit_event(
                "events/end",
                {
                    "sessionId": self.session_id,
                    "requestId": request_id,
                    "status": "ok" if not result.get("isError") else "error",
                    "durationMs": duration_ms,
                },
            )
            return result

    async def _run_tool_call(
        self,
        *,
        name: str,
        arguments: Dict[str, Any],
        timeout: Optional[float],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        loop = asyncio.get_running_loop()
        call = partial(self.server.call_tool, name, arguments, context=context)
        try:
            if timeout is not None:
                return await asyncio.wait_for(
                    loop.run_in_executor(None, call), timeout=timeout
                )
            return await loop.run_in_executor(None, call)
        except asyncio.TimeoutError as exc:
            raise ToolExecutionError(
                code=-32003,
                message="Tool execution timed out",
                data={"reason": "timeout", "timeoutSeconds": timeout},
            ) from exc
        except ValueError as exc:
            raise ToolExecutionError(code=-32602, message=str(exc)) from exc
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Unhandled tool execution error")
            raise ToolExecutionError(
                code=-32603,
                message="Tool execution failed",
                data={"detail": str(exc)},
            ) from exc

    async def _emit_event(self, method: str, params: Dict[str, Any]) -> None:
        if not self._streams_enabled:
            return
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        await self._send(payload)

    def _session_context(self) -> Dict[str, Any]:
        return {
            "sessionId": self.session_id,
            "clientInfo": deepcopy(self.client_info),
            "clientCapabilities": deepcopy(self.client_capabilities),
            "negotiatedCapabilities": deepcopy(self.negotiated_capabilities),
            "authentication": deepcopy(self.authentication),
        }


def _render_prometheus_metrics(server: Optional[MCPServer]) -> bytes:
    summary = (
        server.get_transport_metrics()
        if server is not None
        else {
            "sessions": {"active": 0, "closed": 0},
            "capabilities": {"all": {}, "active": {}},
        }
    )

    registry = CollectorRegistry()
    session_gauge = Gauge(
        "mcp_sessions_total",
        "Count of MCP WebSocket sessions",
        labelnames=("status",),
        registry=registry,
    )
    for status, value in (summary.get("sessions") or {}).items():
        session_gauge.labels(status=status).set(float(value))

    capability_gauge = Gauge(
        "mcp_capability_sessions_total",
        "Sessions grouped by negotiated capability state",
        labelnames=("capability", "state", "scope"),
        registry=registry,
    )
    for scope, capabilities in (summary.get("capabilities") or {}).items():
        for capability, counts in capabilities.items():
            for state, value in counts.items():
                capability_gauge.labels(
                    capability=capability,
                    state=state,
                    scope=scope,
                ).set(float(value))

    return generate_latest(registry)


def _json_default(value: Any) -> Any:
    """Fallback JSON serializer that uses to_serializable for CTX payloads."""
    converted = to_serializable(value)
    if converted is value:
        raise TypeError(
            f"Object of type {type(value).__name__} is not JSON serializable"
        )
    return converted


def create_app(server: Optional[MCPServer] = None) -> FastAPI:
    """Create a FastAPI application exposing the MCP WebSocket transport."""

    app = FastAPI(title="EPA CompTox MCP Server")

    allowed_origins = settings.security.allowed_origins
    if not allowed_origins and settings.app.is_development:
        allowed_origins = ["*"]
    if allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["POST", "GET", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
        )

    if server is not None:
        app.state.mcp_server = server
        app.state.mcp_server_error = None
    else:
        try:
            app.state.mcp_server = MCPServer(validate_health=False)
            app.state.mcp_server_error = None
        except Exception as exc:  # pragma: no cover - exercised in runtime startup
            logger.warning("Failed to initialize MCPServer on startup: %s", exc)
            app.state.mcp_server = None
            app.state.mcp_server_error = exc

    app.add_middleware(AuditMiddleware)

    @app.get("/healthz", tags=["health"])
    async def healthz() -> Dict[str, Any]:
        """Return a lightweight liveness response."""
        return {"status": "ok", "service": app.title}

    @app.get("/readyz", tags=["health"])
    async def readyz() -> Dict[str, Any]:
        """Return readiness status, including CTX connectivity check."""
        server_error = getattr(app.state, "mcp_server_error", None)
        server_instance = getattr(app.state, "mcp_server", None)
        if server_error is not None or server_instance is None:
            raise HTTPException(status_code=503, detail="MCP server not initialized")
        try:
            health = server_instance.check_health(timeout=2.0, probe_mode="readiness")
        except Exception as exc:
            cached = getattr(server_instance, "_last_health", None)
            if cached:
                return {"status": "degraded", "ctx": cached, "detail": str(exc)}
            raise HTTPException(
                status_code=503,
                detail=f"CTX health check failed: {exc}",
            ) from exc
        return {"status": "ok", "ctx": health}

    @app.get("/metrics", tags=["metrics"])
    async def metrics() -> Response:
        server_instance = getattr(app.state, "mcp_server", None)
        payload = _render_prometheus_metrics(server_instance)
        return Response(content=payload, media_type=CONTENT_TYPE_LATEST)

    @app.websocket("/mcp/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        server_error = getattr(app.state, "mcp_server_error", None)
        server_instance = getattr(app.state, "mcp_server", None)
        if server_error is not None or server_instance is None:
            await websocket.accept()
            await websocket.send_text(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32000,
                            "message": "MCP server unavailable",
                            "data": {
                                "detail": (
                                    str(server_error)
                                    if server_error
                                    else "Server not configured"
                                )
                            },
                        },
                    }
                )
            )
            await websocket.close()
            return

        session = MCPWebSocketSession(websocket=websocket, server=server_instance)
        await session.run()

    app.include_router(http_router)

    return app


app = create_app()
