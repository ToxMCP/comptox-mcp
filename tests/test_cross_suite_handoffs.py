from __future__ import annotations

import json
from pathlib import Path

from tests.interop_test_support import (
    build_interop_resource,
    sanitize_aop_handoff,
    sanitize_pbpk_handoff,
    validate_portable_schema,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "cross_suite"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def test_comptox_to_aop_handoff_matches_fixture() -> None:
    interop = build_interop_resource()
    result = interop.execute_tool(
        "build_aop_linkage_summary",
        {"dtxsid": "DTXSID7020182", "max_assays": 5},
    )

    validate_portable_schema("aopLinkageSummary.v1.json", result)
    assert sanitize_aop_handoff(result) == _load_fixture("comptox_to_aop_handoff.json")


def test_comptox_to_pbpk_handoff_matches_fixture() -> None:
    interop = build_interop_resource()
    result = interop.execute_tool(
        "build_pbpk_context_bundle",
        {"dtxsid": "DTXSID7020182"},
    )

    validate_portable_schema("pbpkContextBundle.v1.json", result)
    assert sanitize_pbpk_handoff(result) == _load_fixture(
        "comptox_to_pbpk_handoff.json"
    )
