from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple, Type

from pydantic import BaseModel

from epacomp_tox.resources.base import BaseResource
from epacomp_tox.contracts import load_schema
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
    response_schema_ref: Optional[Tuple[str, str]]


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
            response_schema_ref: Optional[Tuple[str, str]] = None

            schema_ref_def = tool.get("responseSchemaRef")
            if schema_ref_def:
                namespace = schema_ref_def["namespace"]
                schema_name = schema_ref_def["name"]
                response_schema_ref = (namespace, schema_name)
                output_schema = load_schema(namespace, schema_name)

            description = tool.get("description", "")
            parameters_model = create_model_from_schema(name, input_schema)
            combined_annotations = {"resource": resource.name}
            tool_annotations = tool.get("annotations") or {}
            combined_annotations.update(tool_annotations)
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
                response_schema_ref=response_schema_ref,
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
