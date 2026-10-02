"""Stable SDK2 adapter for the released CompTox evidence-federation surface."""

from __future__ import annotations

import logging
import sys
from typing import Any, Awaitable, Callable

import anyio
from mcp.server.caching import CacheHint
from mcp.server.context import ServerRequestContext
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.server.transport_security import TransportSecuritySettings
from mcp.shared.exceptions import MCPError
from mcp_types import (
    PROTOCOL_VERSION_META_KEY,
    CallToolRequestParams,
    CallToolResult,
    ListPromptsResult,
    ListResourcesResult,
    ListResourceTemplatesResult,
    ListToolsResult,
    PaginatedRequestParams,
    ReadResourceRequestParams,
    ReadResourceResult,
    Resource,
    Tool,
    ToolAnnotations,
)
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

from epacomp_tox.server import MCPServer
from epacomp_tox.settings import settings

TOOL_POLICY_KEY = "org.toxmcp/toolPolicy"
RESOURCE_POLICY_KEY = "org.toxmcp/resourcePolicy"
LEGACY_HTTP_REVISIONS = {"2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"}


def is_modern_request(request: Request, payload: dict[str, Any]) -> bool:
    revision = request.headers.get("mcp-protocol-version")
    if revision and revision not in LEGACY_HTTP_REVISIONS:
        return True
    params = payload.get("params")
    metadata = params.get("_meta") if isinstance(params, dict) else None
    return isinstance(metadata, dict) and PROTOCOL_VERSION_META_KEY in metadata


async def expected_errors(operation: Callable[[], Awaitable[Any]]):
    try:
        return await operation()
    except ValueError as error:
        raise MCPError(-32602, "Invalid method parameters.") from error
    except LookupError as error:
        raise MCPError(-32601, "Method or tool not found.") from error
    except PermissionError as error:
        raise MCPError(-32001, "Access to this method or tool is forbidden.") from error


def create_sdk_server(application: MCPServer) -> Server:
    from . import http as legacy

    def request_params(context, params):
        raw = dict(context.params or {})
        raw.pop("_meta", None)
        return raw

    async def list_tools(
        context: ServerRequestContext, params: PaginatedRequestParams | None
    ) -> ListToolsResult:
        result = legacy._handle_tools_list(application, request_params(context, params))
        tools = []
        for item in result["tools"]:
            extensions = {
                key: value
                for key, value in item["annotations"].items()
                if key
                not in {
                    "title",
                    "readOnlyHint",
                    "destructiveHint",
                    "idempotentHint",
                    "openWorldHint",
                }
            }
            tools.append(
                Tool(
                    name=item["name"],
                    title=item.get("title"),
                    description=item.get("description"),
                    input_schema=item["inputSchema"],
                    output_schema=item.get("outputSchema"),
                    annotations=ToolAnnotations.model_validate(item["annotations"]),
                    meta={TOOL_POLICY_KEY: extensions} if extensions else None,
                )
            )
        return ListToolsResult(tools=tools, next_cursor=result.get("nextCursor"))

    async def list_resources(
        context: ServerRequestContext, params: PaginatedRequestParams | None
    ) -> ListResourcesResult:
        result = legacy._handle_resources_list(
            application, request_params(context, params)
        )
        resources = []
        for original in result["resources"]:
            item = dict(original)
            extensions = {
                key: value
                for key, value in item.get("annotations", {}).items()
                if key not in {"audience", "priority", "lastModified"}
            }
            if extensions:
                item["_meta"] = {RESOURCE_POLICY_KEY: extensions}
            resources.append(Resource.model_validate(item))
        return ListResourcesResult(
            resources=resources, next_cursor=result.get("nextCursor")
        )

    async def templates(
        context: ServerRequestContext, params: PaginatedRequestParams | None
    ) -> ListResourceTemplatesResult:
        return ListResourceTemplatesResult(resource_templates=[])

    async def prompts(
        context: ServerRequestContext, params: PaginatedRequestParams | None
    ) -> ListPromptsResult:
        return ListPromptsResult(prompts=[])

    async def call_tool(
        context: ServerRequestContext, params: CallToolRequestParams
    ) -> CallToolResult:
        # Preserve the existing synchronous dispatch boundary; resource provenance
        # is collected in that same call without introducing cross-thread races.
        result = await expected_errors(
            lambda: legacy._handle_tools_call(
                application,
                {"name": params.name, "arguments": params.arguments or {}},
                context.request,
            )
        )
        return CallToolResult.model_validate(result)

    async def read_resource(
        context: ServerRequestContext, params: ReadResourceRequestParams
    ) -> ReadResourceResult:
        raw = request_params(context, params)
        raw["uri"] = str(params.uri)
        result = await expected_errors(
            lambda: legacy._handle_resources_read(application, raw, context.request)
        )
        return ReadResourceResult.model_validate(result)

    info = application.get_server_info()
    return Server(
        info["name"],
        version=info["version"],
        title=info.get("title"),
        on_list_tools=list_tools,
        on_call_tool=call_tool,
        on_list_resources=list_resources,
        on_read_resource=read_resource,
        on_list_resource_templates=templates,
        on_list_prompts=prompts,
        cache_hints={
            method: CacheHint(ttl_ms=60_000, scope="private")
            for method in [
                "tools/list",
                "resources/list",
                "resources/templates/list",
                "prompts/list",
            ]
        },
    )


def create_sdk_http_app(application: MCPServer):
    def split(value):
        return [part.strip() for part in (value or "").split(",") if part.strip()]

    origins = split(settings.mcp_allowed_origins) or [
        origin for origin in settings.security.allowed_origins if origin != "*"
    ]
    return create_sdk_server(application).streamable_http_app(
        json_response=True,
        stateless_http=True,
        max_request_body_size=settings.mcp_max_request_bytes,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=split(settings.mcp_allowed_hosts)
            or ["localhost:*", "127.0.0.1:*", "[::1]:*"],
            allowed_origins=origins
            or ["http://localhost:*", "http://127.0.0.1:*", "http://[::1]:*"],
        ),
    )


class SDKResponse(Response):
    def __init__(self, application: ASGIApp, body: bytes):
        super().__init__()
        self.application = application
        self.body = body

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        supplied = False

        async def replay():
            nonlocal supplied
            if not supplied:
                supplied = True
                return {"type": "http.request", "body": self.body, "more_body": False}
            return await receive()

        await self.application(scope, replay, send)


async def serve_stdio() -> None:
    logging.basicConfig(
        stream=sys.stderr, level=settings.app.log_level.upper(), force=True
    )
    server = create_sdk_server(MCPServer(validate_health=False))
    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())


def main() -> None:
    anyio.run(serve_stdio)


if __name__ == "__main__":
    main()
