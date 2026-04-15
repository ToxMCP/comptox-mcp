# ToxMCP Observability & Debuggability Audit Report

**Audit Date:** 2026-04-15  
**Auditor:** Observability & Debuggability Specialist  
**Scope:** comptox-mcp, oqt-mcp, aop-mcp, pbpk-mcp  
**Severity Legend:** 🔴 Critical | 🟠 High | 🟡 Medium | 🟢 Low

---

> **Reviewed copy (2026-04-15):** This document was retained from the original package but lightly edited for consistency.  
> Unless explicitly stated otherwise, code blocks are **reference implementations**, not validated patches, and scenario-based exploit narratives should not be read as reproduced proofs.



## Executive Summary

This audit reveals **significant observability gaps** across the ToxMCP ecosystem that will make production debugging extremely difficult. The most critical issues are:

1. **No distributed tracing** - Cross-tool workflows are untraceable
2. **Missing feature attribution** - The "Why" gap makes classification results unexplainable
3. **No PII/PSI scrubbing** - Proprietary chemical structures logged in plaintext
4. **No replay capability** - Cannot debug without re-running expensive simulations
5. **No result diff tooling** - Divergent results cannot be analyzed

**Debuggability Debt Score: 8.5/10 (Critical)**

---

## Finding 1: The 'Why' Gap - Missing Feature Attribution 🔴 CRITICAL

### Description
When O-QT returns a classification like "Class 1 (narcosis or baseline toxicity)", there is **no explanation of which molecular features triggered this classification**. The response contains only the classification result without feature-level attribution.

### Evidence

**File:** `oqt-mcp/src/tools/implementations/o_qt_qsar_tools.py` (lines 311-393)

```python
async def run_qsar_prediction(smiles: str, model_id: str) -> dict:
    """Runs a QSAR prediction."""
    # ... fetch prediction ...
    result = {
        "chem_id": chem_id,
        "model_id": model_id,
        "prediction": prediction,  # <-- Contains ONLY the result, not WHY
        "domain": domain,
        "search_hits": hits,
    }
```

The `prediction` object from the QSAR Toolbox API contains:
- `Value`: The predicted value
- `Unit`: The unit of measurement
- `DomainResult`: In/out of domain status
- **Missing:** Which molecular features contributed to this prediction
- **Missing:** Feature importance scores
- **Missing:** Structural alerts triggered

### Concrete Example

**Current Response:**
```json
{
  "prediction": {
    "Value": "Class 1",
    "DomainResult": "Inside applicability domain"
  },
  "model_provenance": {
    "title": "Verhaar Scheme for predicting toxicity mode of action"
  }
}
```

**What Scientists Need:**
```json
{
  "prediction": {
    "Value": "Class 1",
    "DomainResult": "Inside applicability domain",
    "feature_attribution": {
      "triggered_rules": [
        {
          "rule_id": "VERHAAR_001",
          "description": "Non-reactive organic compound with logKow > 2.0",
          "confidence": 0.94,
          "contributing_fragments": ["C-C", "C-H"],
          "molecular_features": {
            "logKow": 3.2,
            "reactive_groups": []
          }
        }
      ],
      "explanation": "Class 1 assigned due to non-reactive nature and moderate lipophilicity consistent with narcosis mechanism"
    }
  }
}
```

### Impact
- **Regulatory Rejection:** Agencies (EPA, ECHA) require explainable predictions
- **Scientific Distrust:** Users cannot validate or challenge results
- **Debugging Impossibility:** When results are wrong, cannot determine if it's data issue, model issue, or bug

### Cross-References
- Related to: Finding 4 (Replay Without Re-execution) - Cannot debug what you cannot explain
- Related to: Finding 5 (Result Diff) - Cannot diff without feature-level comparison

### Recommendation
1. Extend `hazard_contracts.py` to include `feature_attribution` field
2. Parse profiler alerts from Toolbox response to extract triggered rules
3. Add `explain_prediction()` tool that returns human-readable rationale

---

## Finding 2: Cross-Tool Tracing - No Distributed Trace IDs 🔴 CRITICAL

### Description
When a user runs a workflow that hits CompTox → O-QT → AOP, there is **no distributed trace ID that links all three calls**. Each MCP server generates its own isolated correlation ID, making it impossible to see the full request graph.

### Evidence

**File:** `oqt-mcp/src/api/server.py` (lines 95-118)

```python
@app.middleware("http")
async def audit_log_middleware(request: Request, call_next):
    correlation_id = str(uuid.uuid4())  # <-- NEW UUID FOR EVERY REQUEST
    request.state.correlation_id = correlation_id
    # ...
    response.headers["X-Request-ID"] = correlation_id
```

**File:** `aop-mcp/src/server/mcp/router.py` (lines 57-118)

```python
async def mcp_endpoint(request: Request, response: Response):
    # No correlation ID extraction from incoming request!
    payload = await request.json()
    # ...
```

**File:** `comptox-mcp/src/epacomp_tox/orchestrator/workflow.py` (lines 68-206)

```python
def run_workflow(self, ..., workflow_run_id: Optional[str] = None):
    run_id = workflow_run_id or str(uuid4())  # <-- Local only, not propagated
    # No tracing context propagation to O-QT or AOP
```

### The Problem

```
User Request
    │
    ├──► CompTox-MCP [X-Request-ID: abc-123]
    │      └──► Calls O-QT API [X-Request-ID: def-456]  ← NEW ID!
    │
    ├──► O-QT-MCP [X-Request-ID: ghi-789]  ← NEW ID!
    │
    └──► AOP-MCP [X-Request-ID: jkl-012]  ← NEW ID!

Result: Cannot correlate the full workflow!
```

### What Should Happen (OpenTelemetry/W3C Trace Context)

```
User Request [trace-id: abc-123, span-id: xyz]
    │
    ├──► CompTox-MCP [trace-id: abc-123, span-id: comp-1]
    │      └──► Calls O-QT API [trace-id: abc-123, span-id: oqt-1, parent: comp-1]
    │
    ├──► O-QT-MCP [trace-id: abc-123, span-id: oqt-2, parent: xyz]
    │
    └──► AOP-MCP [trace-id: abc-123, span-id: aop-1, parent: xyz]

Result: Full request graph visible in Jaeger/Zipkin!
```

### Impact
- **No End-to-End Visibility:** Cannot trace a chemical through the entire analysis pipeline
- **Latency Attribution Impossible:** Cannot determine which tool is causing slowdowns
- **Error Propagation Opaque:** Errors in one tool appear as failures in another

### Cross-References
- Related to: Finding 5 (Result Diff) - Cannot correlate divergent results across tools

### Recommendation
1. Implement W3C Trace Context propagation (`traceparent` header)
2. Add OpenTelemetry SDK to all MCP servers
3. Deploy Jaeger/Zipkin for distributed tracing visualization
4. Add span IDs to all log entries

---

## Finding 3: Log Privacy Leakage - No PII/PSI Scrubbing 🔴 CRITICAL

### Description
Toxicological data can be proprietary (new drug candidates). The logs capture **chemical structures (SMILES) and CAS numbers in plaintext** with no PII/PSI (Proprietary Substance Information) scrubbing filters.

### Evidence

**File:** `oqt-mcp/src/tools/implementations/o_qt_qsar_tools.py` (lines 311-315)

```python
async def run_qsar_prediction(smiles: str, model_id: str) -> dict:
    log.info(
        f"Running QSAR prediction for SMILES: {smiles[:20]}... using model: {model_id}"
    )  # <-- SMILES LOGGED IN PLAINTEXT!
```

**File:** `oqt-mcp/src/tools/registry.py` (lines 135-157)

```python
# CRITICAL: This should be handled by a dedicated, immutable audit service in production
# Ensure PII/Sensitive data in params is sanitized before logging if necessary.
try:
    logged_params = json.dumps(params, default=str, indent=2)[:500]  # <-- NO SANITIZATION!
except Exception:
    logged_params = "Params serialization failed"

audit.emit(
    {
        "type": "tool_execution",
        "tool": name,
        "user_id": user.id,
        "status": "success",
        "params": logged_params,  # <-- CONTAINS SMILES, CAS, CHEMICAL NAMES!
    }
)
```

**File:** `oqt-mcp/src/api/server.py` (lines 95-118)

```python
async def audit_log_middleware(request: Request, call_next):
    # ...
    event = {
        "type": "http_request",
        "correlation_id": correlation_id,
        "user_id": user_id,
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code,
        "duration_ms": round(duration_ms, 3),
        # <-- NO SCRUBBING OF REQUEST BODY!
    }
    audit.emit(event)
```

### Concrete Privacy Leak Example

**Log Entry (Current):**
```json
{
  "timestamp": "2026-04-15T10:30:00Z",
  "level": "INFO",
  "message": "Running QSAR prediction for SMILES: CC(C)Cc1ccc...",
  "params": {
    "smiles": "CC(C)Cc1ccc(C(C)C(=O)O)cc1",  # <-- IBUPROFEN STRUCTURE!
    "chemical_identifier": "15687-27-1",  # <-- CAS NUMBER!
    "preferred_name": "Ibuprofen"  # <-- DRUG NAME!
  }
}
```

**What It Should Be (Scrubbed):**
```json
{
  "timestamp": "2026-04-15T10:30:00Z",
  "level": "INFO",
  "message": "Running QSAR prediction for SMILES: [REDACTED]...",
  "params": {
    "smiles_hash": "sha256:a3f5c8...",  # <-- HASH ONLY
    "chemical_identifier": "[REDACTED]",
    "preferred_name": "[REDACTED]",
    "_debug": "PII scrubbed - see secure vault for original"
  }
}
```

### Impact
- **Regulatory Violation:** GDPR, CCPA, and pharma confidentiality agreements breached
- **IP Theft Risk:** Competitors can extract chemical structures from logs
- **Audit Failure:** Compliance audits will flag this as critical finding

### Cross-References
- Related to: Finding 1 (Why Gap) - Feature attribution requires chemical data, creating tension with privacy

### Recommendation
1. Implement `PrivacyScrubber` class with regex patterns for:
   - SMILES strings
   - CAS numbers
   - InChI/InChIKey
   - Chemical names (dictionary-based)
2. Hash chemical identifiers for correlation without exposure
3. Store original values in encrypted sidecar for authorized debugging
4. Add `X-Confidentiality-Level` header to control scrubbing per-request

---

## Finding 4: Replay Without Re-execution - No Record Mode 🟠 HIGH

### Description
There is **no 'record mode' that caches deterministic responses**. Developers cannot replay an exact MCP tool call from last Tuesday without re-running the expensive simulation.

### Evidence

**File:** `oqt-mcp/src/qsar/client.py` (lines 55-165)

```python
async def _request(self, method, path, *, params=None, json=None, ...):
    # No caching layer!
    # No VCR/recording mechanism!
    async def _execute_request():
        # ... makes live HTTP request every time ...
```

**File:** `aop-mcp/src/instrumentation/cache.py` (lines 1-47)

```python
class InMemoryCache(Cache):
    """Simple cache abstraction with in-memory implementation."""
    # Only used for SPARQL query caching, not for:
    # - Tool call recording
    # - Response replay
    # - Deterministic debugging
```

**File:** `comptox-mcp/src/epacomp_tox/orchestrator/workflow.py` (lines 350-378)

```python
def _persist_bundle(self, bundle, ...):
    # Saves bundle AFTER execution
    # No recording of intermediate steps
    # No ability to replay from checkpoint
```

### The Problem

**Scenario:** A scientist reports: "Last Tuesday, O-QT said this chemical was Class 2, but today it says Class 1. Why?"

**Current Debugging Process:**
1. Re-run the same query → May get different result (data drift?)
2. Check logs → No feature attribution (Finding 1)
3. Check cross-tool trace → No trace ID (Finding 2)
4. **Result:** Cannot determine cause of divergence

**What Should Exist:**
```python
# Record mode for deterministic replay
@record_replay(cache_dir=".vcr_cassettes")
async def run_qsar_prediction(smiles: str, model_id: str) -> dict:
    # First call: Records to .vcr_cassettes/qsar_abc123.yaml
    # Subsequent calls: Replays from cassette (no API call!)
    ...
```

### Impact
- **Debugging Cost:** Each debug session requires expensive re-execution
- **Non-Determinism:** Cannot distinguish between data drift and bugs
- **Regression Testing:** Cannot verify fixes without live APIs

### Cross-References
- Related to: Finding 1 (Why Gap) - Replay without explanation is insufficient
- Related to: Finding 5 (Result Diff) - Replay enables diff comparison

### Recommendation
1. Integrate VCR.py for HTTP recording/replay
2. Add `TOXMCP_RECORD_MODE` environment variable
3. Store cassettes with versioning for regression testing
4. Add `replay_from_cassette()` helper for debugging

---

## Finding 5: Result Diff Tool - No Divergence Analysis 🟠 HIGH

### Description
When two scientists get different results for the same query, there is **no 'result diff' tool** to determine if it's data drift, model drift, hardware floating-point differences, or a bug.

### Evidence

**Search Results:** No `diff`, `compare`, `divergence`, or `regression` tools found in any repository.

**File:** `comptox-mcp/src/epacomp_tox/orchestrator/audit.py` (lines 1-99)

```python
class AuditBundleStore:
    """Durable storage for orchestrator audit bundles."""
    
    def save(self, bundle, *, attachments=None):
        # Saves bundles with checksums
        # No comparison/diff functionality!
    
    def load_bundle(self, run_id: str) -> Dict[str, any]:
        # Loads single bundle
        # No cross-run comparison!
```

**File:** `pbpk-mcp/docs/mcp-bridge/audit-trail.md` (lines 94-98)

```markdown
## Verification Tools
- `audit verify --from 2025-10-16` – Streams events, recomputes hash chain
- `audit replay --job job-uuid` – Reconstructs timeline for a specific job
# <-- NO `audit diff` TOOL!
```

### What Should Exist

```python
class ResultDiffer:
    """Compare two workflow results to identify divergence."""
    
    def diff(self, run_id_a: str, run_id_b: str) -> DivergenceReport:
        return {
            "divergence_type": "MODEL_DRIFT",  # or DATA_DRIFT, BUG, HARDWARE_FP
            "confidence": 0.94,
            "differences": [
                {
                    "path": "predictive.results[0].prediction.Value",
                    "old": "Class 2",
                    "new": "Class 1",
                    "explanation": "Model version changed from 2.1 to 2.2"
                }
            ],
            "root_cause": {
                "type": "model_update",
                "details": "Verhaar scheme updated 2025-01-10"
            }
        }
```

### Impact
- **Scientific Disagreements:** Cannot resolve "I got different results" issues
- **Regression Detection:** Cannot detect when updates break existing analyses
- **Data Quality:** Cannot identify upstream data changes

### Cross-References
- Related to: Finding 1 (Why Gap) - Diff requires feature-level comparison
- Related to: Finding 4 (Replay) - Diff requires ability to replay old results

### Recommendation
1. Create `toxmcp-diff` CLI tool
2. Implement semantic diff for chemical predictions
3. Add divergence classification (data vs model vs bug)
4. Integrate with audit bundle storage

---

## Finding 6: Missing Structured Health/Metrics Endpoints 🟡 MEDIUM

### Description
Only O-QT has a basic health endpoint. No comprehensive metrics for monitoring tool success rates, latency percentiles, or error rates.

### Evidence

**File:** `oqt-mcp/src/api/server.py` (lines 135-142)

```python
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "environment": settings.app.ENVIRONMENT,
        "auth_bypassed": settings.security.BYPASS_AUTH,
        "qsar_api_url": settings.qsar.QSAR_TOOLBOX_API_URL,
    }
```

**Missing:**
- Tool success/error rates
- Latency histograms
- Queue depth (for async jobs)
- External dependency health (QSAR Toolbox, CompTox API)

### Recommendation
1. Add Prometheus metrics endpoint (`/metrics`)
2. Export key metrics:
   - `toxmcp_tool_invocations_total` (counter with tool, status labels)
   - `toxmcp_tool_duration_seconds` (histogram)
   - `toxmcp_external_api_health` (gauge)

---

## Finding 7: Inconsistent Audit Event Schemas 🟡 MEDIUM

### Description
Each MCP server uses a different audit event schema, making centralized analysis impossible.

### Evidence

**O-QT:** `oqt-mcp/src/tools/registry.py`
```python
audit.emit({
    "type": "tool_execution",
    "tool": name,
    "user_id": user.id,
    "status": "success",
    "params": logged_params,
})
```

**AOP-MCP:** `aop-mcp/src/instrumentation/audit.py`
```python
# Only verifies draft checksums, no event emission!
def verify_audit_chain(draft: Draft) -> bool:
    ...
```

**CompTox:** `comptox-mcp/src/epacomp_tox/orchestrator/audit.py`
```python
# File-based bundle storage, no structured events
class AuditBundleStore:
    def save(self, bundle, *, attachments=None):
        ...
```

### Recommendation
1. Define unified `ToxMcpAuditEvent` schema
2. Include: timestamp, trace_id, tool_name, user_id, duration, status, checksums
3. Implement in shared library across all MCP servers

---

## Finding 8: No Floating-Point Determinism Controls 🟡 MEDIUM

### Description
No controls for ensuring floating-point determinism across different hardware/platforms.

### Impact
- Results may differ between Intel vs AMD, or CPU vs GPU
- Cannot reproduce results on different deployments

### Recommendation
1. Document FP precision requirements
2. Add `deterministic_mode` flag for critical calculations
3. Use fixed-precision libraries where appropriate

---

## Summary Table

| Finding | Severity | Component | Effort to Fix |
|---------|----------|-----------|---------------|
| 1. Why Gap | 🔴 Critical | O-QT | 2-3 weeks |
| 2. Cross-Tool Tracing | 🔴 Critical | All | 1-2 weeks |
| 3. Log Privacy | 🔴 Critical | All | 1 week |
| 4. Replay Mode | 🟠 High | All | 2 weeks |
| 5. Result Diff | 🟠 High | All | 2-3 weeks |
| 6. Health/Metrics | 🟡 Medium | All | 3-5 days |
| 7. Audit Schema | 🟡 Medium | All | 1 week |
| 8. FP Determinism | 🟡 Medium | CompTox | 1 week |

---

## Debuggability Debt Quantification

| Category | Debt Score | Justification |
|----------|------------|---------------|
| Explainability | 9/10 | No feature attribution anywhere |
| Traceability | 8/10 | No distributed tracing, isolated correlation IDs |
| Privacy | 9/10 | Plaintext chemical structures in logs |
| Reproducibility | 8/10 | No record/replay, cannot debug without re-execution |
| Comparability | 8/10 | No diff tools for divergence analysis |
| **Overall** | **8.5/10** | **Critical debuggability debt** |

---

## Priority Recommendations

### Immediate (Week 1-2)
1. **Implement PII/PSI scrubbing** - Critical regulatory/compliance risk
2. **Add distributed trace context propagation** - Enable end-to-end visibility

### Short-term (Week 3-4)
3. **Add feature attribution to O-QT responses** - Enable explainability
4. **Implement VCR recording/replay** - Enable deterministic debugging

### Medium-term (Month 2)
5. **Build result diff tool** - Enable divergence analysis
6. **Unify audit event schemas** - Enable centralized monitoring

---

## Appendix: File References

### O-QT MCP
- `oqt-mcp/src/tools/implementations/o_qt_qsar_tools.py` - Main QSAR tools
- `oqt-mcp/src/tools/hazard_contracts.py` - Response contract builders
- `oqt-mcp/src/tools/provenance.py` - Provenance tracking
- `oqt-mcp/src/tools/registry.py` - Tool execution & audit logging
- `oqt-mcp/src/api/server.py` - HTTP server & middleware
- `oqt-mcp/src/qsar/client.py` - QSAR Toolbox API client
- `oqt-mcp/src/utils/audit.py` - Audit event emission
- `oqt-mcp/src/utils/logging.py` - Structured logging setup

### AOP MCP
- `aop-mcp/src/server/mcp/router.py` - MCP request routing
- `aop-mcp/src/instrumentation/audit.py` - Draft audit chain verification
- `aop-mcp/src/instrumentation/cache.py` - In-memory caching
- `aop-mcp/src/instrumentation/metrics.py` - Basic metrics recording
- `aop-mcp/src/instrumentation/logging.py` - Structured logging

### CompTox MCP
- `comptox-mcp/src/epacomp_tox/orchestrator/workflow.py` - Workflow orchestration
- `comptox-mcp/src/epacomp_tox/orchestrator/audit.py` - Audit bundle storage
- `comptox-mcp/src/epacomp_tox/orchestrator/utils.py` - Metadata sanitization

### PBPK MCP
- `pbpk-mcp/docs/mcp-bridge/audit-trail.md` - Audit trail design document
- `pbpk-mcp/docs/mcp-bridge/monitoring.md` - Monitoring design document

---

*End of Report*
