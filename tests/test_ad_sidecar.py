from __future__ import annotations

import json

from fastapi.testclient import TestClient

from epacomp_tox.predictive import PredictiveRequest
from epacomp_tox.predictive.ad_sidecar import (
    build_reference_ad_sidecar_app,
    evaluate_reference_ad,
)
from epacomp_tox.predictive.descriptor_providers import (
    ExternalChemistryDescriptorProvider,
)
from epacomp_tox.predictive.rule_providers import ExternalExpertRuleProvider


def test_reference_ad_evaluator_passes_similarity_and_coverage() -> None:
    request = PredictiveRequest(
        chemical_identifier="DTXSID000001",
        ad_inputs={
            "similarity": {
                "score": 0.82,
                "neighbors": 4,
            },
            "coverage": {
                "domains": ["in vivo", "in vitro"],
            },
        },
    )
    definition = {
        "model": "GenRA Read-Across Workflow",
        "version": "2.1.0",
        "criteria": [
            {
                "type": "similarity",
                "metric": "tanimoto",
                "threshold": 0.7,
                "minAnalogues": 3,
            },
            {
                "type": "coverage",
                "requirements": ["in vivo", "in vitro"],
                "minimumDomains": 2,
            },
        ],
    }

    result = evaluate_reference_ad(request, definition)

    assert result.in_domain is True
    assert result.confidence > 0.5
    assert result.details["supportedCriteria"] == 2
    assert result.details["unsupportedCriteria"] == []


def test_reference_ad_evaluator_degrades_confidence_for_unsupported_criteria() -> None:
    request = PredictiveRequest(
        chemical_identifier="DTXSID000001",
        ad_inputs={"similarity": {"score": 0.7, "neighbors": 5}},
    )
    definition = {
        "model": "OPERA Property Predictions",
        "version": "3.6.1",
        "criteria": [
            {
                "type": "descriptor_range",
                "descriptors": ["atomCount"],
                "range": {"mode": "min_max"},
            },
            {
                "type": "similarity",
                "metric": "tanimoto",
                "threshold": 0.6,
                "neighbors": 5,
            },
        ],
    }

    result = evaluate_reference_ad(request, definition)

    assert result.in_domain is True
    assert result.details["unsupportedCriteria"] == ["descriptor_range"]
    assert result.confidence < 1.0
    assert result.details["criteriaCoverage"] == 0.5


def test_reference_ad_evaluator_supports_descriptor_range_from_inline_inputs() -> None:
    request = PredictiveRequest(
        chemical_identifier="DTXSID000001",
        ad_inputs={
            "descriptor_values": {
                "atomCount": 22,
                "bondCount": 23,
                "polarSurfaceArea": 55.0,
            },
            "descriptor_bounds": {
                "atomCount": {"min": 1, "max": 40},
                "bondCount": {"min": 1, "max": 45},
                "polarSurfaceArea": {"lower": 10.0, "upper": 120.0},
            },
        },
    )
    definition = {
        "model": "OPERA Property Predictions",
        "version": "3.6.1",
        "criteria": [
            {
                "type": "descriptor_range",
                "descriptors": ["atomCount", "bondCount", "polarSurfaceArea"],
                "range": {"mode": "min_max"},
            }
        ],
    }

    result = evaluate_reference_ad(request, definition)

    assert result.in_domain is True
    assert result.details["unsupportedCriteria"] == []
    assert result.details["criterionResults"][0]["descriptorSource"] == "request.ad_inputs"


def test_reference_ad_evaluator_supports_descriptor_range_from_provider() -> None:
    captured = {}

    class _MockHttpResponse:
        def __init__(self, payload):
            self._payload = payload

        def read(self) -> bytes:
            return json.dumps(self._payload).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def _fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _MockHttpResponse(
            {
                "descriptorValues": {
                    "logP": 2.1,
                    "polarSurfaceArea": 48.0,
                },
                "descriptorBounds": {
                    "logP": {"lower": 0.0, "upper": 5.0},
                    "polarSurfaceArea": {"lower": 10.0, "upper": 90.0},
                },
                "source": "chem-backend",
            }
        )

    provider = ExternalChemistryDescriptorProvider(
        endpoint="http://chem-backend.local/descriptors",
        urlopen=_fake_urlopen,
    )
    request = PredictiveRequest(chemical_identifier="DTXSID000001")
    definition = {
        "model": "TEST Consensus Acute Toxicity",
        "version": "5.2.0",
        "criteria": [
            {
                "type": "descriptor_range",
                "descriptors": ["logP", "polarSurfaceArea"],
                "range": {"lowerPercentile": 0.05, "upperPercentile": 0.95},
            }
        ],
    }

    result = evaluate_reference_ad(
        request,
        definition,
        descriptor_provider=provider,
    )

    assert result.in_domain is True
    assert captured["url"] == "http://chem-backend.local/descriptors"
    assert captured["payload"]["chemicalIdentifier"] == "DTXSID000001"
    assert captured["payload"]["descriptors"] == ["logP", "polarSurfaceArea"]
    assert result.details["criterionResults"][0]["descriptorSource"] == "chem-backend"


def test_reference_ad_evaluator_fails_descriptor_range_when_provider_missing_bounds() -> None:
    class _Provider:
        name = "mock-provider"

        def resolve(self, *, request, descriptors, criterion, definition):
            from epacomp_tox.predictive.descriptor_providers import DescriptorContext

            return DescriptorContext(
                values={"atomCount": 12.0},
                bounds={},
                source="mock-provider",
                metadata={},
            )

    request = PredictiveRequest(chemical_identifier="DTXSID000001")
    definition = {
        "model": "OPERA Property Predictions",
        "version": "3.6.1",
        "criteria": [
            {
                "type": "descriptor_range",
                "descriptors": ["atomCount"],
                "range": {"mode": "min_max"},
            }
        ],
    }

    result = evaluate_reference_ad(
        request,
        definition,
        descriptor_provider=_Provider(),
    )

    assert result.in_domain is False
    assert result.details["criterionResults"][0]["reason"] == "missing_descriptor_context"


def test_reference_ad_evaluator_supports_expert_rule_from_inline_inputs() -> None:
    request = PredictiveRequest(
        chemical_identifier="DTXSID000001",
        ad_inputs={
            "expert_rule": {
                "mode_of_action_tags": {
                    "target_tags": ["pparg", "nuclear receptor"],
                    "analogues": [
                        {"id": "a1", "tags": ["pparg", "nuclear receptor"]},
                        {"id": "a2", "tags": ["pparg"]},
                    ],
                }
            }
        },
    )
    definition = {
        "model": "GenRA Read-Across Workflow",
        "version": "2.1.0",
        "criteria": [
            {
                "type": "expert_rule",
                "rule": "Mode of action tags must align",
                "allowableMismatch": 1,
            }
        ],
    }

    result = evaluate_reference_ad(request, definition)

    assert result.in_domain is True
    assert result.details["criterionResults"][0]["ruleKey"] == "mode_of_action_tags_align"
    assert result.details["criterionResults"][0]["ruleSource"] == "request.ad_inputs"


def test_reference_ad_evaluator_derives_expert_rule_tags_from_bioactivity_and_aop_inputs() -> None:
    request = PredictiveRequest(
        chemical_identifier="DTXSID000001",
        ad_inputs={
            "expert_rule": {
                "mechanistic_context": {
                    "target": {
                        "bioactivity_summary": [
                            {
                                "geneSymbol": "PPARG",
                                "targetFamily": "nuclear receptor",
                                "activityDirection": "activation",
                                "hitcall": 1,
                            },
                            {
                                "geneSymbol": "AHR",
                                "targetFamily": "transcription factor",
                                "activityDirection": "activation",
                                "hitCall": False,
                            },
                        ],
                        "aop_mappings": [
                            {
                                "eventLabel": "PPARG activation",
                                "eventType": "molecular_initiating_event",
                            }
                        ],
                    },
                    "analogues": [
                        {
                            "id": "a1",
                            "bioactivity_summary": [
                                {
                                    "geneSymbol": "PPARG",
                                    "targetFamily": "nuclear receptor",
                                    "activityDirection": "activation",
                                    "hitcall": 1,
                                }
                            ],
                        },
                        {
                            "id": "a2",
                            "aop_mappings": [
                                {
                                    "eventLabel": "PPARG activation",
                                    "eventType": "molecular_initiating_event",
                                }
                            ],
                        },
                    ],
                }
            }
        },
    )
    definition = {
        "model": "GenRA Read-Across Workflow",
        "version": "2.1.0",
        "criteria": [
            {
                "type": "expert_rule",
                "rule": "Mode of action tags must align",
                "allowableMismatch": 1,
            }
        ],
    }

    result = evaluate_reference_ad(request, definition)

    assert result.in_domain is True
    assert result.details["criterionResults"][0]["mechanisticDerivationUsed"] is True
    assert result.details["criterionResults"][0]["ruleSource"] == "derived:mechanistic_context"


def test_reference_ad_evaluator_fails_derived_expert_rule_when_mechanistic_tags_diverge() -> None:
    request = PredictiveRequest(
        chemical_identifier="DTXSID000001",
        ad_inputs={
            "expert_rule": {
                "mechanistic_context": {
                    "target": {
                        "bioactivity_summary": [
                            {
                                "geneSymbol": "PPARG",
                                "targetFamily": "nuclear receptor",
                                "activityDirection": "activation",
                                "hitcall": 1,
                            }
                        ]
                    },
                    "analogues": [
                        {
                            "id": "a1",
                            "bioactivity_summary": [
                                {
                                    "geneSymbol": "AHR",
                                    "targetFamily": "transcription factor",
                                    "activityDirection": "activation",
                                    "hitcall": 1,
                                }
                            ],
                        }
                    ],
                }
            }
        },
    )
    definition = {
        "model": "GenRA Read-Across Workflow",
        "version": "2.1.0",
        "criteria": [
            {
                "type": "expert_rule",
                "rule": "Mode of action tags must align",
                "allowableMismatch": 1,
            }
        ],
    }

    result = evaluate_reference_ad(request, definition)

    assert result.in_domain is False
    assert result.details["criterionResults"][0]["analogueResults"][0]["passed"] is False


def test_reference_ad_evaluator_fails_expert_rule_when_mismatch_exceeds_threshold() -> None:
    request = PredictiveRequest(
        chemical_identifier="DTXSID000001",
        ad_inputs={
            "expert_rule": {
                "mode_of_action_tags": {
                    "target_tags": ["pparg", "nuclear receptor"],
                    "analogues": [
                        {"id": "a1", "tags": ["ahr", "transcription factor"]},
                    ],
                }
            }
        },
    )
    definition = {
        "model": "GenRA Read-Across Workflow",
        "version": "2.1.0",
        "criteria": [
            {
                "type": "expert_rule",
                "rule": "Mode of action tags must align",
                "allowableMismatch": 1,
            }
        ],
    }

    result = evaluate_reference_ad(request, definition)

    assert result.in_domain is False
    assert result.details["criterionResults"][0]["analogueResults"][0]["passed"] is False


def test_reference_ad_evaluator_supports_expert_rule_from_provider() -> None:
    captured = {}

    class _MockHttpResponse:
        def __init__(self, payload):
            self._payload = payload

        def read(self) -> bytes:
            return json.dumps(self._payload).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def _fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _MockHttpResponse(
            {
                "ruleContext": {
                    "mode_of_action_tags": {
                        "target_tags": ["pparg", "nuclear receptor"],
                        "analogues": [
                            {"id": "a1", "tags": ["pparg", "nuclear receptor"]},
                            {"id": "a2", "tags": ["pparg"]},
                        ],
                    }
                },
                "source": "mechanistic-backend",
            }
        )

    provider = ExternalExpertRuleProvider(
        endpoint="http://mechanistic-backend.local/rules",
        urlopen=_fake_urlopen,
    )
    request = PredictiveRequest(chemical_identifier="DTXSID000001")
    definition = {
        "model": "GenRA Read-Across Workflow",
        "version": "2.1.0",
        "criteria": [
            {
                "type": "expert_rule",
                "rule": "Mode of action tags must align",
                "allowableMismatch": 1,
            }
        ],
    }

    result = evaluate_reference_ad(
        request,
        definition,
        rule_provider=provider,
    )

    assert result.in_domain is True
    assert captured["url"] == "http://mechanistic-backend.local/rules"
    assert captured["payload"]["rule"] == "Mode of action tags must align"
    assert result.details["criterionResults"][0]["ruleSource"] == "mechanistic-backend"


def test_reference_ad_evaluator_fails_when_required_inputs_are_missing() -> None:
    request = PredictiveRequest(chemical_identifier="DTXSID000001")
    definition = {
        "model": "TEST Consensus Acute Toxicity",
        "version": "5.2.0",
        "criteria": [
            {
                "type": "similarity",
                "metric": "tanimoto",
                "threshold": 0.65,
            }
        ],
    }

    result = evaluate_reference_ad(request, definition)

    assert result.in_domain is False
    assert result.details["criterionResults"][0]["reason"] == "missing_similarity_inputs"


def test_reference_ad_sidecar_http_contract() -> None:
    client = TestClient(build_reference_ad_sidecar_app())

    response = client.post(
        "/evaluate",
        json={
            "request": {
                "chemical_identifier": "DTXSID000001",
                "ad_inputs": {
                    "similarity": {"score": 0.8, "neighbors": 5},
                },
            },
            "applicabilityDomain": {
                "model": "OPERA Property Predictions",
                "version": "3.6.1",
                "criteria": [
                    {
                        "type": "similarity",
                        "metric": "tanimoto",
                        "threshold": 0.6,
                        "neighbors": 5,
                    }
                ],
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["in_domain"] is True
    assert body["details"]["adEvaluator"] == "external-chemistry-service"


def test_reference_ad_sidecar_healthz() -> None:
    client = TestClient(build_reference_ad_sidecar_app())

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_reference_ad_sidecar_healthz_reports_descriptor_provider() -> None:
    class _Provider:
        name = "mock-provider"

        def resolve(self, *, request, descriptors, criterion, definition):
            raise AssertionError("not used")

    client = TestClient(build_reference_ad_sidecar_app(descriptor_provider=_Provider()))

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["descriptorProvider"] == "mock-provider"


def test_reference_ad_sidecar_healthz_reports_rule_provider() -> None:
    class _Provider:
        name = "mock-rule-provider"

        def resolve(self, *, request, criterion, definition):
            raise AssertionError("not used")

    client = TestClient(build_reference_ad_sidecar_app(rule_provider=_Provider()))

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["ruleProvider"] == "mock-rule-provider"
