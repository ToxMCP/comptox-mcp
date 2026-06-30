from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

from jsonschema import Draft202012Validator


def _default_schema_root() -> Path:
    override = os.getenv("EPACOMP_TOX_CONTRACT_SCHEMA_ROOT")
    if override:
        return Path(override)

    repo_relative = (
        Path(__file__).resolve().parents[3] / "docs" / "contracts" / "schemas"
    )
    if repo_relative.exists():
        return repo_relative

    return Path.cwd() / "docs" / "contracts" / "schemas"


SCHEMA_ROOT = _default_schema_root()


class SchemaValidationError(RuntimeError):
    """Raised when a payload fails JSON Schema validation."""


def _schema_path(namespace: str, name: str) -> Path:
    return SCHEMA_ROOT / namespace / f"{name}.json"


@lru_cache(maxsize=128)
def load_schema(namespace: str, name: str) -> Dict[str, Any]:
    """Load and cache a JSON Schema by namespace/name."""
    path = _schema_path(namespace, name)
    if not path.exists():
        raise FileNotFoundError(f"Schema '{namespace}/{name}' not found at {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


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
