from __future__ import annotations

from typing import Any, Dict, List

from jsonschema import Draft202012Validator

from ctxpy import CtxApiError
from epacomp_tox.resources.base import BaseResource
from epacomp_tox.server import COMPTOX_API_KEY_URL, COMPTOX_SOURCE_URL, MCPServer


class ContractResource(BaseResource):
    @property
    def name(self) -> str:
        return "contract"

    @property
    def description(self) -> str:
        return "Tool-result contract fixture"

    def get_tools(self) -> List[Dict[str, Any]]:
        object_schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
        }
        return [
            {
                "name": "object_result",
                "description": "Return an object.",
                "inputSchema": {"type": "object", "properties": {}},
                "outputSchema": object_schema,
            },
            {
                "name": "list_result",
                "description": "Return a list.",
                "inputSchema": {"type": "object", "properties": {}},
                "outputSchema": {"type": "array", "items": {"type": "string"}},
            },
            {
                "name": "auth_error",
                "description": "Raise an upstream authentication error.",
                "inputSchema": {"type": "object", "properties": {}},
                "outputSchema": object_schema,
            },
        ]

    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        self._last_metadata = {"resource": self.name}
        self._last_provenance = {"retrieved_at": "2026-07-22T00:00:00+00:00"}
        if tool_name == "object_result":
            return {"value": "ok"}
        if tool_name == "list_result":
            return []
        if tool_name == "auth_error":
            raise CtxApiError(401, "upstream secret detail", detail={"secret": True})
        raise ValueError(f"Unknown tool: {tool_name}")


class ContractServer(MCPServer):
    def _initialize_resources(self) -> Dict[str, BaseResource]:
        return {"contract": ContractResource(api_key="dummy")}


def _server() -> ContractServer:
    return ContractServer(api_key="dummy", validate_health=False)


def test_object_structured_content_matches_advertised_schema() -> None:
    server = _server()
    result = server.call_tool("object_result", {}, context={"sessionId": "session-1"})
    schema = server.tool_registry.get_registration("object_result").output_schema

    assert result["structuredContent"] == {"value": "ok"}
    assert result["_meta"]["resource"] == "contract"
    assert result["_meta"]["session"]["sessionId"] == "session-1"
    assert result["_meta"]["provenance"]["retrieved_at"].startswith("2026-07-22")
    Draft202012Validator(schema).validate(result["structuredContent"])


def test_empty_list_uses_registry_data_envelope() -> None:
    server = _server()
    result = server.call_tool("list_result", {})
    schema = server.tool_registry.get_registration("list_result").output_schema

    assert result["structuredContent"] == {"data": []}
    Draft202012Validator(schema).validate(result["structuredContent"])


def test_authentication_errors_are_actionable_and_not_schema_payloads() -> None:
    result = _server().call_tool("auth_error", {})

    assert result["isError"] is True
    assert "structuredContent" not in result
    assert result["_meta"]["error"]["code"] == "comptox_authentication_failed"
    assert result["_meta"]["error"]["status"] == 401
    assert COMPTOX_API_KEY_URL in result["content"][0]["text"]
    assert "upstream secret detail" not in result["content"][0]["text"]


def test_chemical_renderers_expose_results_and_source() -> None:
    search_text = MCPServer._render_tool_content(
        "search_chemical",
        [
            {
                "preferredName": "Bisphenol A",
                "dtxsid": "DTXSID7020182",
                "casrn": "80-05-7",
            }
        ],
    )
    resolve_text = MCPServer._render_tool_content(
        "resolve_chemical_identifier",
        {
            "status": "resolved",
            "inputIdentifier": "80-05-7",
            "preferredName": "Bisphenol A",
            "canonicalDtxsid": "DTXSID7020182",
            "casrn": "80-05-7",
            "candidateCount": 1,
            "warnings": [],
        },
    )

    for text in (search_text, resolve_text):
        assert "Bisphenol A" in text
        assert "DTXSID7020182" in text
        assert COMPTOX_SOURCE_URL in text
        assert "Successfully retrieved structured data" not in text
