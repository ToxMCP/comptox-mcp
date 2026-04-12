from __future__ import annotations

import json
import urllib.error
from typing import Any, Dict, Optional

import pytest

from epacomp_tox.metadata.applicability import ApplicabilityDomainStore
from epacomp_tox.predictive import (
    ADEvaluatorError,
    ADCheckResult,
    DelegatedServiceADEvaluator,
    ExternalChemistryServiceADEvaluator,
    GenRAService,
    OperaPropertyService,
    PredictiveRequest,
    PredictiveServiceBase,
    TestConsensusPredictiveService,
    build_ad_evaluator,
)
from epacomp_tox.predictive.clients import PredictiveClient


class StubClient(PredictiveClient):
    def __init__(
        self,
        *,
        response: Dict[str, Any],
        confidence: float = 1.0,
        in_domain: bool = True,
    ):
        self.response = response
        self.confidence = confidence
        self.in_domain = in_domain

    def predict(self, request: PredictiveRequest) -> Dict[str, Any]:
        return {**self.response, "identifier": request.chemical_identifier}

    def check_applicability_domain(self, request: PredictiveRequest) -> ADCheckResult:
        return ADCheckResult(in_domain=self.in_domain, confidence=self.confidence)


class StubGenRAAnalogueClient(StubClient):
    def __init__(self, *, analogue_response: Any, **kwargs):
        super().__init__(**kwargs)
        self.analogue_response = analogue_response

    def search_analogues(self, request: PredictiveRequest) -> Any:
        return self.analogue_response


class DummyService(PredictiveServiceBase):
    def __init__(self, *, config: Optional[Dict[str, Any]] = None, **kwargs):
        self.ad_checks = 0
        super().__init__(
            config=config
            or {"name": "Dummy Service", "version": "0.1", "ad_model_name": ""},
            **kwargs,
        )

    def _predict_impl(self, request: PredictiveRequest) -> Dict[str, Any]:
        return {"value": 1.0}

    def _check_ad_impl(self, request: PredictiveRequest) -> ADCheckResult:
        self.ad_checks += 1
        return ADCheckResult(in_domain=True, confidence=0.5)


SERVICE_CASES = [
    (
        TestConsensusPredictiveService,
        {
            "name": "TEST Consensus Acute Toxicity",
            "version": "5.2.0",
            "ad_model_name": "TEST Consensus Acute Toxicity",
        },
        "block",
    ),
    (
        OperaPropertyService,
        {
            "name": "OPERA Property Predictions",
            "version": "3.6.1",
            "ad_model_name": "OPERA Property Predictions",
        },
        "warn",
    ),
    (
        GenRAService,
        {
            "name": "GenRA Read-Across Workflow",
            "version": "2.1.0",
            "ad_model_name": "GenRA Read-Across Workflow",
        },
        "block",
    ),
]


@pytest.mark.parametrize("service_cls,config,policy", SERVICE_CASES)
def test_predictive_service_success(service_cls, config, policy):
    client = StubClient(response={"value": 1.23})
    service = service_cls(
        config=config,
        client=client,
        ad_store=ApplicabilityDomainStore(),
    )
    req = PredictiveRequest(chemical_identifier="DTXSID000001")
    result = service.predict(req)
    assert result.prediction["value"] == 1.23
    assert result.applicability_domain.in_domain is True
    assert result.metadata["identifier"] == "DTXSID000001"
    assert result.metadata.get("adPolicy") == policy


@pytest.mark.parametrize("service_cls,config,_policy", SERVICE_CASES)
def test_predictive_service_requires_client(service_cls, config, _policy):
    service = service_cls(config=config)
    req = PredictiveRequest(chemical_identifier="DTXSID000001")
    with pytest.raises(RuntimeError):
        service.predict(req)


@pytest.mark.parametrize("service_cls,config,policy", SERVICE_CASES)
def test_predictive_service_policy_enforcement(service_cls, config, policy):
    client = StubClient(response={"value": 1.23}, in_domain=False)
    service = service_cls(
        config=config,
        client=client,
        ad_store=ApplicabilityDomainStore(),
    )
    req = PredictiveRequest(chemical_identifier="DTXSID000001")
    if policy == "block":
        with pytest.raises(ValueError):
            service.predict(req)
    else:
        result = service.predict(req)
        assert result.metadata.get("adWarning") is True


def test_genra_service_prepares_request_with_auto_analogue_ids() -> None:
    client = StubGenRAAnalogueClient(
        response={"value": 1.23},
        analogue_response={
            "analogues": [
                {"dtxsid": "DTXSID0000999"},
                {"chemicalIdentifier": "DTXSID0000888"},
            ]
        },
    )
    service = GenRAService(
        config={
            "name": "GenRA Read-Across Workflow",
            "version": "2.1.0",
            "ad_model_name": "GenRA Read-Across Workflow",
        },
        client=client,
        ad_store=ApplicabilityDomainStore(),
    )

    prepared = service.prepare_request(
        PredictiveRequest(chemical_identifier="DTXSID000001")
    )

    assert prepared.ad_inputs["similarity"]["neighborIds"] == [
        "DTXSID0000999",
        "DTXSID0000888",
    ]
    assert prepared.ad_inputs["similarity"]["neighbors"] == 2
    assert prepared.ad_inputs["expert_rule"]["analogueIds"] == [
        "DTXSID0000999",
        "DTXSID0000888",
    ]
    assert prepared.ad_inputs["expert_rule"]["analogueIdSource"] == "genra-analogue-search"


def test_genra_service_surfaces_output_derived_analogue_ids_in_metadata() -> None:
    client = StubClient(
        response={
            "prediction": "ok",
            "analogues": [{"dtxsid": "DTXSID0000999"}, {"id": "DTXSID0000888"}],
        }
    )
    service = GenRAService(
        config={
            "name": "GenRA Read-Across Workflow",
            "version": "2.1.0",
            "ad_model_name": "GenRA Read-Across Workflow",
        },
        client=client,
        ad_store=ApplicabilityDomainStore(),
    )

    result = service.predict(PredictiveRequest(chemical_identifier="DTXSID000001"))

    assert result.metadata["resolvedAnalogueIds"] == [
        "DTXSID0000999",
        "DTXSID0000888",
    ]
    assert result.metadata["resolvedAnalogueCount"] == 2
    assert result.metadata["analogueIdSource"] == "genra-prediction-payload"


def test_delegated_ad_evaluator_preserves_current_behavior() -> None:
    service = DummyService(ad_evaluator=DelegatedServiceADEvaluator())

    result = service.predict(PredictiveRequest(chemical_identifier="DTXSID000001"))

    assert service.ad_checks == 1
    assert result.metadata["adEvaluator"] == "delegated-service"
    assert result.metadata["adEnforcementLocation"] == "delegated-service"


def test_external_chemistry_ad_evaluator_bypasses_service_ad_check() -> None:
    evaluator = ExternalChemistryServiceADEvaluator(
        lambda request, definition: {
            "in_domain": False,
            "confidence": 0.91,
            "details": {"mode": "external"},
        }
    )
    service = DummyService(ad_evaluator=evaluator)

    with pytest.raises(ValueError):
        service.predict(PredictiveRequest(chemical_identifier="DTXSID000001"))

    assert service.ad_checks == 0


def test_build_ad_evaluator_defaults_to_delegated_service(monkeypatch) -> None:
    monkeypatch.delenv("EPACOMP_AD_EVALUATOR", raising=False)
    evaluator = build_ad_evaluator({})

    assert isinstance(evaluator, DelegatedServiceADEvaluator)


def test_build_ad_evaluator_requires_sidecar_url_for_external_backend(
    monkeypatch,
) -> None:
    monkeypatch.delenv("EPACOMP_AD_SIDECAR_URL", raising=False)
    with pytest.raises(ValueError, match="ad_sidecar_url"):
        build_ad_evaluator({"ad_evaluator": "external-chemistry-service"})


class _MockHttpResponse:
    def __init__(self, payload: Dict[str, Any]) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> "_MockHttpResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def test_external_chemistry_sidecar_posts_request_and_sets_metadata(
    tmp_path,
) -> None:
    captured: Dict[str, Any] = {}
    ad_dir = tmp_path / "ad"
    ad_dir.mkdir()
    (ad_dir / "dummy.json").write_text(
        json.dumps(
            {
                "model": "Dummy Service",
                "version": "0.1",
                "criteria": [{"type": "similarity", "threshold": 0.7}],
                "policy": "block",
            }
        )
    )
    ad_store = ApplicabilityDomainStore(directory=ad_dir)

    def _fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _MockHttpResponse(
            {
                "in_domain": True,
                "confidence": 0.88,
                "details": {"criteriaMatched": 1},
            }
        )

    evaluator = ExternalChemistryServiceADEvaluator(
        endpoint="http://ad-sidecar.local/evaluate",
        timeout_seconds=12,
        bearer_token="secret-token",
        api_key="sidecar-key",
        urlopen=_fake_urlopen,
    )
    service = DummyService(
        config={"name": "Dummy Service", "version": "0.1", "ad_model_name": "Dummy Service"},
        ad_store=ad_store,
        ad_evaluator=evaluator,
    )

    result = service.predict(PredictiveRequest(chemical_identifier="DTXSID000001"))

    assert service.ad_checks == 0
    assert captured["url"] == "http://ad-sidecar.local/evaluate"
    assert captured["timeout"] == 12
    headers = {key.lower(): value for key, value in captured["headers"].items()}
    assert headers["authorization"] == "Bearer secret-token"
    assert headers["x-api-key"] == "sidecar-key"
    assert captured["payload"]["request"]["chemical_identifier"] == "DTXSID000001"
    assert captured["payload"]["applicabilityDomain"]["model"] == "Dummy Service"
    assert result.metadata["adEvaluator"] == "external-chemistry-service"
    assert result.metadata["adEnforcementLocation"] == "local-engine"


def test_external_chemistry_sidecar_falls_back_to_delegated_on_transport_error() -> None:
    def _failing_urlopen(request, timeout):
        raise urllib.error.URLError("sidecar unavailable")

    evaluator = ExternalChemistryServiceADEvaluator(
        endpoint="http://ad-sidecar.local/evaluate",
        fallback_to_delegated=True,
        urlopen=_failing_urlopen,
    )
    service = DummyService(ad_evaluator=evaluator)

    result = service.predict(PredictiveRequest(chemical_identifier="DTXSID000001"))

    assert service.ad_checks == 1
    assert result.metadata["adEvaluator"] == "external-chemistry-service"
    assert result.metadata["adEnforcementLocation"] == "delegated-service"
    assert result.metadata["adFallbackUsed"] is True
    assert result.metadata["adFallbackReason"] == "external-chemistry-service-unavailable"


def test_external_chemistry_sidecar_raises_without_fallback_on_transport_error() -> None:
    def _failing_urlopen(request, timeout):
        raise urllib.error.URLError("sidecar unavailable")

    evaluator = ExternalChemistryServiceADEvaluator(
        endpoint="http://ad-sidecar.local/evaluate",
        urlopen=_failing_urlopen,
    )
    service = DummyService(ad_evaluator=evaluator)

    with pytest.raises(ADEvaluatorError, match="external chemistry AD evaluator failed"):
        service.check_applicability_domain(
            PredictiveRequest(chemical_identifier="DTXSID000001")
        )


def test_predictive_service_builds_external_evaluator_from_config() -> None:
    service = DummyService(
        config={
            "name": "Dummy Service",
            "version": "0.1",
            "ad_model_name": "",
            "ad_evaluator": "external-chemistry-service",
            "ad_sidecar_url": "http://ad-sidecar.local/evaluate",
        }
    )

    assert isinstance(service.ad_evaluator, ExternalChemistryServiceADEvaluator)
