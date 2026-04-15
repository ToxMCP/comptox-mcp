from __future__ import annotations

from unittest import mock

from epacomp_tox.orchestrator.ctx_data import CtxDataAssembler
from epacomp_tox.orchestrator.identifiers import IdentifierResolver
from epacomp_tox.orchestrator.models import PredictiveTask
from epacomp_tox.orchestrator.predictive import PredictiveCoordinator
from epacomp_tox.orchestrator.workflow import GenRAOrchestrator
from epacomp_tox.predictive import ADCheckResult, PredictiveRequest
from epacomp_tox.predictive.base import PredictiveServiceBase
from epacomp_tox.resources.cheminformatics import CheminformaticsResource
from epacomp_tox.resources.exposure import ExposureResource
from epacomp_tox.resources.hazard import HazardResource


def _mock_resource(resource_cls):
    return mock.create_autospec(resource_cls, instance=True)


class _StubService(PredictiveServiceBase):
    def __init__(self):
        super().__init__(config={"name": "Stub", "version": "1.0"})

    def _predict_impl(self, request):
        return {"prediction": "ok"}

    def _check_ad_impl(self, request):
        return ADCheckResult(in_domain=True, confidence=0.9, details={})


def test_bundle_includes_provenance_section(tmp_path):
    hazard_resource = _mock_resource(HazardResource)
    exposure_resource = _mock_resource(ExposureResource)
    cheminformatics_resource = _mock_resource(CheminformaticsResource)
    chemical_resource = mock.Mock()

    hazard_resource.search_hazard.return_value = [{"hazard": 1}]
    hazard_resource.get_last_metadata.return_value = {}
    exposure_resource.search_httk.return_value = [{"httk": 2}]
    exposure_resource.search_qsurs.return_value = []
    exposure_resource.search_cpdat.return_value = [{"fc": "cat"}]
    exposure_resource.get_last_metadata.return_value = {}
    cheminformatics_resource.search_toxprints.return_value = {"toxprints": []}
    cheminformatics_resource.get_last_metadata.return_value = {}
    chemical_resource.search_chemical.return_value = [
        {"dtxsid": "DTXSID0000001", "preferredName": "Example"}
    ]
    chemical_resource.get_chemical_details.return_value = {
        "dtxsid": "DTXSID0000001",
        "preferredName": "Example",
        "casrn": "50-00-0",
    }
    chemical_resource.get_last_metadata.return_value = {}

    resolver = IdentifierResolver(chemical_resource=chemical_resource, cache_ttl=0)
    assembler = CtxDataAssembler(
        hazard_resource=hazard_resource,
        exposure_resource=exposure_resource,
        cheminformatics_resource=cheminformatics_resource,
        include_toxprints=False,
        cache_ttl=0,
    )
    coordinator = PredictiveCoordinator({"stub": _StubService()})
    orchestrator = GenRAOrchestrator(
        identifier_resolver=resolver,
        ctx_data_assembler=assembler,
        predictive_coordinator=coordinator,
        persistence_dir=tmp_path,
        clock=lambda: "2025-03-26T00:00:00Z",
    )

    bundle = orchestrator.run_workflow(
        target_identifier="50-00-0",
        identifier_type="casrn",
        scenarios=["genra_read_across"],
        predictive_plan=[
            PredictiveTask(
                service="stub",
                request=PredictiveRequest(chemical_identifier="DTXSID0000001"),
            )
        ],
        options={"traceId": "trace-xyz-999"},
    )

    assert "provenance" in bundle
    prov = bundle["provenance"]
    assert prov["traceId"] == "trace-xyz-999"
    assert prov["createdAt"] == "2025-03-26T00:00:00Z"
    assert "serverVersion" in prov
    assert "runtimeEnvironment" in prov
    assert "upstreamProvenance" in prov
    assert "ctxData" in prov["upstreamProvenance"]
    assert "predictive" in prov["upstreamProvenance"]


def test_bundle_provenance_without_trace_id(tmp_path):
    hazard_resource = _mock_resource(HazardResource)
    exposure_resource = _mock_resource(ExposureResource)
    cheminformatics_resource = _mock_resource(CheminformaticsResource)
    chemical_resource = mock.Mock()

    hazard_resource.search_hazard.return_value = [{"hazard": 1}]
    hazard_resource.get_last_metadata.return_value = {}
    exposure_resource.search_httk.return_value = [{"httk": 2}]
    exposure_resource.search_qsurs.return_value = []
    exposure_resource.search_cpdat.return_value = [{"fc": "cat"}]
    exposure_resource.get_last_metadata.return_value = {}
    cheminformatics_resource.search_toxprints.return_value = {"toxprints": []}
    cheminformatics_resource.get_last_metadata.return_value = {}
    chemical_resource.search_chemical.return_value = [
        {"dtxsid": "DTXSID0000001", "preferredName": "Example"}
    ]
    chemical_resource.get_chemical_details.return_value = {
        "dtxsid": "DTXSID0000001",
        "preferredName": "Example",
        "casrn": "50-00-0",
    }
    chemical_resource.get_last_metadata.return_value = {}

    resolver = IdentifierResolver(chemical_resource=chemical_resource, cache_ttl=0)
    assembler = CtxDataAssembler(
        hazard_resource=hazard_resource,
        exposure_resource=exposure_resource,
        cheminformatics_resource=cheminformatics_resource,
        include_toxprints=False,
        cache_ttl=0,
    )
    coordinator = PredictiveCoordinator({"stub": _StubService()})
    orchestrator = GenRAOrchestrator(
        identifier_resolver=resolver,
        ctx_data_assembler=assembler,
        predictive_coordinator=coordinator,
        persistence_dir=tmp_path,
        clock=lambda: "2025-03-26T00:00:00Z",
    )

    bundle = orchestrator.run_workflow(
        target_identifier="50-00-0",
        identifier_type="casrn",
        scenarios=["genra_read_across"],
        predictive_plan=[
            PredictiveTask(
                service="stub",
                request=PredictiveRequest(chemical_identifier="DTXSID0000001"),
            )
        ],
    )

    assert "provenance" in bundle
    assert bundle["provenance"]["traceId"] is None
