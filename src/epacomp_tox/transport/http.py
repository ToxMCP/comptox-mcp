from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from epacomp_tox.server import MCPServer
from epacomp_tox.transport.common import (
    PRIMARY_PROTOCOL_VERSION,
    SUPPORTED_PROTOCOL_VERSIONS,
)

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
    "prompts": {"enabled": True},
}

router = APIRouter()


@router.get("/mcp")
async def mcp_probe(request: Request) -> Response:
    """
    Lightweight probe endpoint for MCP clients performing HTTP GET discovery.
    Returns server info and supported protocol versions without requiring a JSON-RPC body.
    """
    server = _get_mcp_server(request)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "serverInfo": server.get_server_info(),
            "protocolVersion": PRIMARY_PROTOCOL_VERSION,
            "supportedProtocolVersions": SUPPORTED_PROTOCOL_VERSIONS,
            "capabilities": HTTP_SERVER_CAPABILITIES,
        },
    )


# Issue 3: OAuth discovery placeholder endpoints
@router.get("/.well-known/oauth-authorization-server")
@router.get("/mcp/.well-known/oauth-authorization-server")
@router.get("/.well-known/oauth-authorization-server/mcp")
async def oauth_discovery_placeholder() -> Response:
    """
    Handle OAuth discovery probes from MCP clients.
    Returns 200 OK with empty content to satisfy client discovery attempts.
    """
    return JSONResponse(status_code=status.HTTP_200_OK, content={})


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
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP server unavailable",
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


def _extract_trace_id(request: Request) -> str:
    """Extract trace ID from W3C traceparent header or generate a new one."""
    traceparent = request.headers.get("traceparent")
    if traceparent:
        parts = traceparent.split("-")
        if len(parts) == 4:
            return parts[1]
    return str(uuid4())


def _build_request_context(request: Request) -> Dict[str, Any]:
    session_id = request.headers.get("x-mcp-session-id") or str(uuid4())
    user_agent = request.headers.get("user-agent")
    trace_id = _extract_trace_id(request)
    context: Dict[str, Any] = {
        "sessionId": session_id,
        "traceId": trace_id,
        "clientInfo": {
            "name": "http-client",
            **({"userAgent": user_agent} if user_agent else {}),
        },
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

    # Handle Codex CLI / MCP handshake (streamable HTTP).
    # Some clients send {"type": "connect", ...}; others omit "type" and only
    # include protocolVersion/capabilities. Treat both as a handshake probe and
    # respond with a 'connected' envelope that includes a sessionId.
    # is_connect = payload.get("type") == "connect"
    # looks_like_handshake = (
    #     not payload.get("jsonrpc")
    #     and ("protocolVersion" in payload or "capabilities" in payload)
    # )
    # if is_connect or looks_like_handshake:
    #     logger.info("Received handshake from client: %s", payload.get("clientInfo"))
    #     protocol_version = payload.get("protocolVersion") or PRIMARY_PROTOCOL_VERSION
    #     session_id = request.headers.get("x-mcp-session-id") or str(uuid4())
    #     return JSONResponse(
    #         status_code=status.HTTP_200_OK,
    #         content={
    #             "type": "connected",
    #             "protocolVersion": protocol_version,
    #             "sessionId": session_id,
    #             "serverInfo": server.get_server_info(),
    #             "capabilities": HTTP_SERVER_CAPABILITIES,
    #             "supportedProtocolVersions": SUPPORTED_PROTOCOL_VERSIONS,
    #         },
    #     )

    request_id = payload.get("id")
    method = payload.get("method")
    params = payload.get("params") or {}
    jsonrpc_version = payload.get("jsonrpc")

    # Compatibility: respond to JSON-RPC initialize with a proper JSON-RPC envelope
    # while still carrying the "connected" shape Codex/Gemini expect.
    # if isinstance(method, str) and method.lower() in {"initialize", "mcp/initialize"}:
    #     protocol_version = (params or {}).get("protocolVersion") or PRIMARY_PROTOCOL_VERSION
    #     session_id = request.headers.get("x-mcp-session-id") or str(uuid4())
    #     logger.info("Responding to initialize with JSON-RPC connected envelope for compatibility")
    #     initialize_result = {
    #         "type": "connected",  # <-- THIS CAUSES THE ERROR
    #         "sessionId": session_id,
    #         "protocolVersion": protocol_version,
    #         "supportedProtocolVersions": SUPPORTED_PROTOCOL_VERSIONS,
    #         "serverInfo": server.get_server_info(),
    #         "capabilities": HTTP_SERVER_CAPABILITIES,
    #     }
    #     return JSONResponse(
    #         status_code=status.HTTP_200_OK,
    #         content=_jsonrpc_success(initialize_result, request_id),
    #     )

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

    return JSONResponse(
        status_code=status.HTTP_200_OK, content=_jsonrpc_success(result, request_id)
    )


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
        return {}

    if method == "shutdown":
        logger.info("Shutdown requested via HTTP transport.")
        return {}

    if method in {"tools.list", "tools/list", "mcp/tool.list", "mcp/tool/list"}:
        return _handle_tools_list(server, params)

    if method in {
        "resources.list",
        "resources/list",
        "mcp/resource.list",
        "mcp/resource/list",
    }:
        return _handle_resources_list(server, params)

    if method in {"resources/templates/list", "resources.templates.list"}:
        return _handle_resources_templates_list(server, params)

    if method in {"prompts/list", "prompts.list", "mcp/prompt.list", "mcp/prompt/list"}:
        return _handle_prompts_list(server, params)

    if method in {"resources/read", "resources.read"}:
        return await _handle_resources_read(server, params, request)

    if method in {"tools.call", "tools/call", "mcp/tool.call", "mcp/tool/call"}:
        return await _handle_tools_call(server, params, request)

    if method == "ping":
        return {}

    raise LookupError(f"Method not found: {method}")


def _handle_initialize(server: MCPServer, params: Dict[str, Any]) -> Dict[str, Any]:
    if params and not isinstance(params, dict):
        raise ValueError("Initialize parameters must be an object.")

    logger.info(
        "HTTP MCP initialize with capabilities: %s", params.get("capabilities", {})
    )
    protocol_version = params.get("protocolVersion") or PRIMARY_PROTOCOL_VERSION
    # session_id = params.get("sessionId") or str(uuid4()) # Removed as per instructions

    # Return ONLY standard MCP fields
    return {
        # "type": "connected",      # <-- DELETE THIS
        # "sessionId": session_id,  # <-- DELETE THIS
        "protocolVersion": protocol_version,
        "capabilities": HTTP_SERVER_CAPABILITIES,
        "serverInfo": server.get_server_info(),
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


def _handle_resources_templates_list(
    server: MCPServer, params: Dict[str, Any]
) -> Dict[str, Any]:
    """Handle resources/templates/list - returns empty list as templates are not supported."""
    if params and not isinstance(params, dict):
        raise ValueError("resources/templates/list parameters must be an object.")

    # This server doesn't support resource templates
    return {"resourceTemplates": []}


def _handle_prompts_list(server: MCPServer, params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle prompts/list - returns empty list as prompts are not supported."""
    if params and not isinstance(params, dict):
        raise ValueError("prompts/list parameters must be an object.")

    # This server doesn't support prompts
    return {"prompts": []}


def _coerce_value(value: Any) -> Any:
    """
    Coerce query string values to appropriate Python types.
    Handles: "true"/"false" -> bool, numeric strings -> int/float, else string.
    """
    if not isinstance(value, str):
        return value

    # Handle boolean strings
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"

    # Try integer conversion
    try:
        return int(value)
    except ValueError:
        pass

    # Try float conversion
    try:
        return float(value)
    except ValueError:
        pass

    # Return as string
    return value


def _coerce_query_params(parsed_query: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce parse_qs output into a flat arguments dict with typed values."""
    coerced: Dict[str, Any] = {}
    for key, values in parsed_query.items():
        if len(values) == 1:
            # Assuming _coerce_value is defined elsewhere in http.py
            coerced[key] = _coerce_value(values[0])
        else:
            coerced[key] = [_coerce_value(v) for v in values]

    # COMPAT: accept "search" as an alias for "query"
    if "query" not in coerced and "search" in coerced:
        coerced["query"] = coerced.get("search")

    # Note: Filtering and defaulting are handled in the adapter.
    return coerced


def _extract_legacy_tool(uri: str) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Extract tool name and query args from legacy resource URIs, avoiding identifier confusion.
    """
    parsed = urlparse(uri)
    segments = [segment for segment in parsed.path.split("/") if segment]

    tool_name: Optional[str] = None
    candidate_name: Optional[str] = None

    # 1. Check for explicit /tool/ segment
    if len(segments) >= 2 and segments[0] == "tool":
        candidate_name = segments[1]
    # 2. Check for implicit tool name (Codex pattern)
    elif len(segments) == 1:
        candidate_name = segments[0]

    if candidate_name:
        # Heuristic check: Reject names that look like chemical identifiers
        is_identifier = (
            candidate_name.startswith(("DTXSID", "DTXCID"))
            or
            # Check for CASRN-like patterns (numeric with dashes, at least 5 digits)
            (len(candidate_name) >= 5 and candidate_name.replace("-", "").isdigit())
        )

        if not is_identifier:
            tool_name = candidate_name
        else:
            logger.debug(
                f"Rejecting path segment '{candidate_name}' as a tool name; looks like an identifier."
            )

    # Coerce query parameters
    tool_params = _coerce_query_params(parse_qs(parsed.query, keep_blank_values=True))
    return tool_name, tool_params


def _adapt_legacy_arguments(
    tool_name: str, arguments: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Maps legacy URI parameters to specific tool parameters and cleans up arguments
    using a whitelist approach to satisfy strict schema validation.
    """
    adapted_args = arguments.copy()

    # --- Utility functions ---
    SINGULAR_ID_KEYS = {"identifier", "dtxsid", "dtxcid", "casrn", "query", "search"}
    PLURAL_ID_KEYS = {"identifiers", "dtxsids", "dtxcids", "casrns"}

    def extract_singular_identifier(args: Dict[str, Any]) -> Optional[str]:
        # (Implementation remains the same as previous analysis)
        value = None
        for key in SINGULAR_ID_KEYS:
            if key in args:
                value = args.get(key)
                break
        if value is None:
            for key in PLURAL_ID_KEYS:
                if key in args:
                    v = args.get(key)
                    if (isinstance(v, list) and v) or isinstance(v, str):
                        value = v
                        break
        if value:
            if isinstance(value, list) and value:
                value = value[0]
            return str(value) if value is not None else None
        return None

    def extract_plural_identifiers(args: Dict[str, Any]) -> Optional[List[str]]:
        # (Implementation remains the same as previous analysis)
        value = None
        for key in PLURAL_ID_KEYS:
            if key in args:
                value = args.get(key)
                break
        if value is None:
            for key in SINGULAR_ID_KEYS:
                if key in args:
                    value = args.get(key)
                    break
        if value:
            return value if isinstance(value, list) else [value]
        return None

    def clean_keys_whitelist(args: Dict[str, Any], allowed_keys: set[str]):
        """
        Removes any keys not present in the allowed_keys set (including 'limit', 'tool', etc.).
        """
        keys_to_remove = set(args.keys()) - allowed_keys

        # Also explicitly handle common transport keys often added by clients.
        # 'tool' must be removed as it's used for routing but not part of the schema.
        TRANSPORT_KEYS = {
            "limit",
            "offset",
            "cursor",
            "page",
            "pageSize",
            "tool",
            "name",
        }
        keys_to_remove.update(TRANSPORT_KEYS.intersection(args.keys()))

        for key in keys_to_remove:
            args.pop(key, None)

    # --- Value Normalization ---
    if "dataset" in adapted_args and isinstance(adapted_args.get("dataset"), str):
        dataset_value = adapted_args["dataset"].lower()
        if dataset_value == "toxval":
            adapted_args["dataset"] = "toxvaldb"
        elif dataset_value == "toxref":
            adapted_args["dataset"] = "toxrefdb"

    # --- Specific mappings and Whitelisting ---

    # MAPPING: Chemical Details
    if tool_name == "get_chemical_details":
        id_type = None
        identifier_value = None
        client_id_type = adapted_args.get("identifierType", adapted_args.get("id_type"))

        if "dtxsid" in adapted_args:
            identifier_value = adapted_args.get("dtxsid")
            id_type = "dtxsid"
        elif "dtxcid" in adapted_args:
            identifier_value = adapted_args.get("dtxcid")
            id_type = "dtxcid"
        elif "identifier" in adapted_args and client_id_type in ["dtxsid", "dtxcid"]:
            identifier_value = adapted_args.get("identifier")
            id_type = client_id_type

        allowed_keys = {"identifier", "id_type", "subset"}

        if identifier_value and id_type:
            if isinstance(identifier_value, list) and identifier_value:
                identifier_value = identifier_value[0]
            adapted_args["identifier"] = str(identifier_value)
            adapted_args["id_type"] = id_type

        clean_keys_whitelist(adapted_args, allowed_keys)

    elif tool_name == "batch_get_chemical_details":
        id_type = None
        identifiers_value = None
        dtxsids = adapted_args.get("dtxsids", adapted_args.get("dtxsid"))
        if dtxsids:
            identifiers_value = dtxsids
            id_type = "dtxsid"
        else:
            dtxcids = adapted_args.get("dtxcids", adapted_args.get("dtxcid"))
            if dtxcids:
                identifiers_value = dtxcids
                id_type = "dtxcid"

        allowed_keys = {"identifiers", "id_type", "subset"}

        if identifiers_value and id_type:
            if not isinstance(identifiers_value, list):
                identifiers_value = [identifiers_value]
            adapted_args["identifiers"] = identifiers_value
            adapted_args["id_type"] = id_type

        clean_keys_whitelist(adapted_args, allowed_keys)

    # MAPPING: Chemical Search
    elif tool_name == "search_chemical":
        identifier = extract_singular_identifier(adapted_args)
        allowed_keys = {"query", "search_type"}

        if identifier:
            is_id_search = False
            if (
                arguments.get("dtxsid")
                or arguments.get("casrn")
                or arguments.get("identifier")
            ) and not (arguments.get("query") or arguments.get("search")):
                is_id_search = True

            adapted_args["query"] = identifier
            default_type = "equals" if is_id_search else "contains"
            adapted_args.setdefault("search_type", default_type)

        clean_keys_whitelist(adapted_args, allowed_keys)

    # MAPPING: Hazard Search
    elif tool_name == "search_hazard":
        if "dtxsid" in adapted_args or "casrn" in adapted_args:
            adapted_args.setdefault("dataset", "toxvaldb")

        allowed_keys = {"dtxsid", "casrn", "dataset"}
        clean_keys_whitelist(adapted_args, allowed_keys)

    # MAPPING: Exposure search (legacy alias support + sensible defaults)
    elif tool_name in ["search_exposures", "search_exposure"]:
        identifiers_list = extract_plural_identifiers(adapted_args)
        if identifiers_list:
            adapted_args["dtxsids"] = identifiers_list
            if len(identifiers_list) == 1:
                adapted_args["dtxsid"] = identifiers_list[0]
        else:
            identifier = extract_singular_identifier(adapted_args)
            if identifier:
                adapted_args["dtxsid"] = identifier

        data_type = (
            adapted_args.get("data_type")
            or adapted_args.get("dataset")
            or adapted_args.get("type")
        )
        adapted_args["data_type"] = str(data_type or "pathways")

        allowed_keys = {"data_type", "dtxsid", "dtxsids"}
        clean_keys_whitelist(adapted_args, allowed_keys)

    # MAPPING: Tools expecting 'dtxsid' (Singular) - Comprehensive list
    elif tool_name in [
        # Chemical
        "get_chemical_fate_summary",
        "get_chemical_fate_details",
        # Bioactivity
        "get_bioactivity_models",
        "get_bioactivity_summary_by_dtxsid",
        "get_bioactivity_aed",
        "get_bioactivity_analytical_qc",
        # Exposure
        "get_exposure_functional_use",
        "get_seem_general",
        "get_seem_demographic",
        "get_exposure_product_data",
        "get_exposure_list_presence",
        "get_exposure_httk",
        "get_exposure_functional_use_probability",
        "get_exposure_ccd_puc",
        "get_exposure_ccd_production_volume",
        "get_exposure_ccd_monitoring_data",
        "get_exposure_ccd_keywords",
        "get_exposure_ccd_functional_use",
        "get_exposure_ccd_chem_weight_fractions",
        "get_exposure_mmdb_single_sample_by_dtxsid",
        "get_exposure_mmdb_aggregate_by_dtxsid",
        # Hazard
        "get_hazard_toxval",
        "get_hazard_skin_eye",
        "get_hazard_cancer_summary",
        "get_hazard_genetox_summary",
        "get_hazard_genetox_details",
        "get_hazard_adme_ivive",
        "get_hazard_pprtv",
        "get_hazard_iris",
        "get_hazard_hawc",
    ]:
        identifier = extract_singular_identifier(adapted_args)
        if identifier:
            adapted_args["dtxsid"] = identifier

        # Define specific allowed sets for tools with optional params.
        if tool_name == "get_chemical_fate_summary":
            allowed_keys = {"dtxsid", "property_name"}
        elif tool_name == "get_bioactivity_models":
            allowed_keys = {"dtxsid", "model_name"}
        else:
            allowed_keys = {"dtxsid"}

        clean_keys_whitelist(adapted_args, allowed_keys)

    # MAPPING: Hazard ToxRef (provide defaults for legacy single-identifier calls)
    elif tool_name == "get_hazard_toxref":
        identifier = extract_singular_identifier(adapted_args)
        if identifier:
            adapted_args.setdefault("lookup_type", "dtxsid")
            adapted_args.setdefault("value", identifier)

        adapted_args.setdefault("dataset", "summary")
        allowed_keys = {"dataset", "lookup_type", "value"}
        clean_keys_whitelist(adapted_args, allowed_keys)

    # MAPPING: Tools expecting 'dtxsids' (Plural Array) - Comprehensive list
    elif tool_name in [
        # Chemical
        "get_chemical_extra_data",
        "check_chemical_ghs_links",
        # Hazard
        "batch_search_hazard",
        "batch_get_hazard_toxval",
        "batch_get_hazard_skin_eye",
        "batch_get_hazard_cancer_summary",
        "batch_get_hazard_genetox_summary",
        "batch_get_hazard_genetox_details",
        "batch_get_hazard_toxref",
        # Exposure
        "batch_get_seem_general",
        "batch_get_seem_demographic",
        "batch_get_exposure_product_data",
        "batch_get_exposure_list_presence",
        "batch_get_exposure_httk",
        "batch_get_exposure_functional_use",
        # Bioactivity
        "batch_get_bioactivity_aed",
    ]:
        identifiers_list = extract_plural_identifiers(adapted_args)
        if identifiers_list:
            adapted_args["dtxsids"] = identifiers_list

        if tool_name == "check_chemical_ghs_links":
            allowed_keys = {"dtxsids", "source"}
        elif tool_name == "batch_search_hazard":
            allowed_keys = {"dtxsids", "dataset"}
        else:
            allowed_keys = {"dtxsids"}

        clean_keys_whitelist(adapted_args, allowed_keys)

    # Default cleanup for any tools not explicitly handled
    else:
        # For unhandled tools, we still attempt to clean up client-injected transport parameters
        TRANSPORT_KEYS = {
            "limit",
            "offset",
            "cursor",
            "page",
            "pageSize",
            "tool",
            "name",
        }
        # This is a fallback blacklist approach for unmapped tools
        clean_keys_whitelist(adapted_args, set(adapted_args.keys()) - TRANSPORT_KEYS)

    return adapted_args


def _summarize_tool_definitions(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Creates a concise summary of tool definitions, removing bulky schemas for discovery."""
    summarized_tools = []
    for tool in tools:
        summary = {
            "name": tool.get("name"),
            "title": tool.get(
                "title", tool.get("name")
            ),  # Fallback to name if title is missing
            "description": tool.get("description"),
        }
        # Filter out keys where value is None
        summary = {k: v for k, v in summary.items() if v is not None}
        summarized_tools.append(summary)
    return summarized_tools


def _sanitize_tool_result_for_resource_read(tool_result: Dict[str, Any]) -> str:
    """
    Sanitizes and truncates a tool result for embedding in resources/read 'text' field.
    Used by compatibility shims to prevent massive JSON blobs via legacy transport.
    """
    structured_data = tool_result.get("structuredContent", tool_result)

    # Define strict limits for this legacy transport layer
    MAX_ITEMS = 50
    MAX_LENGTH = 10000  # 10KB limit

    truncated_data = structured_data
    is_truncated_items = False

    # 1. Truncate items
    if isinstance(structured_data, list):
        if len(structured_data) > MAX_ITEMS:
            truncated_data = structured_data[:MAX_ITEMS]
            is_truncated_items = True

    try:
        # 2. Serialize the (potentially truncated) data
        # Use compact serialization (no indent) to save space
        serialized_data = json.dumps(truncated_data, default=str)
    except TypeError:
        return json.dumps(
            {"error": "Tool result could not be serialized via legacy transport."}
        )

    # 3. Enforce maximum length constraint
    if len(serialized_data) > MAX_LENGTH:
        # If still too long, we must summarize instead of returning partial data.
        summary = {
            "status": "error",
            "message": "Tool execution successful, but results exceed transport limits.",
            "detail": f"Data size ({len(serialized_data)} chars) > MAX_LENGTH ({MAX_LENGTH} chars). Please use tools/call directly for full results.",
        }
        if isinstance(structured_data, list):
            summary["total_records"] = len(structured_data)

        return json.dumps(summary, default=str)

    # 4. Handle item truncation warning
    if is_truncated_items:
        # If items were truncated but length is okay, wrap the data with a warning.
        summary = {
            "status": "partial_success",
            "message": f"Showing first {MAX_ITEMS} of {len(structured_data)} results.",
            "detail": f"Total results exceeds MAX_ITEMS ({MAX_ITEMS}). Please use tools/call directly for full results.",
            "data": truncated_data,
        }
        return json.dumps(summary, default=str)

    return serialized_data


async def _handle_resources_read(
    server: MCPServer, params: Dict[str, Any], request: Request
) -> Dict[str, Any]:
    """
    Handle resources/read, including comprehensive compatibility shims for legacy URIs.
    """
    if not isinstance(params, dict):
        raise ValueError("resources/read parameters must be an object.")

    uri = params.get("uri")
    if not isinstance(uri, str) or not uri:
        raise ValueError("Resource 'uri' must be provided.")

    if not uri.startswith("resource://"):
        raise ValueError(f"Invalid resource URI format: {uri}")

    parsed = urlparse(uri)
    resource_name = parsed.netloc or ""

    # COMPAT: explicit tool execution tunneled via params (e.g., {"uri": ..., "name": ...})
    tool_name_param = params.get("name")
    tool_args_param = params.get("arguments") or params.get("parameters")
    if isinstance(tool_name_param, str) and tool_name_param:
        logger.info(
            "resources/read received explicit tool name in params; redirecting: %s",
            tool_name_param,
        )
        arguments = tool_args_param if isinstance(tool_args_param, dict) else {}

        # Adaptation and execution
        adapted_arguments = _adapt_legacy_arguments(tool_name_param, arguments)
        try:
            tool_result = await _handle_tools_call(
                server,
                {"name": tool_name_param, "arguments": adapted_arguments},
                request,
            )
        except Exception as exc:
            raise ValueError(f"Tool execution failed: {exc}") from exc

        sanitized_text = _sanitize_tool_result_for_resource_read(tool_result)
        return {
            "contents": [
                {"uri": uri, "mimeType": "application/json", "text": sanitized_text}
            ]
        }

    # COMPAT: URI-based tool execution and inferred search (Unified flow)

    # 1. Extract potential tool name from path segments and get query arguments.
    path_tool_name, query_args = _extract_legacy_tool(uri)

    # 2. Determine the tool name and arguments to use.

    # Prioritize the 'tool' query parameter (e.g., resource://bioactivity?tool=...)
    explicit_query_tool = query_args.get("tool")
    if isinstance(explicit_query_tool, str) and explicit_query_tool:
        tool_to_use = explicit_query_tool
        args_to_use = query_args  # Adapter will clean 'tool' via whitelist
        logger.info(f"Using explicit tool from query parameter: {tool_to_use}")

    # Otherwise, use the tool name extracted from the path (e.g., resource://chemical/search_chemical?...)
    elif path_tool_name:
        tool_to_use = path_tool_name
        args_to_use = query_args
        logger.info(f"Using tool from URI path: {tool_to_use}")

    # Otherwise, attempt inference based on resource name and available arguments.
    else:
        inferred_args = query_args.copy()
        segments = [segment for segment in parsed.path.split("/") if segment]

        # Handle identifier in the path (e.g., resource://hazard/DTXSID...)
        # _extract_legacy_tool confirmed this is not a tool name if we are here with 1 segment.
        if len(segments) == 1:
            identifier = segments[0]
            logger.info(f"Detected identifier in path: {identifier}")
            # Map the identifier based on pattern
            if identifier.startswith("DTXSID"):
                inferred_args.setdefault("dtxsid", identifier)
            elif identifier.startswith("DTXCID"):
                inferred_args.setdefault("dtxcid", identifier)
            elif len(identifier) >= 5 and identifier.replace("-", "").isdigit():
                inferred_args.setdefault("casrn", identifier)
            else:
                inferred_args.setdefault("query", identifier)

        # Check if we have arguments for inference
        if inferred_args:
            logger.info("Attempting inferred search for resource: %s", resource_name)
            inferred_tool_map = {
                "chemical": "search_chemical",
                "hazard": "search_hazard",
                "exposure": "search_exposures",
                "bioactivity": "search_bioactivity",
                "chemical_list": "search_chemical_list",
                "prioritization": "prioritize_risk_signals",
            }
            tool_to_use = inferred_tool_map.get(resource_name)
            args_to_use = inferred_args
        else:
            tool_to_use = None
            args_to_use = {}

    # 3. Execute the determined tool (if any)
    if tool_to_use:
        # Normalize legacy aliases before validation/dispatch
        alias_map = {"search_exposure": "search_exposures"}
        tool_to_use = alias_map.get(tool_to_use, tool_to_use)
        # Adaptation and execution
        adapted_arguments = _adapt_legacy_arguments(tool_to_use, args_to_use)
        try:
            tool_result = await _handle_tools_call(
                server,
                {"name": tool_to_use, "arguments": adapted_arguments},
                request,
            )

            sanitized_text = _sanitize_tool_result_for_resource_read(tool_result)
            return {
                "contents": [
                    {"uri": uri, "mimeType": "application/json", "text": sanitized_text}
                ]
            }

        except Exception as exc:
            # Catch validation errors (400) or LookupErrors during legacy execution
            raise ValueError(f"Tool execution failed: {exc}") from exc

    # Standard resource read path (No tool found or inferred)
    # (Keep this section the same as previously implemented, including resource lookup and summarization)
    resource_name = parsed.netloc or uri.replace("resource://", "").split("?")[0]

    # Get the resource from the server
    if resource_name not in server.resources:
        # Handle potential empty resource name if URI is just "resource://"
        if not resource_name:
            raise ValueError("Invalid resource URI: missing resource name.")
        raise LookupError(f"Resource not found: {resource_name}")

    resource = server.resources[resource_name]

    full_tool_definitions = [
        tool
        for tool in server.tool_registry.list_definitions()
        if tool.get("annotations", {}).get("resource") == resource_name
    ]

    # Assuming _summarize_tool_definitions is defined elsewhere
    summarized_tools = _summarize_tool_definitions(full_tool_definitions)

    resource_content = {
        "name": resource_name,
        "description": resource.description,
        "tools": summarized_tools,
    }

    # Ensure json is imported if not already
    import json

    return {
        "contents": [
            {
                "uri": uri,
                "mimeType": "application/json",
                "text": json.dumps(resource_content),
            }
        ]
    }


async def _handle_tools_call(
    server: MCPServer, params: Dict[str, Any], request: Request
) -> Dict[str, Any]:
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

    # --- Issue 1: Sanitize the response content to prevent client-side parsing issues ---
    # Intercept the result and simplify the 'content' field if it contains oversized JSON dumps
    if (
        isinstance(result, dict)
        and "structuredContent" in result
        and "content" in result
    ):
        structured_data = result.get("structuredContent")
        summary = None

        # Generate a simple summary based on the structured data
        if isinstance(structured_data, list):
            summary = f"Successfully retrieved {len(structured_data)} records."
        elif isinstance(structured_data, dict):
            summary = "Successfully retrieved structured data."

        if summary:
            # Heuristic check: If the original content seems to be a raw JSON dump, replace it
            original_content = result.get("content")
            is_likely_json_dump = False

            if (
                isinstance(original_content, list)
                and len(original_content) > 0
                and isinstance(original_content[0], dict)
                and original_content[0].get("type") == "text"
            ):
                text_content = original_content[0].get("text", "")
                if isinstance(text_content, str):
                    stripped_text = text_content.strip()
                    # Check if it starts like JSON or is excessively long (e.g., > 512 chars)
                    if stripped_text.startswith(("[", "{")) or len(stripped_text) > 512:
                        is_likely_json_dump = True

            if is_likely_json_dump:
                logger.debug(
                    f"Sanitizing large/JSON 'content' field for tool: {tool_name}"
                )
                result["content"] = [{"type": "text", "text": summary}]
    # --- END Issue 1 modification ---

    # Ensure content is serializable JSON
    try:
        json.dumps(result)
    except TypeError as exc:
        logger.debug("Tool result not JSON serializable: %s", exc)
        raise ValueError("Tool result could not be serialized.") from exc

    return result
