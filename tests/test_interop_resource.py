import pytest

from epacomp_tox.resources.interop import InteropResource
from tests.interop_test_support import build_interop_resource, validate_portable_schema


@pytest.fixture
def interop_resource() -> InteropResource:
    return build_interop_resource()


def test_build_aop_linkage_summary_validates_portable_schema(
    interop_resource: InteropResource,
) -> None:
    result = interop_resource.execute_tool(
        "build_aop_linkage_summary",
        {"dtxsid": "DTXSID7020182", "max_assays": 5},
    )

    validate_portable_schema("aopLinkageSummary.v1.json", result)
    assert result["lookupMode"] == "dtxsid"
    assert result["mappings"][0]["aopId"] == "AOP:42"


def test_build_pbpk_context_bundle_validates_portable_schema(
    interop_resource: InteropResource,
) -> None:
    result = interop_resource.execute_tool(
        "build_pbpk_context_bundle",
        {"dtxsid": "DTXSID7020182"},
    )

    validate_portable_schema("pbpkContextBundle.v1.json", result)
    assert result["handoffTarget"] == "pbpk-mcp"
    assert result["modelCardRefs"] == [
        {
            "modelName": "HTTK PBPK Surrogate",
            "modelVersion": "1.0",
            "endpoint": "internal dose metrics",
        }
    ]


def test_assemble_comptox_evidence_pack_validates_portable_schema(
    interop_resource: InteropResource,
) -> None:
    result = interop_resource.execute_tool(
        "assemble_comptox_evidence_pack",
        {
            "dtxsid": "DTXSID7020182",
            "hazard_datasets": ["toxval", "adme_ivive"],
            "max_assays": 5,
        },
    )

    validate_portable_schema("comptoxEvidencePack.v1.json", result)
    assert result["metadata"]["suiteRole"] == "evidence-federation"
    assert result["semanticCoverage"]["aopLinkage"] == "linked"
