from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from epacomp_tox.server import MCPServer
from epacomp_tox.transport.common import PRIMARY_PROTOCOL_VERSION, SUPPORTED_PROTOCOL_VERSIONS

logger = logging.getLogger(__name__)

JSONRPC_VERSION = "2.0"

# JSON-RPC / MCP error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
UNAUTHORIZED = -32000
FORBIDDEN = -32001
TOOL_EXECUTION_ERROR = -32002

# HTTP transport capabilities advertised during initialize
HTTP_SERVER_CAPABILITIES: Dict[str, Any] = {
    "tools": {"enabled": True},
    "resources": {"enabled": True},
    "logging": {"enabled": False},
    "prompts": {"enabled": False},
}

router = APIRouter()


def _jsonrpc_success(result: Any, request_id: Optional[Any]) -> Dict[str, Any]:
    response: Dict[str, Any] = {"jsonrpc": JSONRPC_VERSION, "result": result}
    if request_id is not None:
        response["id"] = request_id
    return response


def _jsonrpc_error(
    *,
    code: int,
    message: str,
    request_id: Optional[Any],
    data: Any = None,
) -> Dict[str, Any]:
    error: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    payload: Dict[str, Any] = {"jsonrpc": JSONRPC_VERSION, "error": error}
    if request_id is not None:
        payload["id"] = request_id
    return payload


def _get_mcp_server(request: Request) -> MCPServer:
    server = getattr(request.app.state, "mcp_server", None)
    server_error = getattr(request.app.state, "mcp_server_error", None)
    if server is None or server_error is not None:
        detail = str(server_error) if server_error else "MCP server not configured"
        logger.error("MCP server unavailable: %s", detail)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="MCP server unavailable"
        )
    return server


def _normalize_tool_parameters(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle parameter shapes used by various MCP clients."""
    if not isinstance(params, dict):
        raise ValueError("Tool parameters must be an object.")

    # Standard shape
    tool_params = params.get("parameters")
    if isinstance(tool_params, dict) and tool_params:
        return tool_params

    # Gemini / Codex style `arguments`
    arguments = params.get("arguments")
    if isinstance(arguments, dict) and arguments:
        return arguments

    # Fall back to remaining keys beyond the required ones
    candidate: Dict[str, Any] = {
        key: value
        for key, value in params.items()
        if key not in {"name", "parameters", "arguments"}
    }
    if candidate:
        return candidate

    # Explicit empty dictionary is acceptable
    return tool_params or {}


def _build_request_context(request: Request) -> Dict[str, Any]:
    session_id = request.headers.get("x-mcp-session-id") or str(uuid4())
    user_agent = request.headers.get("user-agent")
    context: Dict[str, Any] = {
        "sessionId": session_id,
        "clientInfo": {"name": "http-client", **({"userAgent": user_agent} if user_agent else {})},
        "clientCapabilities": {},
        "negotiatedCapabilities": {},
        "transport": {"type": "http"},
    }
    correlation_id = getattr(request.state, "correlation_id", None)
    if correlation_id:
        context["correlationId"] = correlation_id
    return context


@router.post("/mcp")
async def mcp_endpoint(request: Request) -> Response:
    # Obtain server instance or raise 503
    server = _get_mcp_server(request)

    try:
        payload = await request.json()
    except Exception as exc:
        logger.debug("Failed to parse JSON body: %s", exc)
        content = _jsonrpc_error(
            code=PARSE_ERROR, message="Parse error: invalid JSON", request_id=None
        )
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=content)

    if isinstance(payload, list):
        content = _jsonrpc_error(
            code=INVALID_REQUEST,
            message="Batch requests are not supported.",
            request_id=None,
        )
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=content)

    if not isinstance(payload, dict):
        content = _jsonrpc_error(
            code=INVALID_REQUEST,
            message="Request body must be a JSON object.",
            request_id=None,
        )
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=content)

    request_id = payload.get("id")
    method = payload.get("method")
    params = payload.get("params") or {}
    jsonrpc_version = payload.get("jsonrpc")

    if jsonrpc_version != JSONRPC_VERSION:
        content = _jsonrpc_error(
            code=INVALID_REQUEST,
            message="Invalid JSON-RPC version.",
            request_id=request_id,
        )
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=content)

    if not isinstance(method, str):
        content = _jsonrpc_error(
            code=INVALID_REQUEST,
            message="Method must be a string.",
            request_id=request_id,
        )
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=content)

    try:
        result = await _dispatch_method(
            server=server,
            method=method,
            params=params,
            request=request,
            request_id=request_id,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        logger.debug("Invalid request parameters: %s", exc)
        content = _jsonrpc_error(
            code=INVALID_PARAMS, message=str(exc), request_id=request_id
        )
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=content)
    except LookupError as exc:
        logger.debug("Requested tool not found: %s", exc)
        content = _jsonrpc_error(
            code=METHOD_NOT_FOUND, message=str(exc), request_id=request_id
        )
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=content)
    except PermissionError as exc:
        logger.warning("Forbidden tool access: %s", exc)
        content = _jsonrpc_error(
            code=FORBIDDEN, message=str(exc), request_id=request_id
        )
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content=content)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Unhandled MCP error")
        content = _jsonrpc_error(
            code=INTERNAL_ERROR,
            message="Internal server error",
            request_id=request_id,
            data=str(exc),
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=content
        )

    if request_id is None:
        # Notification – no response content
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return JSONResponse(status_code=status.HTTP_200_OK, content=_jsonrpc_success(result, request_id))


async def _dispatch_method(
    *,
    server: MCPServer,
    method: str,
    params: Dict[str, Any],
    request: Request,
    request_id: Optional[Any],
) -> Any:
    method = method.lower()

    if method == "initialize":
        return _handle_initialize(server, params)

    if method in {"initialized", "notifications/initialized"}:
        logger.info("Client reported initialization complete.")
        return {"status": "ok"}

    if method == "shutdown":
        logger.info("Shutdown requested via HTTP transport.")
        return {"status": "ok"}

    if method in {"tools.list", "tools/list", "mcp/tool.list", "mcp/tool/list"}:
        return _handle_tools_list(server, params)

    if method in {"resources.list", "resources/list", "mcp/resource.list", "mcp/resource/list"}:
        return _handle_resources_list(server, params)

    if method in {"tools.call", "tools/call", "mcp/tool.call", "mcp/tool/call"}:
        return await _handle_tools_call(server, params, request)

    if method == "ping":
        return {"status": "ok"}

    raise LookupError(f"Method not found: {method}")


def _handle_initialize(server: MCPServer, params: Dict[str, Any]) -> Dict[str, Any]:
    if params and not isinstance(params, dict):
        raise ValueError("Initialize parameters must be an object.")

    logger.info("HTTP MCP initialize with capabilities: %s", params.get("capabilities", {}))
    return {
        "protocolVersion": params.get("protocolVersion") or PRIMARY_PROTOCOL_VERSION,
        "supportedProtocolVersions": SUPPORTED_PROTOCOL_VERSIONS,
        "serverInfo": server.get_server_info(),
        "capabilities": HTTP_SERVER_CAPABILITIES,
    }


def _handle_tools_list(server: MCPServer, params: Dict[str, Any]) -> Dict[str, Any]:
    if params and not isinstance(params, dict):
        raise ValueError("tools.list parameters must be an object.")

    cursor = params.get("cursor")
    limit = params.get("limit")
    limit_value: Optional[int] = None
    if isinstance(limit, (int, float)):
        limit_value = int(limit)
        if limit_value <= 0:
            limit_value = None

    tools, next_cursor = server.list_tools(cursor=cursor, limit=limit_value)
    return {"tools": tools, "nextCursor": next_cursor}


def _handle_resources_list(server: MCPServer, params: Dict[str, Any]) -> Dict[str, Any]:
    if params and not isinstance(params, dict):
        raise ValueError("resources.list parameters must be an object.")

    cursor = params.get("cursor")
    limit = params.get("limit")
    limit_value: Optional[int] = None
    if isinstance(limit, (int, float)):
        limit_value = int(limit)
        if limit_value <= 0:
            limit_value = None

    resources, next_cursor = server.list_resources(cursor=cursor, limit=limit_value)
    return {"resources": resources, "nextCursor": next_cursor}


async def _handle_tools_call(server: MCPServer, params: Dict[str, Any], request: Request) -> Dict[str, Any]:
    tool_name = params.get("name")
    if not isinstance(tool_name, str) or not tool_name:
        raise ValueError("Tool 'name' must be provided.")

    tool_params = _normalize_tool_parameters(params)
    context = _build_request_context(request)

    try:
        result = server.call_tool(tool_name, tool_params, context=context)
    except ValueError as exc:
        message = str(exc).lower()
        if "not found" in message or "unknown tool" in message:
            raise LookupError(f"Tool not found: {tool_name}") from exc
        raise

    # Ensure content is serializable JSON
    try:
        json.dumps(result)
    except TypeError as exc:
        logger.debug("Tool result not JSON serializable: %s", exc)
        raise ValueError("Tool result could not be serialized.") from exc

    return result
