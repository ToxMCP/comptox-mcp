from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Type, Union

from pydantic import BaseModel, Field, create_model

try:
    from typing import Literal  # Python 3.8+
except ImportError:  # pragma: no cover - fallback for very old versions
    from typing_extensions import Literal  # type: ignore


JSONSchema = Dict[str, Any]


def _literal_from_enum(enum_values: List[Any]) -> Any:
    try:
        return Literal[tuple(enum_values)]  # type: ignore[misc]
    except TypeError:  # pragma: no cover - defensive
        return Any


def _schema_type_to_annotation(schema: JSONSchema) -> Any:
    if not isinstance(schema, dict):
        return Any

    if "enum" in schema and isinstance(schema["enum"], list) and schema["enum"]:
        return _literal_from_enum(schema["enum"])

    schema_type = schema.get("type")
    if isinstance(schema_type, list):  # union of types, fallback to Any
        return Any

    if schema_type == "string":
        return str
    if schema_type == "integer":
        return int
    if schema_type == "number":
        return float
    if schema_type == "boolean":
        return bool
    if schema_type == "array":
        item_schema = schema.get("items", {})
        item_annotation = _schema_type_to_annotation(item_schema)
        return List[item_annotation]  # type: ignore[list-item]
    if schema_type == "object":
        return Dict[str, Any]

    return Any


def create_model_from_schema(
    tool_name: str, schema: Optional[JSONSchema]
) -> Type[BaseModel]:
    schema = schema or {}
    if schema.get("type", "object") != "object":
        # Default to accepting any mapping
        return create_model(
            f"{tool_name.title()}Params",
            **{"__root__": (Dict[str, Any], Field(default_factory=dict))},
        )

    properties: Dict[str, JSONSchema] = schema.get("properties", {})
    required_fields = set(schema.get("required", []))
    fields: Dict[str, Tuple[Any, Field]] = {}

    for prop_name, prop_schema in properties.items():
        annotation = _schema_type_to_annotation(prop_schema)
        description = prop_schema.get("description")
        default = prop_schema.get("default")

        if prop_name in required_fields and default is None:
            field_info = Field(..., description=description)
        else:
            field_info = Field(
                default if default is not None else None, description=description
            )

        fields[prop_name] = (annotation, field_info)

    model_name = "".join(part.capitalize() for part in tool_name.split("_")) or "Tool"
    return create_model(f"{model_name}Params", **fields)
