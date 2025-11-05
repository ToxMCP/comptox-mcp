#!/usr/bin/env python3
"""Validate CompTox model metadata and applicability domain reference files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from epacomp_tox.metadata.validator import (
    DEFAULT_AD_DIR,
    DEFAULT_CARDS_DIR,
    DEFAULT_SCHEMA_PATH,
    MetadataValidationError,
    validate_applicability_domains,
    validate_model_cards,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cards-dir",
        type=Path,
        default=DEFAULT_CARDS_DIR,
        help="Directory containing model card JSON files",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=DEFAULT_SCHEMA_PATH,
        help="Path to CompTox model card JSON schema",
    )
    parser.add_argument(
        "--ad-dir",
        type=Path,
        default=DEFAULT_AD_DIR,
        help="Directory containing applicability domain definitions",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        validate_model_cards(cards_dir=args.cards_dir, schema_path=args.schema)
        validate_applicability_domains(directory=args.ad_dir)
    except MetadataValidationError as exc:
        print("Validation failed:\n" + str(exc), file=sys.stderr)
        return 1
    print("Metadata validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
