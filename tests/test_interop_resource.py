import pytest

from ctxpy import CtxApiError
from epacomp_tox.resources.interop import InteropResource
from tests.interop_test_support import (
    StubBioactivityResource,
    StubChemicalResource,
    StubExposureResource,
    StubHazardResource,
    StubMetadataResource,
    build_interop_resource,
    validate_portable_schema,
)


@pytest.fixture
def interop_resource() -> InteropResource:
    return build_interop_resource()


def test_build_aop_linkage_summary_validates_portable_schema(
    interop_resource: InteropResource,
) -> None:
    result = interop_resource.execute_tool(
        "build_aop_linkage_summary",
        {"identifier": "80-05-7", "identifier_type": "casrn", "max_assays": 5},
    )

    validate_portable_schema("aopLinkageSummary.v1.json", result)
    assert result["lookupMode"] == "dtxsid"
    assert result["mappings"][0]["aopId"] == "AOP:42"
    assert result["identityResolution"]["canonicalDtxsid"] == "DTXSID7020182"
    assert result["generatedFromTools"]


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
            "limitations": ["Use only for screening contexts."],
            "warnings": ["Does not perform PBPK simulation itself."],
        }
    ]
    assert "metadata:model_cards" not in result["knownDataGaps"]


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
    assert result["generatedFromTools"]
    assert isinstance(result["limitations"], list)


class MissingMmdbExposureResource(StubExposureResource):
    def get_exposure_mmdb_aggregate_by_dtxsid(self, dtxsid: str):
        raise CtxApiError(
            status=404,
            message="CTX API request failed: 404 ",
            detail={
                "status": 404,
                "error": "Not Found",
                "path": f"/exposure/mmdb/aggregate/search/by-dtxsid/{dtxsid}",
            },
        )


def test_assemble_comptox_evidence_pack_tolerates_missing_optional_mmdb_slice() -> None:
    interop = InteropResource(
        api_key="fake",
        chemical_resource=StubChemicalResource(),
        bioactivity_resource=StubBioactivityResource(),
        exposure_resource=MissingMmdbExposureResource(),
        hazard_resource=StubHazardResource(),
        metadata_resource=StubMetadataResource(),
    )

    result = interop.execute_tool(
        "assemble_comptox_evidence_pack",
        {
            "dtxsid": "DTXSID7020182",
            "hazard_datasets": ["toxval", "adme_ivive"],
            "max_assays": 5,
        },
    )

    validate_portable_schema("comptoxEvidencePack.v1.json", result)
    assert result["exposureEvidenceSummary"]["mmdb"]["recordCount"] == 0
    metadata = interop.get_last_metadata()
    mmdb_step = metadata["steps"]["exposure:mmdb"]
    assert mmdb_step["metadata"]["status"] == 404
    assert mmdb_step["metadata"]["optional"] is True
    assert mmdb_step["metadata"]["missing"] is True
