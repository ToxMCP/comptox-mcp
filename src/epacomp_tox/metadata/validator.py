from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List

from jsonschema import validate, ValidationError

DEFAULT_SCHEMA_PATH = Path("schemas/comptox_model_card.schema.json")
DEFAULT_CARDS_DIR = Path("metadata/model_cards")
DEFAULT_AD_DIR = Path("metadata/applicability_domains")


class MetadataValidationError(Exception):
    """Raised when metadata validation fails."""


def validate_model_cards(
    *,
    cards_dir: Path = DEFAULT_CARDS_DIR,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors: List[str] = []
    for path in sorted(cards_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            validate(instance=payload, schema=schema)
        except (ValidationError, json.JSONDecodeError) as exc:
            errors.append(f"{path}: {exc}")
    if errors:
        raise MetadataValidationError("\n".join(errors))


def validate_applicability_domains(
    *, directory: Path = DEFAULT_AD_DIR
) -> None:
    required_fields = {"model", "version", "criteria", "policy"}
    errors: List[str] = []
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{path}: invalid JSON: {exc}")
            continue
        missing = required_fields - set(payload.keys())
        if missing:
            errors.append(f"{path}: missing fields {sorted(missing)}")
        if not isinstance(payload.get("criteria"), list):
            errors.append(f"{path}: 'criteria' must be a list")
    if errors:
        raise MetadataValidationError("\n".join(errors))


def validate_all() -> None:
    validate_model_cards()
    validate_applicability_domains()
