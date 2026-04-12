from __future__ import annotations

from pathlib import Path

from epacomp_tox.contracts import validate_payload
from epacomp_tox.server import MCPServer

ROOT_DIR = Path(__file__).resolve().parents[1]


def test_contract_manifest_validates_and_matches_live_catalog() -> None:
    server = MCPServer(api_key="dummy", validate_health=False)

    result = server.execute_tool("get_contract_manifest", {})
    validate_payload(
        result,
        namespace="manifest",
        name="get_contract_manifest.response.schema",
    )

    live_resource_names = list(server.resources.keys())
    live_tool_names = sorted(tool["name"] for tool in server.get_tools())

    assert [item["name"] for item in result["resources"]] == live_resource_names
    assert [item["name"] for item in result["tools"]] == live_tool_names
    assert result["server"]["resourceCount"] == len(live_resource_names)
    assert result["server"]["toolCount"] == len(live_tool_names)
    assert result["publicBoundary"]["experimentalModules"] == [
        "predictive",
        "orchestrator",
    ]


def test_contract_manifest_tracks_schema_files_and_examples() -> None:
    server = MCPServer(api_key="dummy", validate_health=False)
    result = server.execute_tool("get_contract_manifest", {})

    portable_files = sorted(
        f"schemas/{path.name}" for path in (ROOT_DIR / "schemas").glob("*.json")
    )
    response_schema_paths = sorted(
        str(path.relative_to(ROOT_DIR))
        for path in (ROOT_DIR / "docs" / "contracts" / "schemas").glob("*/*.json")
    )

    assert sorted(item["file"] for item in result["portableObjectSchemas"]) == portable_files
    assert sorted(item["path"] for item in result["responseSchemas"]) == response_schema_paths

    interop_refs = result["publicContractReferences"]["interop"]
    assert {item["toolName"] for item in interop_refs} == {
        "assemble_comptox_evidence_pack",
        "build_aop_linkage_summary",
        "build_pbpk_context_bundle",
    }
    prioritization_refs = result["publicContractReferences"][
        "screeningPrioritization"
    ]
    assert prioritization_refs == [
        {
            "toolName": "prioritize_risk_signals",
            "responseSchemaRef": {
                "namespace": "risk",
                "name": "prioritize_risk_signals.response.schema",
            },
        }
    ]
