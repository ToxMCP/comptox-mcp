from __future__ import annotations

from unittest import mock

import pytest

from ctxpy import RateLimitInfo

from epacomp_tox.orchestrator.ctx_data import CtxDataAssembler
from epacomp_tox.orchestrator.identifiers import (
    IdentifierResolutionError,
    IdentifierResolver,
)
from epacomp_tox.orchestrator.predictive import PredictiveCoordinator
from epacomp_tox.orchestrator.models import PredictiveTask
from epacomp_tox.orchestrator.workflow import GenRAOrchestrator
from epacomp_tox.resources.cheminformatics import CheminformaticsResource
from epacomp_tox.resources.exposure import ExposureResource
from epacomp_tox.resources.hazard import HazardResource
from epacomp_tox.predictive import (
    ADCheckResult,
    PredictiveRequest,
    PredictiveServiceBase,
)


def _rate_limit(limit: int = 120, remaining: int = 119, reset: int = 60) -> RateLimitInfo:
    return RateLimitInfo(limit=limit, remaining=remaining, reset=reset)


class _StubADStore:
    def __init__(self, definition):
        self._definition = definition

    def get_definition(self, _model_name):
        return self._definition


class _StubPredictiveService(PredictiveServiceBase):
    def __init__(self, *, name: str, ad_results, payloads, ad_definition):
        super().__init__(
            config={"name": name, "version": "1.0"},
            ad_store=_StubADStore(ad_definition),
        )
        self._ad_results = list(ad_results)
        self._payloads = list(payloads)
        self._last_ad_result = self._ad_results[-1] if self._ad_results else None
        self.ad_checks = 0
        self.predictions = 0

    def _predict_impl(self, request: PredictiveRequest):
        self.predictions += 1
        if not self._payloads:
            raise RuntimeError("No payload configured")
        value = self._payloads.pop(0)
        # retain last value so repeated predict calls can reuse when necessary
        self._payloads.append(value)
        return value

    def _check_ad_impl(self, request: PredictiveRequest) -> ADCheckResult:
        self.ad_checks += 1
        if self._ad_results:
            result = self._ad_results.pop(0)
            self._last_ad_result = result
            self._ad_results.append(result)
            return result
        if self._last_ad_result is None:
            raise RuntimeError("No AD result configured")
        return self._last_ad_result


def test_identifier_resolver_caches_and_sanitizes_metadata():
    chemical_resource = mock.Mock()
    chemical_resource.search_chemical.return_value = [
        {
            "dtxsid": "DTXSID0000001",
            "preferredName": "Example Chemical",
            "casrn": "50-00-0",
        }
    ]
    chemical_resource.get_chemical_details.return_value = {
        "dtxsid": "DTXSID0000001",
        "preferredName": "Example Chemical",
        "casrn": "50-00-0",
        "synonyms": ["example chemical", "Formaldehyde"],
    }
    chemical_resource.get_last_metadata.side_effect = [
        {"status": 200, "rate_limit": _rate_limit()},
        {"status": 200, "request_id": "req-chem-1"},
    ]

    resolver = IdentifierResolver(chemical_resource=chemical_resource, cache_ttl=120)

    result = resolver.resolve("50-00-0", identifier_type="casrn")
    assert result.dtxsid == "DTXSID0000001"
    assert result.cache_hit is False
    assert "Formaldehyde" in result.synonyms
    assert result.trace[0].metadata["rate_limit"]["limit"] == 120

    cached = resolver.resolve("50-00-0", identifier_type="casrn")
    assert cached.cache_hit is True
    assert chemical_resource.search_chemical.call_count == 1
    assert chemical_resource.get_chemical_details.call_count == 1
    # No additional metadata calls when serving from cache
    assert chemical_resource.get_last_metadata.call_count == 2


def test_identifier_resolver_raises_when_not_found():
    chemical_resource = mock.Mock()
    chemical_resource.search_chemical.return_value = []
    chemical_resource.get_last_metadata.return_value = {}

    resolver = IdentifierResolver(chemical_resource=chemical_resource)
    with pytest.raises(IdentifierResolutionError):
        resolver.resolve("UNKNOWN", identifier_type="name")


def _mock_resource(resource_cls):
    return mock.create_autospec(resource_cls, instance=True)


def test_ctx_data_assembler_fetches_datasets_and_uses_cache():
    hazard_resource = _mock_resource(HazardResource)
    exposure_resource = _mock_resource(ExposureResource)
    cheminformatics_resource = _mock_resource(CheminformaticsResource)

    hazard_resource.search_hazard.return_value = [{"hazard": "record"}]
    hazard_resource.get_last_metadata.side_effect = lambda: {"status": 200, "rate_limit": _rate_limit(100, 98, 30)}

    exposure_resource.search_httk.return_value = [{"httk": "value"}]
    exposure_resource.search_qsurs.return_value = []
    exposure_resource.search_cpdat.return_value = [{"fc": "industrial"}]
    exposure_resource.get_last_metadata.side_effect = lambda: {"status": 200, "request_id": "req-exp"}

    cheminformatics_resource.search_toxprints.return_value = {"fingerprints": ["FP1"]}
    cheminformatics_resource.get_last_metadata.return_value = {}

    assembler = CtxDataAssembler(
        hazard_resource=hazard_resource,
        exposure_resource=exposure_resource,
        cheminformatics_resource=cheminformatics_resource,
        hazard_data_types=("all",),
        exposure_datasets=("httk",),
        cpdat_vocabularies=("fc",),
        include_toxprints=False,
        cache_ttl=300,
    )

    bundle = assembler.assemble("dtxsid0001234", scenarios=["genra_read_across"])
    assert bundle.cache_hit is False
    assert bundle.hazard["all"][0]["hazard"] == "record"
    assert bundle.exposure["httk"][0]["httk"] == "value"
    assert bundle.exposure["cpdat:fc"][0]["fc"] == "industrial"
    assert "exposure:qsurs" in bundle.data_gaps  # qsurs returned empty
    assert bundle.cheminformatics["toxprints"]["fingerprints"] == ["FP1"]
    assert bundle.trace[0].metadata["rate_limit"]["limit"] == 100

    # Cached execution should avoid additional upstream calls
    cached = assembler.assemble("dtxsid0001234", scenarios=["genra_read_across"])
    assert cached.cache_hit is True
    assert hazard_resource.search_hazard.call_count == 1
    assert exposure_resource.search_httk.call_count == 1
    assert exposure_resource.search_qsurs.call_count == 1
    assert exposure_resource.search_cpdat.call_count == 1
    assert cheminformatics_resource.search_toxprints.call_count == 1


def test_ctx_data_assembler_marks_toxprint_gap_when_resource_missing():
    hazard_resource = _mock_resource(HazardResource)
    hazard_resource.search_hazard.return_value = []
    hazard_resource.get_last_metadata.return_value = {}

    exposure_resource = _mock_resource(ExposureResource)
    exposure_resource.get_last_metadata.return_value = {}

    assembler = CtxDataAssembler(
        hazard_resource=hazard_resource,
        exposure_resource=exposure_resource,
        cheminformatics_resource=None,
        hazard_data_types=("all",),
        exposure_datasets=(),
        cpdat_vocabularies=(),
        include_toxprints=True,
        cache_ttl=0,
    )

    bundle = assembler.assemble("DTXSID9999999")
    assert "cheminformatics:toxprints" in bundle.data_gaps
    assert "hazard:all" in bundle.data_gaps


def test_predictive_coordinator_success_flow():
    ad = ADCheckResult(in_domain=True, confidence=0.9)
    service = _StubPredictiveService(
        name="Stub",
        ad_results=[ad],
        payloads=[{"value": 42}],
        ad_definition={"model": "Stub", "version": "1", "policy": "block", "errorCode": "STUB_AD_FAIL"},
    )
    coordinator = PredictiveCoordinator({"stub": service})
    task = PredictiveTask(service="stub", request=PredictiveRequest(chemical_identifier="DTXSID0001"))

    result = coordinator.run([task])

    assert result.succeeded is True
    assert len(result.guardrails) == 0
    assert result.results[0].prediction == {"value": 42}
    assert service.ad_checks >= 2
    assert service.predictions == 1


def test_predictive_coordinator_blocks_on_ad_failure():
    ad = ADCheckResult(in_domain=False, confidence=0.3)
    service = _StubPredictiveService(
        name="Blocked",
        ad_results=[ad],
        payloads=[{"value": 1}],
        ad_definition={"model": "Blocked", "version": "1", "policy": "block", "errorCode": "BLOCKED_AD"},
    )
    coordinator = PredictiveCoordinator({"blocked": service})
    task = PredictiveTask(service="blocked", request=PredictiveRequest(chemical_identifier="DTXSID0002"))

    result = coordinator.run([task], require_ad_clearance=True)

    assert result.succeeded is False
    assert result.results[0].status == "denied"
    assert result.guardrails[0].status == "denied"
    assert result.guardrails[0].code == "BLOCKED_AD"
    # predict never invoked when AD fails hard
    assert service.predictions == 0



def test_predictive_coordinator_warn_policy_continues():
    ad = ADCheckResult(in_domain=False, confidence=0.55)
    service = _StubPredictiveService(
        name="Warning",
        ad_results=[ad],
        payloads=[{"value": 7}],
        ad_definition={"model": "Warning", "version": "1", "policy": "warn", "errorCode": "WARN_AD"},
    )
    coordinator = PredictiveCoordinator({"warning": service}, default_require_ad_clearance=False)
    task = PredictiveTask(service="warning", request=PredictiveRequest(chemical_identifier="DTXSID0003"))

    result = coordinator.run([task])

    assert result.succeeded is True
    assert result.results[0].status == "success"
    assert len(result.guardrails) == 1
    assert result.guardrails[0].status == "warning"
    assert result.guardrails[0].code == "WARN_AD"
    assert service.predictions == 1


def test_genra_orchestrator_successful_bundle(tmp_path):
    hazard_resource = _mock_resource(HazardResource)
    exposure_resource = _mock_resource(ExposureResource)
    cheminformatics_resource = _mock_resource(CheminformaticsResource)
    chemical_resource = mock.Mock()

    hazard_resource.search_hazard.return_value = [{"hazard": 1}]
    hazard_resource.get_last_metadata.return_value = {}
    exposure_resource.search_httk.return_value = [{"httk": 2}]
    exposure_resource.search_cpdat.return_value = [{"fc": "cat"}]
    exposure_resource.get_last_metadata.return_value = {}
    cheminformatics_resource.search_toxprints.return_value = {"toxprints": []}
    cheminformatics_resource.get_last_metadata.return_value = {}

    chemical_resource.search_chemical.return_value = [{"dtxsid": "DTXSID0000001", "preferredName": "Example"}]
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
    predictive_service = _StubPredictiveService(
        name="Stub",
        ad_results=[ADCheckResult(in_domain=True, confidence=0.9)],
        payloads=[{"prediction": "ok"}],
        ad_definition={"model": "Stub", "version": "1", "policy": "block", "errorCode": "GENRA_AD_FAIL"},
    )
    coordinator = PredictiveCoordinator({"stub": predictive_service})
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
        predictive_plan=[PredictiveTask(service="stub", request=PredictiveRequest(chemical_identifier="DTXSID0000001"))],
    )

    assert bundle["status"] == "success"
    assert bundle["target"]["dtxsid"] == "DTXSID0000001"
    assert bundle["ctxData"]["hazard"]["all"][0]["hazard"] == 1
    assert bundle["predictive"]["results"][0]["prediction"] == {"prediction": "ok"}
    assert bundle["evidence"]["confidenceBand"] in {"Robust", "Limited", "Unavailable"}
    run_dir = tmp_path / bundle["workflowRunId"]
    bundle_path = run_dir / "bundle.json"
    metadata_path = run_dir / "metadata.json"
    attachments_dir = run_dir / "attachments"
    assert bundle_path.exists()
    assert metadata_path.exists()
    assert (attachments_dir / "ctx_data.json").exists()
    assert (attachments_dir / "predictive_results.json").exists()
    assert (attachments_dir / "evidence.json").exists()
    assert len(bundle["storage"]["attachments"]) >= 3
    assert bundle["storage"]["bundleChecksum"]


def test_predictive_coordinator_records_prediction_errors():
    ad = ADCheckResult(in_domain=True, confidence=0.8)
    service = _StubPredictiveService(
        name="Error",
        ad_results=[ad],
        payloads=[],  # triggers runtime error inside predict
        ad_definition={"model": "Error", "version": "1", "policy": "block", "errorCode": "ERR_AD"},
    )
    coordinator = PredictiveCoordinator({"error": service})
    task = PredictiveTask(service="error", request=PredictiveRequest(chemical_identifier="DTXSID0004"))

    result = coordinator.run([task])

    assert result.succeeded is False
    assert result.results[0].status == "error"
    assert result.guardrails[0].status == "error"
    assert "No payload" in result.results[0].error
