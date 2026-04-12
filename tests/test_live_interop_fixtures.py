from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from epacomp_tox.contracts import validate_payload

ROOT_DIR = Path(__file__).resolve().parents[1]
CAPTURE_DIR = ROOT_DIR / "tests" / "golden" / "interop_live"
CAPTURE_MANIFEST_PATH = CAPTURE_DIR / "capture_manifest.json"
EXPECTED_SCHEMAS = {
    "assemble_comptox_evidence_pack": (
        "workflow",
        "comptox_evidence_pack.response.schema",
    ),
    "build_aop_linkage_summary": (
        "workflow",
        "aop_linkage_summary.response.schema",
    ),
    "build_pbpk_context_bundle": (
        "workflow",
        "pbpk_context_bundle.response.schema",
    ),
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_live_interop_capture_manifest_tracks_expected_tools() -> None:
    manifest = _load_json(CAPTURE_MANIFEST_PATH)

    assert manifest["captureVersion"] == 1
    assert [entry["tool"] for entry in manifest["fixtures"]] == [
        "assemble_comptox_evidence_pack",
        "build_aop_linkage_summary",
        "build_pbpk_context_bundle",
    ]


def test_live_interop_fixtures_validate_and_match_manifest_checksums() -> None:
    manifest = _load_json(CAPTURE_MANIFEST_PATH)

    for entry in manifest["fixtures"]:
        payload_path = CAPTURE_DIR / entry["file"]
        payload = _load_json(payload_path)
        validate_payload(
            payload,
            namespace=EXPECTED_SCHEMAS[entry["tool"]][0],
            name=EXPECTED_SCHEMAS[entry["tool"]][1],
        )
        assert entry["sha256"] == sha256(payload_path.read_bytes()).hexdigest()
