from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from epacomp_tox.resources.bioactivity import BioactivityResource
from epacomp_tox.resources.chemical import ChemicalResource
from epacomp_tox.resources.exposure import ExposureResource
from epacomp_tox.resources.hazard import HazardResource
from epacomp_tox.resources.interop import InteropResource
from epacomp_tox.resources.manifest import ContractManifestResource
from epacomp_tox.resources.prioritization import PrioritizationResource

SCHEMA_PATHS = [
    Path(
        "docs/contracts/schemas/chemical/resolve_chemical_identifier.response.schema.json"
    ),
    Path("docs/contracts/schemas/hazard/search_hazard.response.schema.json"),
    Path("docs/contracts/schemas/hazard/batch_search_hazard.response.schema.json"),
    Path("docs/contracts/schemas/exposure/search_cpdat.response.schema.json"),
    Path("docs/contracts/schemas/exposure/search_httk.response.schema.json"),
    Path("docs/contracts/schemas/exposure/get_exposure_httk.response.schema.json"),
    Path(
        "docs/contracts/schemas/bioactivity/search_bioactivity_terms.response.schema.json"
    ),
    Path(
        "docs/contracts/schemas/bioactivity/get_bioactivity_summary_by_dtxsid.response.schema.json"
    ),
    Path(
        "docs/contracts/schemas/bioactivity/get_bioactivity_assay.response.schema.json"
    ),
    Path("docs/contracts/schemas/bioactivity/get_bioactivity_aop.response.schema.json"),
    Path("docs/contracts/schemas/workflow/aop_linkage_summary.response.schema.json"),
    Path("docs/contracts/schemas/workflow/pbpk_context_bundle.response.schema.json"),
    Path("docs/contracts/schemas/workflow/comptox_evidence_pack.response.schema.json"),
    Path("docs/contracts/schemas/risk/prioritize_risk_signals.response.schema.json"),
    Path("docs/contracts/schemas/manifest/get_contract_manifest.response.schema.json"),
]


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _tool_map(resource) -> dict[str, dict]:
    return {tool["name"]: tool for tool in resource.get_tools()}


def test_domain_response_schemas_are_valid() -> None:
    for path in SCHEMA_PATHS:
        Draft202012Validator.check_schema(_load_json(path))


def test_hazard_tools_use_domain_specific_response_schemas() -> None:
    tools = _tool_map(HazardResource(api_key="fake"))
    assert tools["search_hazard"]["responseSchemaRef"] == {
        "namespace": "hazard",
        "name": "search_hazard.response.schema",
    }
    assert tools["batch_search_hazard"]["responseSchemaRef"] == {
        "namespace": "hazard",
        "name": "batch_search_hazard.response.schema",
    }


def test_chemical_tools_use_domain_specific_response_schemas() -> None:
    tools = _tool_map(ChemicalResource(api_key="fake"))
    assert tools["resolve_chemical_identifier"]["responseSchemaRef"] == {
        "namespace": "chemical",
        "name": "resolve_chemical_identifier.response.schema",
    }


def test_exposure_tools_use_domain_specific_response_schemas() -> None:
    tools = _tool_map(ExposureResource(api_key="fake"))
    assert tools["search_cpdat"]["responseSchemaRef"] == {
        "namespace": "exposure",
        "name": "search_cpdat.response.schema",
    }
    assert tools["search_httk"]["responseSchemaRef"] == {
        "namespace": "exposure",
        "name": "search_httk.response.schema",
    }
    assert tools["get_exposure_httk"]["responseSchemaRef"] == {
        "namespace": "exposure",
        "name": "get_exposure_httk.response.schema",
    }


def test_bioactivity_tools_use_domain_specific_response_schemas() -> None:
    tools = _tool_map(BioactivityResource(api_key="fake"))
    assert tools["search_bioactivity_terms"]["responseSchemaRef"] == {
        "namespace": "bioactivity",
        "name": "search_bioactivity_terms.response.schema",
    }
    assert tools["get_bioactivity_summary_by_dtxsid"]["responseSchemaRef"] == {
        "namespace": "bioactivity",
        "name": "get_bioactivity_summary_by_dtxsid.response.schema",
    }
    assert tools["get_bioactivity_assay"]["responseSchemaRef"] == {
        "namespace": "bioactivity",
        "name": "get_bioactivity_assay.response.schema",
    }
    assert tools["get_bioactivity_aop"]["responseSchemaRef"] == {
        "namespace": "bioactivity",
        "name": "get_bioactivity_aop.response.schema",
    }


def test_workflow_tools_use_domain_specific_response_schemas() -> None:
    tools = _tool_map(InteropResource(api_key="fake"))
    assert tools["assemble_comptox_evidence_pack"]["responseSchemaRef"] == {
        "namespace": "workflow",
        "name": "comptox_evidence_pack.response.schema",
    }
    assert tools["build_aop_linkage_summary"]["responseSchemaRef"] == {
        "namespace": "workflow",
        "name": "aop_linkage_summary.response.schema",
    }
    assert tools["build_pbpk_context_bundle"]["responseSchemaRef"] == {
        "namespace": "workflow",
        "name": "pbpk_context_bundle.response.schema",
    }


def test_risk_tools_use_domain_specific_response_schemas() -> None:
    tools = _tool_map(PrioritizationResource(api_key="fake"))
    assert tools["prioritize_risk_signals"]["responseSchemaRef"] == {
        "namespace": "risk",
        "name": "prioritize_risk_signals.response.schema",
    }


def test_manifest_tools_use_domain_specific_response_schemas() -> None:
    tools = _tool_map(
        ContractManifestResource(api_key="fake", server_getter=lambda: None)
    )
    assert tools["get_contract_manifest"]["responseSchemaRef"] == {
        "namespace": "manifest",
        "name": "get_contract_manifest.response.schema",
    }
