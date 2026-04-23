from __future__ import annotations

import logging
from typing import Any, Dict, List

from epacomp_tox.resources.base import BaseResource
from epacomp_tox.tools.registry import ToolRegistry


class ArrayOutputResource(BaseResource):
    @property
    def name(self) -> str:
        return "array-output"

    @property
    def description(self) -> str:
        return "Resource used to verify output schema wrapping."

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "list_values",
                "description": "Return array data.",
                "inputSchema": {"type": "object", "properties": {}},
                "outputSchema": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            }
        ]

    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        raise NotImplementedError


def test_registry_wraps_non_object_output_schema_without_warning_log(
    caplog,
) -> None:
    registry = ToolRegistry()
    resource = ArrayOutputResource(api_key="fake")

    with caplog.at_level(logging.WARNING):
        registry.register_resource(resource)

    definition = registry.list_definitions()[0]
    output_schema = definition["outputSchema"]
    assert output_schema["type"] == "object"
    assert output_schema["required"] == ["data"]
    assert output_schema["properties"]["data"] == {
        "type": "array",
        "items": {"type": "string"},
    }
    assert output_schema["properties"]["metadata"]["additionalProperties"] is True
    assert output_schema["properties"]["mcpMetadata"]["additionalProperties"] is True
    assert not caplog.records
