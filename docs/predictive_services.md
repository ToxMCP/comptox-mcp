# Predictive Micro-Server Harness

Phase 2 introduces a shared harness for the TEST, OPERA, and GenRA predictive services. The goal is to give all model micro-servers a consistent structure for request validation, applicability-domain enforcement, and response formatting.

## Components

- `PredictiveServiceBase` (`src/epacomp_tox/predictive/base.py`)
  - Provides `predict` and `check_applicability_domain` entrypoints.
  - Handles guardrail enforcement (AD check before prediction) and metadata packaging.
  - Supplies hooks for model-specific request handling via `_predict_impl` and `_check_ad_impl`.
- `PredictiveRequest`, `PredictiveResponse`, and `ADCheckResult`
  - Pydantic models standardising request payloads and response envelopes.
  - Include chemistry identifier metadata and confidence scores required for downstream audits.
- `build_predictive_router` (`src/epacomp_tox/predictive/router.py`)
  - Creates FastAPI routers exposing `/predict` and `/check_applicability_domain` endpoints for a given service implementation.
  - Ensures consistent HTTP semantics (400 on failed AD, typed responses on success).

## Usage Pattern

```python
from epacomp_tox.predictive.base import PredictiveServiceBase, PredictiveRequest, ADCheckResult
from epacomp_tox.predictive.router import build_predictive_router

class TestConsensusService(PredictiveServiceBase):
    def _predict_impl(self, request: PredictiveRequest):
        # TODO: call TEST executable / API
        return {"endpoint": "LD50", "value": 1.2, "units": "log(mmol/kg)"}

    def _check_ad_impl(self, request: PredictiveRequest) -> ADCheckResult:
        # TODO: evaluate TEST-specific AD rules
        return ADCheckResult(in_domain=True, confidence=0.87)

router = build_predictive_router(service_factory=lambda: TestConsensusService(config={
    "name": "TEST-Consensus",
    "version": "5.2"
}), prefix="/test", tags=["TEST"])
```

Mount the router on a FastAPI app or within the orchestrator transport to expose MCP-compatible REST endpoints.

## Next Steps

- Task 3.2–3.4 will create concrete services for TEST, OPERA, and GenRA by subclassing `PredictiveServiceBase` and wiring in real model integrations.
- Task 3.5 will consume the applicability-domain definitions captured in the model metadata service.
- Task 3.6 will add regression test suites using the shared harness to validate success, AD failure, and error handling scenarios.

Refer back to `docs/model_metadata.md` for the schema that these services will use when serving model cards and AD definitions.

## Concrete Services

- `TestConsensusPredictiveService` wraps the TEST consensus toxicity models.
- `OperaPropertyService` wraps OPERA property predictors.
- `GenRAService` exposes the GenRA read-across workflow.
Each accepts a `PredictiveClient` implementation so integration with external executables or APIs can evolve without changing the harness.

- The TEST consensus service ships with `TestClient`, wrapping `ctxpy` interactions for predictions and applicability-domain checks.

- `OperaClient` provides the bridge to OPERA CLI/API for property predictions.

- `GenRAClient` integrates the GenRA analogue search and evidence weighting workflow.

Regression tests in `tests/test_predictive_regression.py` exercise block vs warn AD policies using the FastAPI router harness. These tests will be incorporated into CI once predictive services are wired into the orchestrator.

## Architecture Summary

The predictive micro-server stack consists of:
- Service wrappers (`TestConsensusPredictiveService`, `OperaPropertyService`, `GenRAService`) inheriting from `PredictiveServiceBase`.
- Per-model clients (`TestClient`, `OperaClient`, `GenRAClient`) that adapt executables/APIs to the harness.
- Shared applicability-domain enforcement provided by `ApplicabilityDomainStore` with block/warn policies.
- FastAPI routers generated via `build_predictive_router` for consistent `/predict` and `/check_applicability_domain` endpoints.

This architecture enables future models to plug in by implementing `PredictiveClient` and providing metadata/AD definitions.

- `GenRAClient` integrates the GenRA analogue search and evidence weighting workflow.

Shared applicability-domain enforcement is wired directly into the base service, so TEST/OPERA/GenRA all honor block/warn policies and surface metadata back to clients.
