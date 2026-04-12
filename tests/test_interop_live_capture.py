from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from epacomp_tox.contracts import validate_payload
from epacomp_tox.interop_live import SmokeError, SmokeRunArtifacts, write_capture_bundle
from tests.interop_test_support import build_interop_resource


def _build_artifacts() -> SmokeRunArtifacts:
    interop = build_interop_resource()
    tool_arguments = {
        "build_aop_linkage_summary": {
            "identifier": "80-05-7",
            "identifier_type": "casrn",
            "max_assays": 5,
        },
        "build_pbpk_context_bundle": {"dtxsid": "DTXSID7020182"},
        "assemble_comptox_evidence_pack": {
            "dtxsid": "DTXSID7020182",
            "hazard_datasets": ["toxval", "adme_ivive"],
            "max_assays": 5,
        },
    }
    payloads = {
        tool_name: interop.execute_tool(tool_name, arguments)
        for tool_name, arguments in tool_arguments.items()
    }
    return SmokeRunArtifacts(
        summary={
            "endpoint": "http://127.0.0.1:8000/mcp",
            "protocolVersion": "2025-06-18",
            "chemical": {
                "label": "Bisphenol A",
                "dtxsid": "DTXSID7020182",
            },
            "toolCount": 3,
            "resourceCount": 1,
        },
        payloads=payloads,
        tool_arguments=tool_arguments,
    )


def test_write_capture_bundle_writes_schema_validated_live_fixture_bundle(
    tmp_path: Path,
) -> None:
    artifacts = _build_artifacts()

    manifest = write_capture_bundle(
        artifacts,
        capture_dir=tmp_path / "interop_live",
        refresh=False,
    )

    capture_dir = tmp_path / "interop_live"
    assert (capture_dir / "capture_manifest.json").exists()
    assert [entry["tool"] for entry in manifest["fixtures"]] == [
        "assemble_comptox_evidence_pack",
        "build_aop_linkage_summary",
        "build_pbpk_context_bundle",
    ]

    expected_schemas = {
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
    for entry in manifest["fixtures"]:
        payload_path = capture_dir / entry["file"]
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        validate_payload(
            payload,
            namespace=expected_schemas[entry["tool"]][0],
            name=expected_schemas[entry["tool"]][1],
        )
        assert entry["sha256"] == sha256(payload_path.read_bytes()).hexdigest()


def test_write_capture_bundle_requires_explicit_refresh_to_overwrite(
    tmp_path: Path,
) -> None:
    artifacts = _build_artifacts()
    capture_dir = tmp_path / "interop_live"

    write_capture_bundle(artifacts, capture_dir=capture_dir, refresh=False)

    with pytest.raises(SmokeError, match="--refresh-live-fixtures"):
        write_capture_bundle(artifacts, capture_dir=capture_dir, refresh=False)

    write_capture_bundle(artifacts, capture_dir=capture_dir, refresh=True)


def test_write_capture_bundle_rejects_invalid_payload_before_writing(
    tmp_path: Path,
) -> None:
    artifacts = _build_artifacts()
    invalid_payloads = dict(artifacts.payloads)
    invalid_payload = dict(invalid_payloads["build_aop_linkage_summary"])
    invalid_payload.pop("provenance")
    invalid_payloads["build_aop_linkage_summary"] = invalid_payload
    broken = SmokeRunArtifacts(
        summary=artifacts.summary,
        payloads=invalid_payloads,
        tool_arguments=artifacts.tool_arguments,
    )

    with pytest.raises(SmokeError):
        write_capture_bundle(broken, capture_dir=tmp_path / "interop_live")

    assert not (tmp_path / "interop_live" / "capture_manifest.json").exists()
