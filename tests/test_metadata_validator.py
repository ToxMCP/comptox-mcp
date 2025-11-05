from __future__ import annotations

import json
from pathlib import Path

import pytest

from epacomp_tox.metadata.validator import (
    MetadataValidationError,
    validate_all,
    validate_applicability_domains,
    validate_model_cards,
)


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload))


def test_validate_model_cards_success(tmp_path: Path) -> None:
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["name"],
        "properties": {"name": {"type": "string"}}
    }
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps(schema))

    cards_dir = tmp_path / "cards"
    cards_dir.mkdir()
    _write(cards_dir / "card.json", {"name": "Model"})

    validate_model_cards(cards_dir=cards_dir, schema_path=schema_path)


def test_validate_model_cards_failure(tmp_path: Path) -> None:
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["name"],
        "properties": {"name": {"type": "string"}}
    }
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps(schema))

    cards_dir = tmp_path / "cards"
    cards_dir.mkdir()
    _write(cards_dir / "card.json", {"title": "Missing name"})

    with pytest.raises(MetadataValidationError):
        validate_model_cards(cards_dir=cards_dir, schema_path=schema_path)


def test_validate_applicability_domains_failure(tmp_path: Path) -> None:
    ad_dir = tmp_path / "ad"
    ad_dir.mkdir()
    _write(ad_dir / "invalid.json", {"model": "A"})

    with pytest.raises(MetadataValidationError):
        validate_applicability_domains(directory=ad_dir)
