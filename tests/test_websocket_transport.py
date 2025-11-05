from __future__ import annotations

import json
import time
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi.testclient import TestClient

from epacomp_tox.resources.base import BaseResource
from epacomp_tox.server import MCPServer
from epacomp_tox.transport.websocket import create_app


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_event_fixture(name: str) -> Dict[str, Any]:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def _assert_structure(expected: Any, actual: Any) -> None:
    if isinstance(expected, dict):
        assert isinstance(actual, dict)
        for key, value in expected.items():
            assert key in actual
            _assert_structure(value, actual[key])
    elif isinstance(expected, list):
        assert isinstance(actual, list)
        if expected:
            for item in actual:
                _assert_structure(expected[0], item)
    elif isinstance(expected, float):
        assert isinstance(actual, (int, float))
    else:
        assert isinstance(actual, type(expected))


def _assert_event_structure(actual: Dict[str, Any], fixture_name: str) -> None:
    expected = _load_event_fixture(fixture_name)
    assert actual["jsonrpc"] == expected["jsonrpc"]
    assert actual["method"] == expected["method"]
    _assert_structure(expected["params"], actual["params"])


class EchoResource(BaseResource):
    """Simple test resource that echoes payloads for deterministic assertions."""

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
                        "text": {
                            "type": "string",
                            "description": "Text to echo back",
                        }
                    },
                    "required": ["text"],
                },
            }
        ]

    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        if tool_name != "echo":
            raise ValueError("Unknown tool")
        text = parameters["text"]
        self._last_metadata = {"resource": self.name}
        return {"echo": text}


class SlowResource(BaseResource):
    """Resource that sleeps before returning to exercise timeout/cancellation paths."""

    @property
    def name(self) -> str:
        return "slow"

    @property
    def description(self) -> str:
        return "Slow test resource"

    def __init__(self, api_key: str = "dummy"):
        super().__init__(api_key)

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "slow_echo",
                "description": "Sleep for a bit then echo text",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "sleep": {"type": "number"},
                    },
                    "required": ["text"],
                },
            }
        ]

    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        if tool_name != "slow_echo":
            raise ValueError("Unknown tool")
        sleep_for = float(parameters.get("sleep", 0.2))
        time.sleep(sleep_for)
        text = parameters["text"]
        self._last_metadata = {"resource": self.name, "sleep": sleep_for}
        return {"echo": text, "slept": sleep_for}


class DummyMCPServer(MCPServer):
    def _initialize_resources(self) -> Dict[str, BaseResource]:
        return {"echo": EchoResource(), "slow": SlowResource()}


@contextmanager
def _connect():
    server = DummyMCPServer(api_key="dummy-key", validate_health=False)
    app = create_app(server=server)
    with TestClient(app) as client:
        with client.websocket_connect("/mcp/ws") as websocket:
            yield server, websocket


def _initialize(websocket, *, capabilities: Optional[Dict[str, Any]] = None, heartbeat_ms: Optional[int] = None):
    websocket.send_json(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": capabilities or {},
                "clientInfo": {"name": "test-client", "version": "0.0.1"},
                **({"heartbeatIntervalMs": heartbeat_ms} if heartbeat_ms is not None else {}),
            },
        }
    )
    init_response = websocket.receive_json()
    notification = websocket.receive_json()
    return init_response, notification


def test_websocket_transport_flow():
    with _connect() as (_, websocket):
        init_response, notification = _initialize(websocket)
        result = init_response["result"]
        assert result["protocolVersion"] == "2025-06-18"
        assert result["serverInfo"]["name"] == "epa-comp-tox-mcp"
        assert "transport" in result
        assert result["capabilities"]["tools"]["streams"] is True
        assert result["capabilities"]["tools"]["cancel"] is True
        assert notification["method"] == "notifications/initialized"

        websocket.send_json(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        )
        tools_response = websocket.receive_json()
        tools = tools_response["result"]["tools"]
        assert any(tool["name"] == "echo" for tool in tools)

        websocket.send_json(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "echo", "arguments": {"text": "hello"}},
            }
        )
        events: List[Dict[str, Any]] = []
        while True:
            message = websocket.receive_json()
            if message.get("id") == 3:
                call_response = message
                break
            events.append(message)

        methods = {event["method"] for event in events}
        assert "events/log" in methods
        assert "events/result" in methods
        assert "events/end" in methods

        for event in events:
            if event["method"] == "events/log":
                _assert_event_structure(event, "events_log.json")
            elif event["method"] == "events/result":
                assert "result" in event["params"]
                result_payload = event["params"]["result"]
                assert result_payload["structuredContent"]["data"]["echo"] == "hello"
            elif event["method"] == "events/end":
                _assert_event_structure(event, "events_end.json")

        result_event = next(event for event in events if event["method"] == "events/result")
        structured = result_event["params"]["result"]["structuredContent"]
        assert structured["data"]["echo"] == "hello"

        call_result = call_response["result"]
        assert call_result["isError"] is False
        assert call_result["structuredContent"]["data"]["echo"] == "hello"
        assert call_result["requestId"] == result_event["params"]["requestId"]


def test_tools_call_timeout():
    with _connect() as (_, websocket):
        _initialize(websocket)

        websocket.send_json(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "slow_echo",
                    "arguments": {"text": "timeout", "sleep": 0.2},
                    "timeoutMs": 10,
                    "requestId": "timeout-case",
                },
            }
        )

        events: List[Dict[str, Any]] = []
        error_response: Optional[Dict[str, Any]] = None
        while error_response is None:
            message = websocket.receive_json()
            if message.get("id") == 2 and "error" in message:
                error_response = message
            else:
                events.append(message)

        error_codes = [event["params"].get("code") for event in events if event["method"] == "events/error"]
        assert -32003 in error_codes
        end_events = [event for event in events if event["method"] == "events/end"]
        assert end_events[0]["params"]["status"] == "error"

        for event in events:
            if event["method"] == "events/error":
                params = event["params"]
                assert params["code"] == -32003
                assert params["data"]["reason"] == "timeout"
            elif event["method"] == "events/end":
                _assert_event_structure(event, "events_end.json")

        assert error_response["error"]["code"] == -32003
        assert error_response["error"]["data"]["requestId"] == "timeout-case"


def test_tools_call_cancel():
    with _connect() as (_, websocket):
        _initialize(websocket)

        websocket.send_json(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "slow_echo",
                    "arguments": {"text": "cancel", "sleep": 1.0},
                    "requestId": "cancel-case",
                },
            }
        )

        websocket.send_json(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/cancel",
                "params": {"requestId": "cancel-case"},
            }
        )

        events: List[Dict[str, Any]] = []
        cancel_response: Optional[Dict[str, Any]] = None
        call_response: Optional[Dict[str, Any]] = None
        while cancel_response is None or call_response is None:
            message = websocket.receive_json()
            if message.get("id") == 3:
                cancel_response = message
            elif message.get("id") == 2:
                call_response = message
            else:
                events.append(message)

        assert cancel_response["result"]["status"] == "cancelled"
        assert call_response["error"]["code"] == -32800

        error_events = [event for event in events if event["method"] == "events/error"]
        assert error_events[0]["params"]["code"] == -32800
        end_events = [event for event in events if event["method"] == "events/end"]
        assert end_events[0]["params"]["status"] == "cancelled"

        for event in events:
            if event["method"] == "events/error":
                params = event["params"]
                assert params["code"] == -32800
            elif event["method"] == "events/end":
                _assert_event_structure(event, "events_end.json")


def test_ping_and_capability_negotiation():
    requested_caps = {"tools": {"streams": False, "cancel": False}}
    with _connect() as (server, websocket):
        init_response, _ = _initialize(websocket, capabilities=requested_caps)
        result = init_response["result"]
        session_id = result["sessionId"]

        negotiated_tools = result["capabilities"]["tools"]
        assert negotiated_tools["streams"] is False
        assert negotiated_tools["cancel"] is False

        metrics = server.get_transport_metrics()
        assert metrics["sessions"]["active"] == 1
        streams_metric = metrics["capabilities"]["active"]["tools.streams"]
        cancel_metric = metrics["capabilities"]["active"]["tools.cancel"]
        assert streams_metric["disabled"] == 1 and streams_metric["enabled"] == 0
        assert cancel_metric["disabled"] == 1 and cancel_metric["enabled"] == 0

        websocket.send_json({"jsonrpc": "2.0", "id": 99, "method": "ping", "params": {}})
        ping_response = websocket.receive_json()
        assert ping_response["id"] == 99
        assert "timestamp" in ping_response["result"]

        websocket.send_json(
            {
                "jsonrpc": "2.0",
                "id": 100,
                "method": "tools/cancel",
                "params": {"requestId": "not-running"},
            }
        )
        cancel_response = websocket.receive_json()
        assert cancel_response["id"] == 100
        assert cancel_response["error"]["code"] == -32004

        websocket.send_json(
            {
                "jsonrpc": "2.0",
                "id": 101,
                "method": "tools/call",
                "params": {
                    "name": "echo",
                    "arguments": {"text": "no-stream"},
                    "requestId": "nostream",
                },
            }
        )
        call_response = websocket.receive_json()
        assert call_response["id"] == 101
        assert "method" not in call_response
        assert call_response["result"]["requestId"] == "nostream"
        assert (
            call_response["result"]["structuredContent"]["data"]["echo"]
            == "no-stream"
        )
        metadata = call_response["result"]["structuredContent"]["metadata"]["session"]
        assert metadata["sessionId"] == session_id
        assert metadata["negotiatedCapabilities"]["tools"]["streams"] is False

        session_meta = server._sessions[session_id]
        client_tools = session_meta["clientCapabilities"]["tools"]
        negotiated = session_meta["negotiatedCapabilities"]["tools"]
        assert client_tools["streams"] is False
        assert negotiated["streams"] is False
        assert negotiated["cancel"] is False

    drained_metrics = server.get_transport_metrics()
    assert drained_metrics["sessions"]["active"] == 0
    assert drained_metrics["sessions"]["closed"] >= 1


def test_metrics_endpoint_reports_transport_summary():
    requested_caps = {"tools": {"streams": False, "cancel": True}}
    server = DummyMCPServer(api_key="dummy-key", validate_health=False)
    app = create_app(server=server)
    with TestClient(app) as client:
        with client.websocket_connect("/mcp/ws") as websocket:
            _initialize(websocket, capabilities=requested_caps)
        summary = server.get_transport_metrics()
        assert summary["capabilities"]["all"]["tools.streams"]["disabled"] == 1
        response = client.get("/metrics")
        assert response.status_code == 200
        body = response.text
        assert "mcp_sessions_total" in body
        assert 'mcp_sessions_total{status="closed"}' in body
        assert any(
            'capability="tools.streams"' in line
            and 'scope="all"' in line
            and 'state="disabled"' in line
            and line.strip().endswith("1.0")
            for line in body.splitlines()
        )
