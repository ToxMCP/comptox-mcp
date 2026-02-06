from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.testclient import TestClient

from epacomp_tox.metadata.applicability import ApplicabilityDomainStore
from epacomp_tox.predictive import (
    ADCheckResult,
    OperaPropertyService,
    PredictiveRequest,
    PredictiveServiceBase,
    TestConsensusPredictiveService,
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


def _write_ad(
    tmp_path: Path, name: str, policy: str, error_code: str | None = None
) -> ApplicabilityDomainStore:
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


class _SchemaStubService(PredictiveServiceBase):
    def __init__(self) -> None:
        super().__init__(
            config={
                "name": "schema-stub",
                "version": "0.0.1",
            }
        )

    def _predict_impl(self, request: PredictiveRequest) -> Dict[str, Any]:
        return {"value": 42, "identifier": request.chemical_identifier}

    def _check_ad_impl(self, request: PredictiveRequest) -> ADCheckResult:
        return ADCheckResult(
            in_domain=True, confidence=0.99, details={"policy": "allow"}
        )


def test_block_policy_returns_error(tmp_path: Path) -> None:
    ad_store = _write_ad(
        tmp_path, "TEST Consensus Acute Toxicity", "block", "TEST_AD_FAIL"
    )
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
    ad_store = _write_ad(
        tmp_path, "OPERA Property Predictions", "warn", "OPERA_AD_WARN"
    )
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


def test_predictive_router_validates_responses(monkeypatch) -> None:
    service = _SchemaStubService()
    router = build_predictive_router(service_factory=lambda: service, prefix="/schema")
    app = FastAPI()
    app.include_router(router)
    client = _create_client(app)

    recorded: list[tuple[str, str]] = []

    def _fake_validate(payload, *, namespace, name):  # type: ignore[override]
        recorded.append((namespace, name))

    monkeypatch.setattr(
        "epacomp_tox.predictive.router.validate_payload", _fake_validate
    )

    resp = client.post("/schema/predict", json={"chemical_identifier": "DTXSID3"})
    assert resp.status_code == 200
    ad_resp = client.post(
        "/schema/check_applicability_domain", json={"chemical_identifier": "DTXSID3"}
    )
    assert ad_resp.status_code == 200

    assert ("predictive", "predict.response.schema") in recorded
    assert ("predictive", "ad_check.response.schema") in recorded
