from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Type

from pydantic import BaseModel

from epacomp_tox.resources.base import BaseResource
from epacomp_tox.tools.schema import create_model_from_schema


@dataclass
class ToolRegistration:
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Optional[Dict[str, Any]]
    resource: BaseResource
    parameters_model: Type[BaseModel]
    annotations: Dict[str, Any]


class ToolRegistry:
    """Registry that manages MCP tool definitions and validation."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolRegistration] = {}

    def register_resource(
        self,
        resource: BaseResource,
        *,
        annotations: Optional[Dict[str, Any]] = None,
    ) -> None:
        for tool in resource.get_tools():
            name = tool["name"]
            if name in self._tools:
                raise ValueError(f"Tool '{name}' already registered.")

            input_schema = tool.get("inputSchema") or tool.get("parameters") or {"type": "object"}
            output_schema = tool.get("outputSchema")
            description = tool.get("description", "")
            parameters_model = create_model_from_schema(name, input_schema)
            combined_annotations = {"resource": resource.name}
            if annotations:
                combined_annotations.update(annotations)

            self._tools[name] = ToolRegistration(
                name=name,
                description=description,
                input_schema=input_schema,
                output_schema=output_schema,
                resource=resource,
                parameters_model=parameters_model,
                annotations=combined_annotations,
            )

    def get_registration(self, name: str) -> ToolRegistration:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"Tool '{name}' is not registered.") from exc

    def list_definitions(self) -> List[Dict[str, Any]]:
        definitions: List[Dict[str, Any]] = []
        for registration in self._tools.values():
            definition = {
                "name": registration.name,
                "title": registration.name,
                "description": registration.description,
                "inputSchema": registration.input_schema,
                "annotations": registration.annotations,
            }
            if registration.output_schema:
                definition["outputSchema"] = registration.output_schema
            definitions.append(definition)
        return definitions

    def __iter__(self) -> Iterable[ToolRegistration]:
        return iter(self._tools.values())

