from __future__ import annotations

import json
from pathlib import Path

import pytest

from epacomp_tox.metadata import ModelCardStore
from epacomp_tox.resources.metadata import MetadataResource

SAMPLE_CARD = {
    "schemaVersion": "1.0",
    "modelDetails": {
        "name": "Sample Model",
        "version": "1.0.0",
        "modelType": "QSAR",
        "description": "Sample description",
        "developers": [{"name": "EPA"}],
        "organizations": ["EPA"],
        "releaseDate": "2025-01-01",
    },
    "intendedUse": {
        "summary": "Sample",
        "inScope": ["Scope"],
        "outOfScope": ["Out"],
        "limitations": [],
        "warnings": [],
        "regulatoryPrograms": [],
    },
    "oecdValidationPrinciples": {
        "definedEndpoint": {"description": "Endpoint", "unit": "mg/L"},
        "unambiguousAlgorithm": {"summary": "Algorithm"},
        "definedApplicabilityDomain": {"summary": "AD"},
        "goodnessOfFitMetrics": {},
        "mechanisticInterpretation": {"summary": "Mechanism"},
    },
    "trainingData": {
        "dataset": {"name": "Training", "source": "EPA"},
        "records": 1,
        "chemicalCount": 1,
    },
    "evaluationData": {
        "datasets": [{"name": "Eval", "source": "EPA"}],
        "validationApproach": "Holdout",
        "metrics": [{"name": "RMSE", "value": 0.1}],
    },
    "applicabilityDomain": {
        "summary": "AD",
        "criteria": [{"type": "descriptor_range", "description": "range"}],
        "enforcement": {"mcpTools": ["sample.check_ad"]},
    },
    "ethicalConsiderations": {"risks": []},
    "provenance": {
        "sourceRepositories": ["https://example.com"],
        "build": {"id": "test", "timestamp": "2025-01-01T00:00:00Z"},
        "checksum": {"algorithm": "SHA256", "value": "abc"},
        "reviewStatus": {"approvedBy": [{"name": "QA"}], "approvalDate": "2025-01-31"},
    },
}


@pytest.fixture()
def sample_store(tmp_path: Path) -> ModelCardStore:
    directory = tmp_path / "cards"
    directory.mkdir()
    with (directory / "sample.json").open("w", encoding="utf-8") as fh:
        json.dump(SAMPLE_CARD, fh)
    return ModelCardStore(directory=directory)


def test_metadata_resource_lists_cards(sample_store: ModelCardStore) -> None:
    resource = MetadataResource(store=sample_store)
    result = resource.execute_tool("metadata_get_model_card", {})
    assert result["modelCards"]
    assert result["modelCards"][0]["card"]["modelDetails"]["name"] == "Sample Model"


def test_metadata_resource_filters_by_name(sample_store: ModelCardStore) -> None:
    resource = MetadataResource(store=sample_store)
    result = resource.execute_tool(
        "metadata_get_model_card", {"model_name": "sample", "limit": 1}
    )
    assert result["modelCards"]
    result = resource.execute_tool("metadata_get_model_card", {"model_name": "unknown"})
    assert result["modelCards"] == []


def test_metadata_resource_filters_by_compliance(sample_store: ModelCardStore) -> None:
    resource = MetadataResource(store=sample_store)
    approved = resource.execute_tool(
        "metadata_get_model_card", {"compliance": "approved"}
    )
    assert len(approved["modelCards"]) == 1
    draft = resource.execute_tool("metadata_get_model_card", {"compliance": "draft"})
    assert draft["modelCards"] == []
