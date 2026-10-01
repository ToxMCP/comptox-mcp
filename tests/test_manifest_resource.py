from __future__ import annotations

import shutil
from pathlib import Path

from epacomp_tox.contracts import validate_payload
from epacomp_tox.resources import manifest
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

    assert (
        sorted(item["file"] for item in result["portableObjectSchemas"])
        == portable_files
    )
    assert (
        sorted(item["path"] for item in result["responseSchemas"])
        == response_schema_paths
    )

    interop_refs = result["publicContractReferences"]["interop"]
    assert {item["toolName"] for item in interop_refs} == {
        "assemble_comptox_evidence_pack",
        "build_aop_linkage_summary",
        "build_pbpk_context_bundle",
    }
    prioritization_refs = result["publicContractReferences"]["screeningPrioritization"]
    assert prioritization_refs == [
        {
            "toolName": "prioritize_risk_signals",
            "responseSchemaRef": {
                "namespace": "risk",
                "name": "prioritize_risk_signals.response.schema",
            },
        }
    ]


def test_manifest_inventories_installed_schema_bundles_without_a_checkout(
    monkeypatch, tmp_path: Path
) -> None:
    installed_data = tmp_path / "installed-data"
    package_data = installed_data / "share" / "epacomp-tox-mcp"
    responses = package_data / "contracts" / "schemas"
    portable = package_data / "portable" / "schemas"
    shutil.copytree(ROOT_DIR / "docs" / "contracts" / "schemas", responses)
    shutil.copytree(ROOT_DIR / "schemas", portable)
    missing_source = tmp_path / "missing-source" / "src" / "epacomp_tox" / "resources"
    monkeypatch.setattr(manifest, "__file__", str(missing_source / "manifest.py"))
    monkeypatch.setattr(manifest, "SCHEMA_ROOT", responses)
    monkeypatch.setattr(
        manifest.sysconfig, "get_path", lambda _name: str(installed_data)
    )

    server = MCPServer(api_key="dummy", validate_health=False)
    result = server.execute_tool("get_contract_manifest", {})

    assert len(result["responseSchemas"]) == len(list(responses.glob("*/*.json"))) > 0
    assert (
        len(result["portableObjectSchemas"]) == len(list(portable.glob("*.json"))) > 0
    )
    # Seven evidence objects have examples; the existing model-card schema does not.
    assert sum("exampleFile" in item for item in result["portableObjectSchemas"]) == 7
    assert all(
        item["path"].startswith("docs/contracts/schemas/")
        for item in result["responseSchemas"]
    )
    assert all(
        item["exampleFile"].startswith("schemas/examples/")
        for item in result["portableObjectSchemas"]
        if "exampleFile" in item
    )
    validate_payload(
        result,
        namespace="manifest",
        name="get_contract_manifest.response.schema",
    )
