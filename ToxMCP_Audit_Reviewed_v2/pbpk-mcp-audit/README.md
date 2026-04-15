# PBPK-MCP Audit Package (Reviewed Copy)

**Repository:** `pbpk-mcp`  
**Package version cited in original audit:** `v0.4.3`  
**Review date:** 2026-04-15  
**Overall posture:** **High risk for scientific guardrails and runtime stability**

---

## How to read this reviewed copy

The original package’s best PBPK findings were about:
- scientifically meaningful parameter control
- resource limits for large simulations
- reproducibility metadata
- runtime isolation and operational hardening

This reviewed copy keeps those findings, but reduces overstatement where exploitability or infrastructure specifics were not validated.

---

## Finding register

| ID | Finding | Severity | Evidence basis | Confidence | Reviewed interpretation |
|---|---|---|---|---|---|
| PBPK-01 | Parameter changes need stronger physiological bounds and sweep governance | **Critical** | Observed + inferred | High | Unreviewed parameter exploration can bias conclusions |
| PBPK-02 | Population-size and memory controls are insufficiently explicit | **Critical** | Observed | High | Large jobs can plausibly destabilize workers without enforced limits |
| PBPK-03 | Reproducibility metadata and deterministic hashing need improvement | **High** | Observed | High | Historical comparability and event integrity are weaker than intended |
| PBPK-04 | Container/runtime hardening needs a clearer threat model and stronger controls | **High** | Observed + scenario | Medium | Important, but severity depends on actual deployment/runtime permissions |
| PBPK-05 | Queueing and availability protections deserve explicit load-test validation | **High** | Observed + inferred | Medium-High | Failure under stress is plausible and should be measured |

---

## Detailed findings

### PBPK-01: Parameter editing needs governance, not only validation
**Severity:** **Critical**  
**Evidence basis:** Observed + inferred  
**Confidence:** High

The original package correctly identified a domain-specific risk that many generic software audits would miss:  
a parameter-editing API can become a vehicle for selective tuning until a preferred outcome appears.

### Why this matters
Even if each individual parameter change is syntactically valid, the workflow still needs:
- physiological plausibility bounds
- actor/reason capture
- sweep detection
- explicit review requirements when repeated tuning occurs

### Recommended control
- bounds database curated with domain-owner review
- change audit trail with before/after values and rationale
- heuristic or rule-based sweep detection
- stronger review requirements when model outputs change materially after repeated edits

---

### PBPK-02: Resource controls should be measured and enforced
**Severity:** **Critical**  
**Evidence basis:** Observed  
**Confidence:** High

The package’s central concern is sound: large population simulations can exhaust memory or queue capacity without explicit control points.

### Reviewed wording
The exact OOM threshold depends on:
- model complexity
- output retention strategy
- worker memory size
- parallelism settings

So the reviewed copy avoids wording like "certain OOM" unless infrastructure measurements support it.

### Recommended control
- hard upper bounds on population size
- memory/CPU quotas
- per-job estimates before execution
- streaming or chunked result handling where feasible
- defaults based on benchmarked infrastructure, not only estimates

---

### PBPK-03: Reproducibility needs a fuller provenance envelope
**Severity:** **High**  
**Evidence basis:** Observed  
**Confidence:** High

The original package was right to emphasize that reproducibility is not just about input values. It also depends on:
- model version
- runtime environment
- floating-point serialization
- seeds and stochastic settings
- artifact generation behavior

### Recommended control
- canonical serialization for hashed events
- explicit handling for float edge cases
- runtime snapshot capture
- clear distinction between scientific result hash and audit-event hash

---

### PBPK-04: Runtime isolation should be threat-model driven
**Severity:** **High**  
**Evidence basis:** Observed + scenario  
**Confidence:** Medium

Container hardening and file/runtime isolation matter here, especially if the system ingests untrusted files or executes complex scientific tooling.  
The original package likely overstated certainty for some escape scenarios, but it was directionally right to treat runtime hardening as important.

### Recommended control
- confirm actual trust boundaries for uploaded files and model assets
- run with least privilege
- document seccomp/AppArmor/SELinux or equivalent controls where used
- separate build-time privilege needs from runtime privilege needs

---

### PBPK-05: Availability and queue behavior need explicit validation
**Severity:** **High**  
**Evidence basis:** Observed + inferred  
**Confidence:** Medium-High

The original package’s DoS and queue-flooding concerns are plausible. The right next step is not stronger rhetoric; it is measurement.

### Recommended control
- representative load tests
- queue depth and age limits
- cancellation/timeout policy
- clear partial-failure behavior
- telemetry for memory, queue delay, retries, and worker saturation

---

## Recommended sequence

### Immediate
- parameter bounds and sweep governance
- population and memory limits
- deterministic hashing improvements

### Next
- runtime hardening review
- load tests and quota tuning
- provenance envelope alignment with the rest of the suite

---

## Validation backlog specific to this repo

- benchmark population-size vs memory/latency on representative workers
- validate deterministic hashing across platforms and Python versions
- review runtime/file ingestion threat model
- confirm how repeated parameter changes are surfaced to reviewers

---

## Related documents

- `ToxMCP_Performance_Resilience_Audit_Report.md`
- `toxmcp_regulatory_audit_report.md`
- `toxmcp_adversarial_audit_report.md`
- `pbpk-mcp-audit/REMEDIATION_CODE.md`
