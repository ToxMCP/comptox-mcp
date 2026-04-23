from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Dict, Tuple

from jsonschema import Draft202012Validator

from epacomp_tox.assets import data_file


class SchemaValidationError(RuntimeError):
    """Raised when a payload fails JSON Schema validation."""


def _schema_resource(namespace: str, name: str) -> Any:
    return data_file("contracts", "schemas", namespace, f"{name}.json")


@lru_cache(maxsize=128)
def load_schema(namespace: str, name: str) -> Dict[str, Any]:
    """Load and cache a JSON Schema by namespace/name."""
    resource = _schema_resource(namespace, name)
    if not resource.is_file():
        raise FileNotFoundError(
            f"Schema '{namespace}/{name}' not found in package data"
        )
    return json.loads(resource.read_text(encoding="utf-8"))


def validate_payload(payload: Any, *, namespace: str, name: str) -> None:
    """Validate a payload against the referenced schema."""
    schema = load_schema(namespace, name)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda error: error.path)
    if errors:
        message = "; ".join(error.message for error in errors)
        raise SchemaValidationError(message)


def schema_ref(namespace: str, name: str) -> Dict[str, str]:
    """Helper to build a schema reference dictionary for tool definitions."""
    return {"namespace": namespace, "name": name}


__all__ = ["SchemaValidationError", "load_schema", "schema_ref", "validate_payload"]
