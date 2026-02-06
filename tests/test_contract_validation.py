import unittest
from typing import Any, Dict, List
from unittest import mock

from epacomp_tox.contracts import SchemaValidationError
from epacomp_tox.resources.base import BaseResource
from epacomp_tox.server import MCPServer


class DummyResource(BaseResource):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.payload: Any = [{"ok": True}]

    @property
    def name(self) -> str:
        return "dummy"

    @property
    def description(self) -> str:
        return "Dummy resource for contract validation tests."

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "dummy_tool",
                "description": "Returns a payload validated against the hazard list schema.",
                "parameters": {"type": "object"},
                "responseSchemaRef": {
                    "namespace": "common",
                    "name": "list_generic.response.schema",
                },
            }
        ]

    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        if tool_name != "dummy_tool":
            raise ValueError(tool_name)
        return self.payload


def _fake_init_resources(self: MCPServer) -> Dict[str, BaseResource]:
    return {"dummy": DummyResource(self.api_key)}


class TestContractValidation(unittest.TestCase):
    @mock.patch.object(MCPServer, "_initialize_resources", new=_fake_init_resources)
    @mock.patch("epacomp_tox.server.configure_ctx_env")
    @mock.patch("epacomp_tox.server.get_base_url", return_value="https://example.test")
    @mock.patch("epacomp_tox.server.get_api_key", return_value="fake-key")
    def test_execute_tool_valid_payload(self, *_: mock.MagicMock) -> None:
        server = MCPServer()
        resource = server.resources["dummy"]
        resource.payload = [{"id": 1}]

        result = server.execute_tool("dummy_tool", {})
        self.assertEqual(result, [{"id": 1}])

    @mock.patch.object(MCPServer, "_initialize_resources", new=_fake_init_resources)
    @mock.patch("epacomp_tox.server.configure_ctx_env")
    @mock.patch("epacomp_tox.server.get_base_url", return_value="https://example.test")
    @mock.patch("epacomp_tox.server.get_api_key", return_value="fake-key")
    def test_execute_tool_invalid_payload_raises(self, *_: mock.MagicMock) -> None:
        server = MCPServer()
        resource = server.resources["dummy"]
        resource.payload = {"unexpected": True}

        with self.assertRaises(SchemaValidationError):
            server.execute_tool("dummy_tool", {})
