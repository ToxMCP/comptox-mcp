# Predictive Micro-Server Harness

> Experimental/internal guide. The predictive service harness described here is not part of the default public MCP tool catalog released in `v0.2.2`.

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

Mount the router on a FastAPI app or within an internal orchestrator transport when working on the experimental predictive stack.

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
  - If the client exposes an analogue-search method such as `search_analogues(...)`, `GenRAService.prepare_request(...)` will auto-seed `ad_inputs.similarity.neighborIds` and `ad_inputs.expert_rule.analogueIds` before AD evaluation.
  - This is what allows orchestrator-side mechanistic enrichment to pull analogue bioactivity/AOP context without the caller pre-populating analogue IDs in the request.
  - If analogue IDs were not available up front, `GenRAService` now backfills them from delegated AD details or the prediction payload when those payloads expose the final analogue set. The stored workflow request provenance and GenRA metadata then record the resolved analogue IDs and their source.

Regression tests in `tests/test_predictive_regression.py` exercise block vs warn AD policies using the FastAPI router harness. These tests are useful internal coverage, but they should not be confused with the canonical public-surface release gates.

## Architecture Summary

The predictive micro-server stack consists of:
- Service wrappers (`TestConsensusPredictiveService`, `OperaPropertyService`, `GenRAService`) inheriting from `PredictiveServiceBase`.
- Per-model clients (`TestClient`, `OperaClient`, `GenRAClient`) that adapt executables/APIs to the harness.
- Shared applicability-domain enforcement provided by `ApplicabilityDomainStore` with block/warn policies.
- FastAPI routers generated via `build_predictive_router` for consistent `/predict` and `/check_applicability_domain` endpoints.

This architecture enables future models to plug in by implementing `PredictiveClient` and providing metadata/AD definitions.

- `GenRAClient` integrates the GenRA analogue search and evidence weighting workflow.

Shared applicability-domain enforcement is wired directly into the base service, so TEST/OPERA/GenRA all honor block/warn policies and surface metadata back to clients.

## Sidecar-backed AD evaluation

The AD harness now supports two backends:

- `delegated-service` keeps the current behavior and calls the model client’s native AD check.
- `external-chemistry-service` posts the predictive request plus the machine-readable AD definition to a chemistry sidecar for local-engine enforcement.

Configure the sidecar through the service config:

```python
service = TestConsensusPredictiveService(
    config={
        "name": "TEST Consensus Acute Toxicity",
        "version": "5.2.0",
        "ad_model_name": "TEST Consensus Acute Toxicity",
        "ad_evaluator": "external-chemistry-service",
        "ad_sidecar_url": "http://localhost:8090/evaluate",
        "ad_sidecar_timeout_seconds": 15,
        "ad_sidecar_fallback_to_delegated": False,
    },
    client=test_client,
)
```

The same knobs can be provided through environment variables when you want one evaluator policy across all predictive services:

- `EPACOMP_AD_EVALUATOR`
- `EPACOMP_AD_SIDECAR_URL`
- `EPACOMP_AD_SIDECAR_TIMEOUT_SECONDS`
- `EPACOMP_AD_SIDECAR_BEARER_TOKEN`
- `EPACOMP_AD_SIDECAR_API_KEY`
- `EPACOMP_AD_SIDECAR_FALLBACK_TO_DELEGATED`

When the sidecar is used successfully, predictive metadata reports `adEvaluator=external-chemistry-service` and `adEnforcementLocation=local-engine`. If delegated fallback is enabled and the sidecar is unavailable, the response is marked with `adFallbackUsed=true` and the enforcement location is downgraded to `delegated-service`.

### Reference sidecar

The repo now includes a small runnable reference sidecar in [`src/epacomp_tox/predictive/ad_sidecar.py`](../src/epacomp_tox/predictive/ad_sidecar.py):

```bash
uvicorn epacomp_tox.predictive.ad_sidecar:app --host 127.0.0.1 --port 8090
```

It is intentionally limited. The reference evaluator currently executes only:

- `similarity`
- `coverage`
- `descriptor_range` when descriptor values and numeric bounds are available
- `expert_rule` for the documented GenRA rule `Mode of action tags must align`

It does not yet execute:

- arbitrary expert rules outside the documented MoA-tag alignment contract

Those unsupported criterion types are reported in the AD result details and reduce overall confidence instead of being silently ignored.

To make the supported criteria executable without embedding a full chemistry stack, the predictive request can include optional `ad_inputs`:

```json
{
  "chemical_identifier": "DTXSID000001",
  "identifier_type": "dtxsid",
  "ad_inputs": {
    "similarity": {
      "score": 0.82,
      "neighbors": 4
    },
    "coverage": {
      "domains": ["in vivo", "in vitro"]
    }
  }
}
```

The sidecar request body posted by `ExternalChemistryServiceADEvaluator` is:

```json
{
  "request": { "...PredictiveRequest..." },
  "applicabilityDomain": { "...AD definition JSON..." }
}
```

This is a reference implementation for internal use. It is meant to prove the contract and evaluation flow, not to replace a full cheminformatics-backed AD engine.

### Optional descriptor backend

`descriptor_range` is now executable only when the sidecar can obtain numeric descriptor values and bounds. The reference sidecar supports two sources:

- inline request inputs via `ad_inputs.descriptor_values` and `ad_inputs.descriptor_bounds`
- an optional chemistry backend configured through environment variables

Descriptor-backend environment variables:

- `EPACOMP_AD_DESCRIPTOR_BACKEND_URL`
- `EPACOMP_AD_DESCRIPTOR_BACKEND_TIMEOUT_SECONDS`
- `EPACOMP_AD_DESCRIPTOR_BACKEND_BEARER_TOKEN`
- `EPACOMP_AD_DESCRIPTOR_BACKEND_API_KEY`

The sidecar posts this descriptor request shape to the backend:

```json
{
  "chemicalIdentifier": "DTXSID000001",
  "identifierType": "dtxsid",
  "descriptors": ["logP", "polarSurfaceArea"],
  "criterion": {
    "type": "descriptor_range",
    "descriptors": ["logP", "polarSurfaceArea"],
    "range": {"lowerPercentile": 0.05, "upperPercentile": 0.95}
  },
  "applicabilityDomain": {
    "model": "TEST Consensus Acute Toxicity",
    "version": "5.2.0",
    "range": {"lowerPercentile": 0.05, "upperPercentile": 0.95}
  }
}
```

Expected backend response:

```json
{
  "descriptorValues": {
    "logP": 2.1,
    "polarSurfaceArea": 48.0
  },
  "descriptorBounds": {
    "logP": {"lower": 0.0, "upper": 5.0},
    "polarSurfaceArea": {"lower": 10.0, "upper": 90.0}
  },
  "source": "chem-backend"
}
```

The sidecar still performs the pass/fail decision itself. The chemistry backend supplies numeric context; it does not replace the AD decision contract.

### Optional expert-rule backend

The sidecar now also supports the GenRA expert rule `Mode of action tags must align`.

Inline request context can be supplied as:

```json
{
  "chemical_identifier": "DTXSID000001",
  "ad_inputs": {
    "expert_rule": {
      "mode_of_action_tags": {
        "target_tags": ["pparg", "nuclear receptor"],
        "analogues": [
          {"id": "a1", "tags": ["pparg", "nuclear receptor"]},
          {"id": "a2", "tags": ["pparg"]}
        ]
      }
    }
  }
}
```

The allowable mismatch threshold comes from the AD definition’s `allowableMismatch`.

The sidecar can also derive these tags automatically from existing CompTox-style mechanistic evidence instead of requiring explicit tag lists. Supported derivation inputs include:

- `bioactivity_summary` / `bioactivitySummary`
- `aop_mappings` / `aopMappings`
- active assay rows carrying `geneSymbol`, `targetFamily`, `activityDirection`, or related fields

Example derived-context input:

```json
{
  "chemical_identifier": "DTXSID000001",
  "ad_inputs": {
    "expert_rule": {
      "mechanistic_context": {
        "target": {
          "bioactivity_summary": [
            {
              "geneSymbol": "PPARG",
              "targetFamily": "nuclear receptor",
              "activityDirection": "activation",
              "hitcall": 1
            }
          ],
          "aop_mappings": [
            {
              "eventLabel": "PPARG activation",
              "eventType": "molecular_initiating_event"
            }
          ]
        },
        "analogues": [
          {
            "id": "a1",
            "bioactivity_summary": [
              {
                "geneSymbol": "PPARG",
                "targetFamily": "nuclear receptor",
                "activityDirection": "activation",
                "hitcall": 1
              }
            ]
          }
        ]
      }
    }
  }
}
```

When this fallback is used, the AD result records `mechanisticDerivationUsed=true` and `ruleSource=derived:mechanistic_context`.

If you want the sidecar to fetch mechanistic context from a backend instead, configure:

- `EPACOMP_AD_RULE_BACKEND_URL`
- `EPACOMP_AD_RULE_BACKEND_TIMEOUT_SECONDS`
- `EPACOMP_AD_RULE_BACKEND_BEARER_TOKEN`
- `EPACOMP_AD_RULE_BACKEND_API_KEY`

The rule-backend request shape is:

```json
{
  "chemicalIdentifier": "DTXSID000001",
  "identifierType": "dtxsid",
  "rule": "Mode of action tags must align",
  "criterion": {
    "type": "expert_rule",
    "rule": "Mode of action tags must align",
    "allowableMismatch": 1
  },
  "applicabilityDomain": {
    "model": "GenRA Read-Across Workflow",
    "version": "2.1.0"
  },
  "expertRuleInputs": {}
}
```

Expected rule-backend response:

```json
{
  "ruleContext": {
    "mode_of_action_tags": {
      "target_tags": ["pparg", "nuclear receptor"],
      "analogues": [
        {"id": "a1", "tags": ["pparg", "nuclear receptor"]},
        {"id": "a2", "tags": ["pparg"]}
      ]
    }
  },
  "source": "mechanistic-backend"
}
```

As with the descriptor backend, the rule backend provides context only. The sidecar still owns the final expert-rule decision and records the source used for evaluation.

## Schema-validated HTTP usage

The predictive routers expose FastAPI endpoints that now validate every response against the JSON Schemas in `docs/contracts/schemas/predictive/`. This ensures downstream agents receive consistent envelopes regardless of which model produced the prediction.

### Predict endpoint example

Run the service locally only when working on the experimental predictive stack, then issue:

```bash
curl -s http://localhost:8000/test/predict \
  -H "Content-Type: application/json" \
  -d '{"chemical_identifier": "DTXSID7020182"}' | jq
```

Sample response (truncated for brevity):

```json
{
  "prediction": {
    "endpoint": "LD50",
    "value": 1.20,
    "units": "log(mmol/kg)"
  },
  "applicability_domain": {
    "in_domain": true,
    "confidence": 0.86,
    "details": {
      "policy": "block"
    }
  },
  "metadata": {
    "identifier": "DTXSID7020182",
    "identifier_type": "dtxsid",
    "model": "TEST Consensus Acute Toxicity",
    "model_version": "5.2.0"
  }
}
```

If the AD policy is `warn`, the router attaches `adWarning/adMessage` metadata; if the policy is `block`, the endpoint returns HTTP 400 with the policy error code.

### Applicability-domain check

```bash
curl -s http://localhost:8000/test/check_applicability_domain \
  -H "Content-Type: application/json" \
  -d '{"chemical_identifier": "DTXSID7020182"}' | jq
```

```json
{
  "in_domain": true,
  "confidence": 0.86,
  "details": {
    "policy": "block"
  }
}
```

Both responses are validated against `predictive/predict.response.schema.json` and `predictive/ad_check.response.schema.json` respectively, so any deviation from the contract is caught before the HTTP response is returned.
