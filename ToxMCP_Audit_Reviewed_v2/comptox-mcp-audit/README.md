# CompTox-MCP Audit Package (Reviewed Copy)

**Repository:** `comptox-mcp`  
**Package version cited in original audit:** `v0.2.2`  
**Review date:** 2026-04-15  
**Overall posture:** **High risk for defensibility and provenance**, more than for classic appsec

---

## How to read this reviewed copy

This summary is designed to be safer to circulate internally than the original draft.

- **Observed** means the claim is grounded in the supplied audit material.
- **Observed + inferred** means the material supports a broader architecture conclusion.
- **Scenario** means the issue is threat-model relevant but still needs runtime validation.

This is **not** a live-repo re-audit. Line references were inherited from the supplied package.

---

## Finding register

| ID | Finding | Severity | Evidence basis | Confidence | Reviewed interpretation |
|---|---|---|---|---|---|
| CTX-01 | Upstream provenance / version capture is not first-class | **Critical** | Observed + inferred | Medium-High | Historical outputs may be hard to defend if provider versions or snapshots are not recorded |
| CTX-02 | Audit trail can fall back to ordinary logging semantics | **Critical** | Observed | High | Tamper evidence and reconstruction are weaker than they should be |
| CTX-03 | Retry strategy lacks mature backoff/jitter guidance | **High** | Observed | Medium | Could amplify upstream instability under load |
| CTX-04 | Transport and protocol handling is locally implemented | **High** | Observed | Medium-High | Migration cost and consistency risk increase as MCP evolves |
| CTX-05 | Upstream data integrity relies heavily on external providers | **High** | Scenario | Medium | Provenance and consistency controls should not depend on unsupported supplier features |

---

## Why this repo matters in the suite

`comptox-mcp` is a provenance-sensitive edge of the ToxMCP system because it often sits near:
- upstream evidence retrieval
- identity resolution and hazard context
- hand-off into downstream reasoning

That means small omissions here can cascade into larger suite-level defensibility gaps later.

---

## Detailed findings

### CTX-01: Upstream provenance / version capture is incomplete
**Severity:** **Critical**  
**Evidence basis:** Observed + inferred  
**Confidence:** Medium-High

The original audit correctly flagged that the package does not clearly show a robust mechanism to record:
- upstream provider version or release identifier
- data snapshot or retrieval timestamp
- request parameters used
- response hash or cache key
- how that metadata is persisted into downstream workflow records

### Reviewed wording
The strongest defensible claim is **not** that every upstream supports strict version pinning.  
It is that the current package does not show a reliable suite-level way to **capture and replay upstream provenance**.

### Recommended control
Use the strongest control the provider actually supports:
1. if the provider exposes a version/snapshot selector, record and enforce it
2. if not, capture request URL, query params, retrieval time, response hash, and cache identity
3. persist that metadata into the workflow/provenance envelope
4. prefer an internal retrieval proxy if deterministic replay is a requirement

> Do **not** assume that custom headers like `X-API-Version` or `X-Data-Snapshot` are supported unless the upstream provider documents them.

---

### CTX-02: Audit trail design is weaker than required for defensibility
**Severity:** **Critical**  
**Evidence basis:** Observed  
**Confidence:** High

The original audit’s concern about fallback-to-logging behavior remains strong. If audit events can devolve into ordinary logs without:
- chain validation
- content-addressed records
- user/session context
- immutable or append-controlled storage semantics

then the resulting trail is unlikely to support strong post-hoc reconstruction.

### Reviewed wording
Use: **high risk of non-conformance for regulated or high-assurance use**  
Avoid: automatic claims of guaranteed regulatory rejection.

### Recommended control
- define a canonical audit-event envelope
- include prior hash / content hash
- bind event to actor, session, tool, input identity, and upstream provenance
- verify the chain on read, not only on write

---

### CTX-03: Retry behavior can worsen upstream instability
**Severity:** **High**  
**Evidence basis:** Observed  
**Confidence:** Medium

This is a classic operational risk rather than a unique toxicology issue. Without jitter, bounded retries, and explicit failure-mode policy, a stressed upstream can trigger synchronized retries and unpredictable latency.

### Recommended control
- exponential backoff with jitter
- hard retry caps
- surface upstream instability in provenance and alerts
- decide explicitly whether failures should be cached, retried later, or returned as partial results

---

### CTX-04: Transport/protocol logic is fragmented
**Severity:** **High**  
**Evidence basis:** Observed  
**Confidence:** Medium-High

The original package was directionally correct: local protocol handling increases long-term migration and consistency cost.

### Recommended control
- centralize transport/version handling in a shared package or shared adapter layer
- keep server logic separate from transport concerns
- make capability/version negotiation testable at the boundary

---

### CTX-05: Upstream integrity should not rely on unsupported supplier-side signing
**Severity:** **High**  
**Evidence basis:** Scenario  
**Confidence:** Medium

The original audit’s concern about supplier dependence is valid, but the reviewed copy tightens the mitigation guidance.

### Better control pattern
Prefer this order of controls:
1. TLS and authenticated transport where available
2. request/response provenance capture
3. cached response hashing
4. consistency checks across time or across sources for high-value conclusions
5. provider-side signatures **only if the provider actually supports them**

---

## Recommended sequence

### Immediate
- define the provenance fields that downstream repos must receive from `comptox-mcp`
- harden audit-event structure
- add retry jitter/backoff

### Next
- align transport/version handling with the suite
- define provider capability matrix for versioning/snapshots
- add fix verification tests for audit chain and provenance persistence

---

## Validation backlog specific to this repo

- verify what upstream services actually expose for version or snapshot control
- confirm where provenance fields are persisted and consumed downstream
- test audit chain recomputation from stored content
- load-test retry behavior against realistic upstream failures

---

## Related documents

- `TOXMCP_MASTER_AUDIT_REPORT.md`
- `toxmcp_regulatory_audit_report.md`
- `toxmcp_future_proofing_audit_report.md`
- `comptox-mcp-audit/REMEDIATION_CODE.md`
