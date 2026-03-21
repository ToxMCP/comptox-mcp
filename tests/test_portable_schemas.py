from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

SCHEMAS_DIR = Path(__file__).resolve().parents[1] / "schemas"
EXAMPLES_DIR = SCHEMAS_DIR / "examples"


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def _schema_registry() -> Registry:
    registry = Registry()
    for path in sorted(SCHEMAS_DIR.glob("*.json")):
        schema = _load_json(path)
        schema_id = schema.get("$id")
        if schema_id:
            registry = registry.with_resource(schema_id, Resource.from_contents(schema))
    return registry


def _schema_for_example(example_path: Path) -> Path:
    base_name = example_path.name.replace(".example.json", ".v1.json")
    return SCHEMAS_DIR / base_name


SCHEMA_PATHS = tuple(sorted(SCHEMAS_DIR.glob("*.json")))
EXAMPLE_PATHS = tuple(sorted(EXAMPLES_DIR.glob("*.example.json")))


@pytest.mark.parametrize("schema_path", SCHEMA_PATHS, ids=lambda path: path.name)
def test_portable_schemas_are_valid(schema_path: Path) -> None:
    schema = _load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, registry=_schema_registry())


@pytest.mark.parametrize("example_path", EXAMPLE_PATHS, ids=lambda path: path.name)
def test_portable_schema_examples_validate(example_path: Path) -> None:
    schema_path = _schema_for_example(example_path)
    assert schema_path.exists(), f"Missing schema for example {example_path.name}"

    schema = _load_json(schema_path)
    instance = _load_json(example_path)
    validator = Draft202012Validator(schema, registry=_schema_registry())
    validator.validate(instance)
