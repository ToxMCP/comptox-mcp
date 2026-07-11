from __future__ import annotations

from typing import Any, Dict
from unittest import mock

from fastapi.testclient import TestClient

from epacomp_tox.resources.base import BaseResource
from epacomp_tox.server import MCPServer
from epacomp_tox.transport.websocket import create_app


class NoopResource(BaseResource):
    @property
    def name(self) -> str:
        return "noop"

    @property
    def description(self) -> str:
        return "No-op resource"

    def __init__(self, api_key: str = "dummy"):
        super().__init__(api_key)

    def get_tools(self) -> list[Dict[str, Any]]:
        return []

    def execute_tool(
        self, tool_name: str, parameters: Dict[str, Any]
    ) -> Any:  # pragma: no cover - unused
        raise NotImplementedError


class HealthServer(MCPServer):
    def _initialize_resources(self) -> Dict[str, BaseResource]:
        return {"noop": NoopResource()}


def test_healthz_returns_ok() -> None:
    server = HealthServer(api_key="dummy")
    app = create_app(server=server)
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"


def test_readyz_returns_ok_when_health_passes() -> None:
    server = HealthServer(api_key="dummy")
    app = create_app(server=server)
    client = TestClient(app)
    with mock.patch.object(
        server,
        "check_health",
        return_value={
            "ok": True,
            "status": 200,
            "url": "https://internal.example.test/ctx-api",
        },
    ) as mock_check_health:
        response = client.get("/readyz")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["ctx"]["ok"] is True
    assert "url" not in body["ctx"]
    assert "internal.example.test" not in response.text
    mock_check_health.assert_called_once_with(timeout=2.0, probe_mode="readiness")


def test_readyz_returns_503_when_health_fails_without_cache() -> None:
    server = HealthServer(api_key="dummy")
    app = create_app(server=server)
    client = TestClient(app)
    with mock.patch.object(
        server, "check_health", side_effect=RuntimeError("auth failed")
    ):
        response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["detail"] == "CTX health check failed"
    assert "auth failed" not in response.text


def test_readyz_returns_degraded_when_cached_health_exists() -> None:
    server = HealthServer(api_key="dummy")
    server._last_health = {"ok": True, "status": 200, "url": "https://example.test"}
    app = create_app(server=server)
    client = TestClient(app)
    with mock.patch.object(
        server, "check_health", side_effect=RuntimeError("auth failed")
    ):
        response = client.get("/readyz")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["ctx"]["status"] == 200
    assert body["detail"] == "CTX health check failed; cached status returned."
    assert "auth failed" not in response.text
    assert "url" not in body["ctx"]
    assert "example.test" not in response.text


def test_readyz_returns_503_when_server_unavailable() -> None:
    server = HealthServer(api_key="dummy")
    app = create_app(server=server)
    app.state.mcp_server_error = RuntimeError("boom")
    app.state.mcp_server = None
    client = TestClient(app)

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["detail"] == "MCP server not initialized"
