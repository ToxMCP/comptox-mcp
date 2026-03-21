from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from fastapi.testclient import TestClient

from epacomp_tox.resources.base import BaseResource
from epacomp_tox.server import MCPServer
from epacomp_tox.transport.websocket import create_app

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class ConformanceResource(BaseResource):
    """Stub resource providing deterministic tool definitions for conformance tests."""

    def __init__(
        self, api_key: str, name: str, description: str, tools: List[Dict[str, Any]]
    ):
        super().__init__(api_key)
        self._name = name
        self._description = description
        self._tools = tools

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    def get_tools(self) -> List[Dict[str, Any]]:
        return self._tools

    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        return {"tool": tool_name, "parameters": parameters}


class ConformanceServer(MCPServer):
    """MCPServer subclass that exposes deterministic stub resources."""

    RESOURCE_SPECS: Dict[str, Dict[str, Any]] = {
        "chemical": {
            "description": "Access to chemical structures, nomenclature, IDs, and properties",
            "tools": [
                {"name": "search_chemical"},
                {"name": "batch_search_chemical"},
            ],
        },
        "exposure": {
            "description": "Access to CPDat, HTTK, QSURs, and related exposure data",
            "tools": [
                {"name": "search_cpdat"},
                {"name": "search_httk"},
            ],
        },
        "hazard": {
            "description": "Access to hazard data from ToxValDB",
            "tools": [{"name": "search_hazard"}],
        },
        "chemical_list": {
            "description": "Access to public chemical lists",
            "tools": [
                {"name": "get_public_list_names"},
                {"name": "get_full_list"},
            ],
        },
        "cheminformatics": {
            "description": "Cheminformatics helpers including ToxPrints",
            "tools": [{"name": "search_toxprints"}],
        },
        "interop": {
            "description": "Cross-suite evidence packaging and handoff builders for AOP and PBPK consumers",
            "tools": [
                {"name": "assemble_comptox_evidence_pack"},
                {"name": "build_aop_linkage_summary"},
                {"name": "build_pbpk_context_bundle"},
            ],
        },
    }

    def _initialize_resources(self) -> Dict[str, BaseResource]:
        resources: Dict[str, BaseResource] = {}
        for resource_name, spec in self.RESOURCE_SPECS.items():
            tools: List[Dict[str, Any]] = []
            for tool in spec["tools"]:
                tools.append(
                    {
                        "name": tool["name"],
                        "description": f"Stub tool for {tool['name']}",
                        "inputSchema": {"type": "object"},
                    }
                )
            resources[resource_name] = ConformanceResource(
                self.api_key,
                name=resource_name,
                description=spec["description"],
                tools=tools,
            )
        return resources


def _load_fixture(name: str) -> Dict[str, Any]:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def _create_client() -> TestClient:
    server = ConformanceServer(api_key="dummy-key", validate_health=False)
    app = create_app(server=server)
    return TestClient(app)


def test_handshake_matches_fixture() -> None:
    expected = _load_fixture("handshake_expected.json")
    client = _create_client()
    with client.websocket_connect("/mcp/ws") as websocket:
        websocket.send_json(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "conformance-suite", "version": "0.0.0"},
                },
            }
        )
        response = websocket.receive_json()

    result = response["result"]
    handshake_subset = {
        "protocolVersion": result["protocolVersion"],
        "capabilities": result["capabilities"],
        "serverInfo": {
            "name": result["serverInfo"]["name"],
            "title": result["serverInfo"]["title"],
        },
        "instructions": result["instructions"],
        "transport": result["transport"],
    }
    assert handshake_subset == expected
    assert "sessionId" in result
    assert isinstance(result["sessionId"], str)


def test_discovery_contains_required_contract() -> None:
    expected = _load_fixture("discovery_required.json")
    client = _create_client()
    with client.websocket_connect("/mcp/ws") as websocket:
        websocket.send_json(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-06-18", "capabilities": {}},
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
        assert tools_response["result"]["nextCursor"] is None
        tool_names = {tool["name"] for tool in tools_response["result"]["tools"]}
        for required in expected["requiredTools"]:
            assert required in tool_names

        websocket.send_json(
            {"jsonrpc": "2.0", "id": 3, "method": "resources/list", "params": {}}
        )
        resources_response = websocket.receive_json()
        resource_names = {
            resource["name"] for resource in resources_response["result"]["resources"]
        }
        for required in expected["requiredResources"]:
            assert required in resource_names
