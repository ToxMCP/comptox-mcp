from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from epacomp_tox.settings import settings
from epacomp_tox.transport.websocket import create_app
from tests.test_http_transport import DummyMCPServer

PROTOCOL = "2026-07-28"


def post(client, method, params=None, headers=None):
    params = {
        **(params or {}),
        "_meta": {
            "io.modelcontextprotocol/protocolVersion": PROTOCOL,
            "io.modelcontextprotocol/clientCapabilities": {},
        },
    }
    request_headers = {
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": PROTOCOL,
        "Mcp-Method": method,
    }
    if method == "tools/call":
        request_headers["Mcp-Name"] = params["name"]
    if method == "resources/read":
        request_headers["Mcp-Name"] = params["uri"]
    request_headers.update(headers or {})
    return client.post(
        "/mcp",
        headers=request_headers,
        json={"jsonrpc": "2.0", "id": 7, "method": method, "params": params},
    )


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "mcp_allowed_hosts", None)
    monkeypatch.setattr(settings, "mcp_allowed_origins", None)
    server = DummyMCPServer(api_key="offline-test-key", validate_health=False)
    with TestClient(
        create_app(server=server), base_url="http://localhost:8200"
    ) as value:
        yield value


def test_modern_full_catalog_preserves_released_contracts(monkeypatch):
    from epacomp_tox.server import MCPServer

    monkeypatch.setattr(settings, "mcp_allowed_hosts", None)
    monkeypatch.setattr(settings, "mcp_allowed_origins", None)
    server = MCPServer(api_key="offline-test-key", validate_health=False)
    with TestClient(
        create_app(server=server), base_url="http://localhost:8200"
    ) as value:
        catalog = {}
        for kind, key in [
            ("tools", "org.toxmcp/toolPolicy"),
            ("resources", "org.toxmcp/resourcePolicy"),
        ]:
            result = post(value, kind + "/list").json()["result"]
            assert result["ttlMs"] == 60_000 and result["cacheScope"] == "private"
            catalog[kind] = []
            for original in result[kind]:
                item = dict(original)
                metadata = item.pop("_meta", {})
                if metadata:
                    assert set(metadata) == {key}
                    item["annotations"].update(metadata[key])
                catalog[kind].append(item)
        baseline = json.loads(
            (
                Path(__file__).parent / "compatibility/v0.2.7-catalog-sha256.json"
            ).read_text()
        )
        assert len(catalog["tools"]) == baseline["tools"] == 85
        assert len(catalog["resources"]) == baseline["resources"] == 10
        assert (
            hashlib.sha256(
                json.dumps(catalog, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            == baseline["sha256"]
        )
        first = post(value, "tools/list", {"limit": 2}).json()["result"]
        second = post(
            value, "tools/list", {"limit": 2, "cursor": first["nextCursor"]}
        ).json()["result"]
        assert [tool["name"] for tool in first["tools"] + second["tools"]] == [
            tool["name"] for tool in catalog["tools"][:4]
        ]
        assert (
            post(value, "resources/templates/list").json()["result"][
                "resourceTemplates"
            ]
            == []
        )
        assert post(value, "prompts/list").json()["result"]["prompts"] == []
        assert (
            PROTOCOL
            in post(value, "server/discover").json()["result"]["supportedVersions"]
        )


def test_modern_tool_preserves_runtime_session_context(client):
    result = post(
        client,
        "tools/call",
        {"name": "echo", "arguments": {"text": "science"}},
        {"x-mcp-session-id": "legacy-context-id"},
    ).json()["result"]
    assert result["structuredContent"] == {"echo": "science"}
    assert result["_meta"]["resource"] == "echo"
    assert result["_meta"]["session"]["sessionId"] == "legacy-context-id"
    assert client.get("/healthz").status_code == 200


def test_modern_invalid_arguments_and_unknown_tool(client):
    for name, arguments, code in [("echo", {}, -32602), ("absent", {}, -32601)]:
        result = post(client, "tools/call", {"name": name, "arguments": arguments})
        assert result.json()["error"]["code"] == code
    assert post(client, "server/discover").status_code == 200


def test_modern_resource_read_preserves_descriptor_and_uri_shim(client):
    descriptor = post(client, "resources/read", {"uri": "resource://echo"}).json()[
        "result"
    ]
    assert json.loads(descriptor["contents"][0]["text"])["name"] == "echo"
    tunneled = post(
        client, "resources/read", {"uri": "resource://echo/echo?text=science"}
    ).json()["result"]
    assert json.loads(tunneled["contents"][0]["text"]) == {"echo": "science"}


@pytest.mark.parametrize(
    "revision", ["2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"]
)
def test_legacy_initialize_and_aliases_remain(client, revision):
    response = client.post(
        "/mcp",
        headers={"MCP-Protocol-Version": revision},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": revision},
        },
    )
    assert response.json()["result"]["protocolVersion"] == revision
    result = client.post(
        "/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools.list", "params": {}}
    )
    assert result.json()["result"]["tools"][0]["annotations"]["resource"] == "echo"


@pytest.mark.parametrize(
    "headers",
    [
        {"Host": "attacker.example"},
        {"Origin": "https://attacker.example"},
        {"Mcp-Method": "tools/call"},
        {"MCP-Protocol-Version": "9999-01-01"},
    ],
)
def test_modern_bad_authority_and_protocol_rejected(client, headers):
    assert post(client, "tools/list", headers=headers).status_code in {400, 403, 421}
    assert post(client, "tools/list").status_code == 200


def test_body_limit_bounds_streamed_and_declared_requests(client):
    response = client.post(
        "/mcp",
        content=iter([b" " * 3_000_000, b" " * 3_000_000]),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    for declared in ["invalid", "-1"]:
        assert (
            client.post(
                "/mcp", content=b"{}", headers={"Content-Length": declared}
            ).status_code
            == 400
        )


def test_sdk_headers_work_through_browser_preflight(client):
    response = client.options(
        "/mcp",
        headers={
            "Origin": "http://localhost:8200",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,mcp-protocol-version,mcp-method,mcp-name",
        },
    )
    assert response.status_code == 200


def test_parallel_calls_preserve_ids_and_individual_results(client):
    def call(index):
        result = post(
            client, "tools/call", {"name": "echo", "arguments": {"text": str(index)}}
        ).json()
        assert result["id"] == 7
        assert result["result"]["structuredContent"] == {"echo": str(index)}
        return result["result"]["_meta"]["session"]["sessionId"]

    with ThreadPoolExecutor(max_workers=4) as pool:
        sessions = list(pool.map(call, range(12)))
    assert len(set(sessions)) == 12
