"""Track-A conformance baseline: drive the REAL MCP server over its ACTUAL
transport (WebSocket) and assert the advertised tool/resource surface matches
the committed catalog snapshot exactly.

This complements the existing gates without duplicating them:

* ``test_mcp_conformance_suite.py`` exercises the WebSocket handshake and
  ``tools/list``/``resources/list`` discovery, but against a deterministic
  *stub* server (``ConformanceServer``) and only asserts a *required subset*.
* ``test_tool_catalog_snapshot.py`` asserts the *exact* tool/resource set of
  the real ``MCPServer``, but in-process via ``server.get_tools()`` -- it never
  crosses the transport boundary.

Neither asserts that the **real** server, when discovered by a real MCP client
over the **actual** WebSocket transport (``/mcp/ws``), advertises *exactly* the
committed catalog. A registration that is dropped, renamed, or shadowed only on
the wire (e.g. a transport-layer filter) would slip past both. This gate closes
that gap by comparing the live ``tools/list``/``resources/list`` payload to the
checked-in ``tests/fixtures/tool_catalog_snapshot.json`` literal.

PROOF (advisory gate self-test): rename a registered tool -> the live
``tools/list`` set diverges from the committed snapshot -> this test goes red
with an attributed diff -> revert -> green.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from fastapi.testclient import TestClient

from epacomp_tox.server import MCPServer
from epacomp_tox.transport.websocket import create_app

SNAPSHOT_PATH = Path(__file__).parent / "fixtures" / "tool_catalog_snapshot.json"

PROTOCOL_VERSION = "2025-06-18"


def _load_snapshot() -> Dict[str, Any]:
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def _discover_over_websocket() -> Dict[str, Any]:
    """Connect a real MCP client to the real server over the WebSocket
    transport and return the advertised tool names + resource names."""

    server = MCPServer(api_key="dummy-key", validate_health=False)
    app = create_app(server=server)
    client = TestClient(app)

    with client.websocket_connect("/mcp/ws") as websocket:
        websocket.send_json(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {
                        "name": "track-a-conformance",
                        "version": "0.0.0",
                    },
                },
            }
        )
        handshake = websocket.receive_json()
        assert handshake["id"] == 1
        notification = websocket.receive_json()
        assert notification.get("method") == "notifications/initialized"

        websocket.send_json(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        )
        tools_response = websocket.receive_json()

        websocket.send_json(
            {"jsonrpc": "2.0", "id": 3, "method": "resources/list", "params": {}}
        )
        resources_response = websocket.receive_json()

    assert tools_response["result"]["nextCursor"] is None
    return {
        "tool_names": sorted(
            tool["name"] for tool in tools_response["result"]["tools"]
        ),
        "resource_names": [
            resource["name"] for resource in resources_response["result"]["resources"]
        ],
    }


def test_live_websocket_tool_surface_matches_committed_snapshot() -> None:
    """The real server's WebSocket-advertised tool set must equal the committed
    catalog snapshot exactly (no drops, renames, or wire-only shadowing)."""

    snapshot = _load_snapshot()
    live = _discover_over_websocket()

    expected_tools = sorted(snapshot["tool_names"])
    actual_tools = live["tool_names"]

    missing = sorted(set(expected_tools) - set(actual_tools))
    extra = sorted(set(actual_tools) - set(expected_tools))
    assert actual_tools == expected_tools, (
        "Live WebSocket tools/list diverged from committed catalog snapshot. "
        f"Missing from wire: {missing}. Extra on wire: {extra}."
    )


def test_live_websocket_resource_surface_matches_committed_snapshot() -> None:
    """The real server's WebSocket-advertised resource set (and ordering) must
    equal the committed catalog snapshot exactly."""

    snapshot = _load_snapshot()
    live = _discover_over_websocket()

    assert live["resource_names"] == snapshot["resource_names"], (
        "Live WebSocket resources/list diverged from committed catalog "
        f"snapshot. Wire: {live['resource_names']}. "
        f"Snapshot: {snapshot['resource_names']}."
    )
