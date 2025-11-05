from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from epacomp_tox.metadata.applicability import ApplicabilityDomainStore
from epacomp_tox.predictive import (
    PredictiveRequest,
    ADCheckResult,
    TestConsensusPredictiveService,
    OperaPropertyService,
    build_predictive_router,
)
from epacomp_tox.predictive.clients import PredictiveClient


class StubClient(PredictiveClient):
    def __init__(self, *, response, in_domain: bool, confidence: float = 0.9):
        self.response = response
        self.in_domain = in_domain
        self.confidence = confidence

    def predict(self, request: PredictiveRequest):
        return self.response

    def check_applicability_domain(self, request: PredictiveRequest) -> ADCheckResult:
        return ADCheckResult(in_domain=self.in_domain, confidence=self.confidence)


def _write_ad(tmp_path: Path, name: str, policy: str, error_code: str | None = None) -> ApplicabilityDomainStore:
    directory = tmp_path / "ad"
    directory.mkdir()
    payload = {
        "model": name,
        "version": "1",
        "criteria": [],
        "policy": policy,
    }
    if error_code:
        payload["errorCode"] = error_code
    (directory / "entry.json").write_text(json.dumps(payload))
    return ApplicabilityDomainStore(directory=directory)


def _create_client(app) -> TestClient:
    return TestClient(app)


def test_block_policy_returns_error(tmp_path: Path) -> None:
    ad_store = _write_ad(tmp_path, "TEST Consensus Acute Toxicity", "block", "TEST_AD_FAIL")
    service = TestConsensusPredictiveService(
        config={
            "name": "TEST Consensus Acute Toxicity",
            "version": "5.2.0",
            "ad_model_name": "TEST Consensus Acute Toxicity",
        },
        client=StubClient(response={"value": 1.23}, in_domain=False),
        ad_store=ad_store,
    )
    router = build_predictive_router(service_factory=lambda: service, prefix="/test")
    app = FastAPI()
    app.include_router(router)
    client = _create_client(app)
    response = client.post("/test/predict", json={"chemical_identifier": "DTXSID1"})
    assert response.status_code == 400
    assert "TEST_AD_FAIL" in response.json()["detail"]


def test_warn_policy_allows_response(tmp_path: Path) -> None:
    ad_store = _write_ad(tmp_path, "OPERA Property Predictions", "warn", "OPERA_AD_WARN")
    service = OperaPropertyService(
        config={
            "name": "OPERA Property Predictions",
            "version": "3.6.1",
            "ad_model_name": "OPERA Property Predictions",
        },
        client=StubClient(response={"value": 0.5}, in_domain=False),
        ad_store=ad_store,
    )
    router = build_predictive_router(service_factory=lambda: service, prefix="/opera")
    app = FastAPI()
    app.include_router(router)
    client = _create_client(app)
    response = client.post("/opera/predict", json={"chemical_identifier": "DTXSID2"})
    assert response.status_code == 200
    body = response.json()
    assert body["metadata"]["adWarning"] is True
    assert "OPERA_AD_WARN" in body["metadata"]["adMessage"]
