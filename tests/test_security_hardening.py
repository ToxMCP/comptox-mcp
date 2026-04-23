from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from epacomp_tox.resources.base import BaseResource
from epacomp_tox.server import MCPServer
from epacomp_tox.settings import RateLimitSettings
from epacomp_tox.transport.security import AuthContext, AuthError, InMemoryRateLimiter
from epacomp_tox.transport.websocket import create_app


class EchoResource(BaseResource):
    def __init__(self, api_key: str = "dummy"):
        super().__init__(api_key)

    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echo test resource"

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "echo",
                "description": "Echo back provided text",
                "inputSchema": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
            }
        ]

    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        if tool_name != "echo":
            raise ValueError("Unknown tool")
        self._last_metadata = {"resource": self.name}
        return {"echo": parameters["text"]}


class CrashingResource(EchoResource):
    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        raise RuntimeError("secret-token-value")


class EchoServer(MCPServer):
    def __init__(self, resource: Optional[BaseResource] = None):
        self._resource = resource or EchoResource()
        super().__init__(api_key="dummy-key", validate_health=False)

    def _initialize_resources(self) -> Dict[str, BaseResource]:
        return {"echo": self._resource}


class FakeAuthValidator:
    enabled = True

    def authenticate_header(
        self, authorization: Optional[str], *, remote_addr: Optional[str] = None
    ) -> AuthContext:
        if authorization == "Bearer valid":
            return AuthContext(
                subject_hash="subject-hash",
                issuer="https://issuer.example",
                audience=("mcp://test",),
                scopes=("tox:read",),
                expires_at=1893456000,
                token_hash="token-hash",
            )
        if authorization == "Bearer noscope":
            raise AuthError(
                status_code=403,
                error="insufficient_scope",
                description="Bearer token is missing required MCP scope.",
                required_scopes=["tox:read"],
            )
        raise AuthError(
            status_code=401,
            error="invalid_token",
            description="Bearer token is required.",
            required_scopes=["tox:read"],
        )

    def protected_resource_metadata(self) -> Dict[str, Any]:
        return {
            "resource": "https://mcp.example/mcp",
            "authorization_servers": ["https://issuer.example"],
            "scopes_supported": ["tox:read"],
            "bearer_methods_supported": ["header"],
        }

    def www_authenticate_header(self, error: Optional[AuthError] = None) -> str:
        suffix = f', error="{error.error}"' if error else ""
        return (
            'Bearer, resource="https://mcp.example/mcp", '
            'scope="tox:read"'
            f"{suffix}"
        )


def _rpc_call(tool_params: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "echo", "parameters": tool_params},
    }


def test_http_rejects_missing_bearer_token_with_challenge() -> None:
    app = create_app(server=EchoServer(), auth_validator=FakeAuthValidator())
    with TestClient(app) as client:
        response = client.post("/mcp", json=_rpc_call({"text": "hello"}))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == -32000
    assert "WWW-Authenticate" in response.headers
    assert "Bearer" in response.headers["WWW-Authenticate"]


def test_http_rejects_valid_token_missing_scope() -> None:
    app = create_app(server=EchoServer(), auth_validator=FakeAuthValidator())
    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            json=_rpc_call({"text": "hello"}),
            headers={"authorization": "Bearer noscope"},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == -32001


def test_http_does_not_echo_raw_authentication_metadata() -> None:
    app = create_app(server=EchoServer(), auth_validator=FakeAuthValidator())
    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            json=_rpc_call({"text": "hello"}),
            headers={"authorization": "Bearer valid"},
        )

    assert response.status_code == 200
    body_text = response.text
    assert "Bearer valid" not in body_text
    structured = response.json()["result"]["structuredContent"]
    assert structured["metadata"]["session"]["auth"]["subjectHash"] == "subject-hash"


def test_protected_resource_metadata_endpoint_is_public() -> None:
    app = create_app(server=EchoServer(), auth_validator=FakeAuthValidator())
    with TestClient(app) as client:
        response = client.get("/.well-known/oauth-protected-resource")

    assert response.status_code == 200
    assert response.json()["resource"] == "https://mcp.example/mcp"


def test_invalid_extra_tool_parameter_fails_before_execution() -> None:
    app = create_app(server=EchoServer(), auth_validator=FakeAuthValidator())
    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            json=_rpc_call({"text": "hello", "extra": "nope"}),
            headers={"authorization": "Bearer valid"},
        )

    assert response.status_code == 400
    assert "Additional properties" in response.json()["error"]["message"]


def test_tool_call_rate_limit_returns_jsonrpc_error() -> None:
    app = create_app(server=EchoServer(), auth_validator=FakeAuthValidator())
    app.state.rate_limiter = InMemoryRateLimiter(
        RateLimitSettings(requests_per_minute=60, burst=1)
    )
    with TestClient(app) as client:
        first = client.post(
            "/mcp",
            json=_rpc_call({"text": "first"}),
            headers={"authorization": "Bearer valid"},
        )
        second = client.post(
            "/mcp",
            json=_rpc_call({"text": "second"}),
            headers={"authorization": "Bearer valid"},
        )

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error"]["code"] == -32029


def test_internal_tool_exception_does_not_leak_raw_detail() -> None:
    app = create_app(
        server=EchoServer(resource=CrashingResource()),
        auth_validator=FakeAuthValidator(),
    )
    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            json=_rpc_call({"text": "hello"}),
            headers={"authorization": "Bearer valid"},
        )

    assert response.status_code == 200
    assert response.json()["result"]["isError"] is True
    assert "secret-token-value" not in response.text


def test_websocket_rejects_missing_bearer_token() -> None:
    app = create_app(server=EchoServer(), auth_validator=FakeAuthValidator())
    with TestClient(app) as client:
        with client.websocket_connect("/mcp/ws") as websocket:
            message = websocket.receive_json()
            assert message["error"]["code"] == -32000
            with pytest.raises(WebSocketDisconnect):
                websocket.receive_text()


def test_websocket_accepts_valid_bearer_token() -> None:
    app = create_app(server=EchoServer(), auth_validator=FakeAuthValidator())
    with TestClient(app) as client:
        with client.websocket_connect(
            "/mcp/ws", headers={"authorization": "Bearer valid"}
        ) as websocket:
            websocket.send_json(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-11-25",
                        "capabilities": {},
                        "clientInfo": {"name": "test"},
                    },
                }
            )
            assert websocket.receive_json()["result"]["protocolVersion"] == "2025-11-25"
