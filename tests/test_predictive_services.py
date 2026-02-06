from __future__ import annotations

from typing import Any, Dict

import pytest

from epacomp_tox.metadata.applicability import ApplicabilityDomainStore
from epacomp_tox.predictive import (
    ADCheckResult,
    GenRAService,
    OperaPropertyService,
    PredictiveRequest,
    TestConsensusPredictiveService,
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
