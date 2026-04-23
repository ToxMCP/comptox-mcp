from __future__ import annotations

import logging
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple, Type

from jsonschema import Draft202012Validator
from pydantic import BaseModel

from epacomp_tox.contracts import load_schema
from epacomp_tox.resources.base import BaseResource
from epacomp_tox.tools.schema import create_model_from_schema

logger = logging.getLogger(__name__)


@dataclass
class ToolRegistration:
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Optional[Dict[str, Any]]
    resource: BaseResource
    parameters_model: Type[BaseModel]
    input_validator: Draft202012Validator
    output_validator: Optional[Draft202012Validator]
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
        wrapped_tools: List[str] = []
        for tool in resource.get_tools():
            name = tool["name"]
            if name in self._tools:
                raise ValueError(f"Tool '{name}' already registered.")

            input_schema = (
                tool.get("inputSchema") or tool.get("parameters") or {"type": "object"}
            )
            input_schema = _normalise_input_schema(input_schema)
            output_schema = tool.get("outputSchema")
            response_schema_ref: Optional[Tuple[str, str]] = None

            schema_ref_def = tool.get("responseSchemaRef")
            if schema_ref_def:
                namespace = schema_ref_def["namespace"]
                schema_name = schema_ref_def["name"]
                response_schema_ref = (namespace, schema_name)
                # Only load if not already present (e.g. from resource-level override)
                if not output_schema:
                    output_schema = load_schema(namespace, schema_name)

            if output_schema and output_schema.get("type") != "object":
                # Wrap non-object schemas (e.g. arrays) in a standard envelope to match server behavior
                # and satisfy MCP/Gemini requirements for tool output schemas.
                wrapped_tools.append(name)
                output_schema = {
                    "type": "object",
                    "properties": {"data": output_schema},
                    "required": ["data"],
                }
            if output_schema:
                output_schema = _normalise_output_schema(output_schema)

            description = tool.get("description", "")
            parameters_model = create_model_from_schema(name, input_schema)
            combined_annotations = {"resource": resource.name}
            tool_annotations = tool.get("annotations") or {}
            combined_annotations.update(tool_annotations)
            if annotations:
                combined_annotations.update(annotations)
            combined_annotations.setdefault("readOnlyHint", True)
            combined_annotations.setdefault("destructiveHint", False)
            combined_annotations.setdefault("openWorldHint", True)
            combined_annotations.setdefault("idempotentHint", True)

            self._tools[name] = ToolRegistration(
                name=name,
                description=description,
                input_schema=input_schema,
                output_schema=output_schema,
                resource=resource,
                parameters_model=parameters_model,
                input_validator=Draft202012Validator(input_schema),
                output_validator=(
                    Draft202012Validator(output_schema) if output_schema else None
                ),
                annotations=combined_annotations,
                response_schema_ref=response_schema_ref,
            )

        if wrapped_tools:
            logger.debug(
                "Wrapped non-object output schemas for resource '%s': %s",
                resource.name,
                ", ".join(sorted(wrapped_tools)),
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


def _normalise_input_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    normalised = deepcopy(schema or {"type": "object"})
    if normalised.get("type", "object") == "object":
        normalised.setdefault("properties", {})
        normalised.setdefault("additionalProperties", False)
    return normalised


def _normalise_output_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    normalised = deepcopy(schema)
    if normalised.get("type") != "object":
        return normalised
    properties = normalised.setdefault("properties", {})
    metadata_schema = {"type": "object", "additionalProperties": True}
    properties.setdefault("metadata", metadata_schema)
    properties.setdefault("mcpMetadata", metadata_schema)
    properties.setdefault(
        "data",
        {
            "type": [
                "object",
                "array",
                "string",
                "number",
                "integer",
                "boolean",
                "null",
            ],
            "additionalProperties": True,
        },
    )
    return normalised
