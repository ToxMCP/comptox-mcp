from __future__ import annotations

import json
from typing import Any, Dict, List

from fastapi.testclient import TestClient

from ctxpy import RateLimitInfo
from epacomp_tox.resources.base import BaseResource
from epacomp_tox.server import MCPServer
from epacomp_tox.transport.common import PRIMARY_PROTOCOL_VERSION
from epacomp_tox.transport.http import INVALID_PARAMS, METHOD_NOT_FOUND
from epacomp_tox.transport.websocket import create_app


class EchoResource(BaseResource):
    """Simple resource used to verify HTTP transport behaviour."""

    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echo test resource"

    def __init__(self, api_key: str = "dummy"):
        super().__init__(api_key)

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "echo",
                "description": "Echo back provided text",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                    },
                    "required": ["text"],
                },
            }
        ]

    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        if tool_name != "echo":
            raise ValueError("Unknown tool")
        payload = parameters["text"]
        self._last_metadata = {"resource": self.name}
        return {"echo": payload}


class DummyMCPServer(MCPServer):
    def _initialize_resources(self) -> Dict[str, BaseResource]:
        return {"echo": EchoResource()}


class NestedMetadataEchoResource(EchoResource):
    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        if tool_name != "echo":
            raise ValueError("Unknown tool")
        self._last_metadata = {
            "resource": self.name,
            "steps": {
                "echo:call": {
                    "metadata": {
                        "rate_limit": RateLimitInfo(
                            limit=None, remaining=None, reset=None
                        )
                    }
                }
            },
        }
        return {"echo": parameters["text"]}


class NestedMetadataMCPServer(MCPServer):
    def _initialize_resources(self) -> Dict[str, BaseResource]:
        return {"echo": NestedMetadataEchoResource()}


class DomainMetadataEchoResource(EchoResource):
    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        if tool_name != "echo":
            raise ValueError("Unknown tool")
        self._last_metadata = {
            "resource": self.name,
            "steps": {
                "echo:call": {
                    "metadata": {
                        "rate_limit": RateLimitInfo(
                            limit=None, remaining=None, reset=None
                        )
                    }
                }
            },
        }
        return {
            "echo": parameters["text"],
            "metadata": {"suiteRole": "evidence-federation"},
        }


class DomainMetadataMCPServer(MCPServer):
    def _initialize_resources(self) -> Dict[str, BaseResource]:
        return {"echo": DomainMetadataEchoResource()}


class PrioritizationEchoResource(BaseResource):
    @property
    def name(self) -> str:
        return "prioritization"

    @property
    def description(self) -> str:
        return "Prioritization test resource"

    def __init__(self, api_key: str = "dummy"):
        super().__init__(api_key)

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "prioritize_risk_signals",
                "description": "Return a deterministic prioritization payload",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dtxsid": {"type": "string"},
                    },
                    "required": ["dtxsid"],
                },
            }
        ]

    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        if tool_name != "prioritize_risk_signals":
            raise ValueError("Unknown tool")
        self._last_metadata = {"resource": self.name}
        return {
            "chemicalRef": {"dtxsid": parameters["dtxsid"]},
            "prioritization": {"priorityBand": "higher", "marginOfExposure": 50.0},
        }


class PrioritizationReadMCPServer(MCPServer):
    def _initialize_resources(self) -> Dict[str, BaseResource]:
        return {"prioritization": PrioritizationEchoResource()}


def _create_app():
    server = DummyMCPServer(api_key="dummy-key", validate_health=False)
    return create_app(server=server)


def _create_nested_metadata_app():
    server = NestedMetadataMCPServer(api_key="dummy-key", validate_health=False)
    return create_app(server=server)


def _create_domain_metadata_app():
    server = DomainMetadataMCPServer(api_key="dummy-key", validate_health=False)
    return create_app(server=server)


def _create_prioritization_read_app():
    server = PrioritizationReadMCPServer(api_key="dummy-key", validate_health=False)
    return create_app(server=server)


def test_http_transport_initialize_and_list_and_call():
    app = _create_app()
    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"capabilities": {}},
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["result"]["protocolVersion"] == PRIMARY_PROTOCOL_VERSION
        assert payload["result"]["serverInfo"]["name"] == "epa-comp-tox-mcp"
        assert payload["result"]["capabilities"]["tools"]["enabled"] is True

        list_response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        )
        assert list_response.status_code == 200
        tools_payload = list_response.json()
        tools = tools_payload["result"]["tools"]
        assert any(tool["name"] == "echo" for tool in tools)
        first_tool = next(tool for tool in tools if tool["name"] == "echo")
        assert first_tool["annotations"]["resource"] == "echo"

        call_response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "echo", "parameters": {"text": "hello"}},
            },
        )
        assert call_response.status_code == 200
        call_payload = call_response.json()["result"]
        assert call_payload["structuredContent"]["echo"] == "hello"


def test_http_transport_method_not_found():
    app = _create_app()
    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 10, "method": "unknown"},
        )
        assert response.status_code == 404
        payload = response.json()
        assert payload["error"]["code"] == METHOD_NOT_FOUND
        assert "Method not found" in payload["error"]["message"]


def test_http_transport_tool_not_found():
    app = _create_app()
    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 42,
                "method": "tools/call",
                "params": {"name": "missing", "parameters": {"text": "nope"}},
            },
        )
        assert response.status_code == 404
        payload = response.json()
        assert payload["error"]["code"] == METHOD_NOT_FOUND
        assert "missing" in payload["error"]["message"]


def test_http_transport_invalid_parameters():
    app = _create_app()
    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 11,
                "method": "tools/call",
                "params": {"name": "echo", "parameters": {}},
            },
        )
        assert response.status_code == 400
        payload = response.json()
        assert payload["error"]["code"] == INVALID_PARAMS


def test_http_transport_serializes_nested_metadata_rate_limit() -> None:
    app = _create_nested_metadata_app()
    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 12,
                "method": "tools/call",
                "params": {"name": "echo", "parameters": {"text": "hello"}},
            },
        )

        assert response.status_code == 200
        payload = response.json()["result"]["structuredContent"]
        nested_rate_limit = payload["metadata"]["steps"]["echo:call"]["metadata"][
            "rate_limit"
        ]
        assert nested_rate_limit == {
            "limit": None,
            "remaining": None,
            "reset": None,
        }


def test_http_transport_preserves_domain_metadata_when_attaching_runtime_metadata() -> (
    None
):
    app = _create_domain_metadata_app()
    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 13,
                "method": "tools/call",
                "params": {"name": "echo", "parameters": {"text": "hello"}},
            },
        )

        assert response.status_code == 200
        payload = response.json()["result"]["structuredContent"]
        assert payload["metadata"] == {"suiteRole": "evidence-federation"}
        assert payload["mcpMetadata"]["resource"] == "echo"
        nested_rate_limit = payload["mcpMetadata"]["steps"]["echo:call"]["metadata"][
            "rate_limit"
        ]
        assert nested_rate_limit == {
            "limit": None,
            "remaining": None,
            "reset": None,
        }


def test_http_resources_read_infers_prioritization_tool_from_resource_uri() -> None:
    app = _create_prioritization_read_app()
    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 14,
                "method": "resources/read",
                "params": {
                    "uri": "resource://prioritization?dtxsid=DTXSID7020182",
                },
            },
        )

        assert response.status_code == 200
        payload = response.json()["result"]["contents"][0]
        text = json.loads(payload["text"])
        assert text["chemicalRef"]["dtxsid"] == "DTXSID7020182"
        assert text["prioritization"]["priorityBand"] == "higher"
