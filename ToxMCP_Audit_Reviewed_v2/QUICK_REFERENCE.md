# ToxMCP Audit Quick Reference (Reviewed Copy)

**Purpose:** Fast triage for engineering and leadership  
**How to read this page:** It prioritizes what to fix first, not what to claim most loudly.

---

## Top cross-suite items

| Rank | Finding | Primary repos | Severity | Evidence basis | Confidence | First action |
|---|---|---|---|---|---|---|
| 1 | Historical reconstruction and provenance gaps | All | **Critical** | Observed + inferred | High | Define a single provenance envelope and capture code/data/runtime versions at workflow start |
| 2 | No mandatory scientific review checkpoints in high-risk flows | `oqt-mcp`, cross-suite | **Critical** | Observed + inferred | High | Add explicit pause-and-approve checkpoints before predictive and reporting steps |
| 3 | Unsafe interpolation / trust-boundary handling | `aop-mcp`, `oqt-mcp` | **Critical / High** | Observed + scenario | High / Medium | Remove structural query interpolation; isolate untrusted identifiers from prompts |
| 4 | Resource-control and resilience gaps | `pbpk-mcp`, `aop-mcp` | **High** | Observed | High | Add quotas, circuit breaker behavior, and load-test-derived defaults |
| 5 | Auditability and traceability gaps | All | **High** | Observed + inferred | High | Propagate a single trace ID and emit replayable provenance records |
| 6 | Cross-suite orchestration responsibility is documented but not implemented | All | **High** | Observed + inferred | Medium-High | Define orchestration ownership, evidence deduplication, and contradiction handling |

---

## Repo-by-repo first moves

### `comptox-mcp`
1. Capture upstream provenance in a way the provider actually supports
2. Replace audit-log fallback behavior with a tamper-evident trail design
3. Add retry jitter/backoff and document supported MCP transport/version strategy

### `oqt-mcp`
1. Enforce applicability-domain gates, not just narrative AD summaries
2. Add mandatory human review checkpoints and stronger PDF provenance defaults
3. Treat chemical identifiers as untrusted text when crossing LLM or agent boundaries

### `aop-mcp`
1. Remove arbitrary query-shape interpolation; use allow-listed query plans and safe binding
2. Add resilience controls for SPARQL upstream failure
3. Tighten draft-signature and checksum-chain semantics

### `pbpk-mcp`
1. Enforce parameter bounds and log parameter sweeps
2. Add population and memory quotas with tested defaults
3. Improve reproducibility metadata and deterministic event hashing

---

## What changed in the reviewed copy

- absolute phrases were softened to match evidence
- remediation code is now framed as **reference code**
- future-proofing language was updated to current MCP public context
- validation gaps were moved into an explicit backlog

See:
- `AUDIT_EVIDENCE_FRAMEWORK.md`
- `REVISION_LOG.md`
- `VALIDATION_BACKLOG.md`

---

## Items to validate before external circulation

| Finding | Why validation is needed |
|---|---|
| SPARQL injection | Need to confirm actual runtime-controlled fields and endpoint permissions |
| Prompt injection via identifiers | Need a real prompt-boundary trace, not only a scenario |
| Regulated-use compliance gaps | Need intended-use and procedural-control context |
| Upstream version pinning | Need to verify what external providers actually expose |
| Population/OOM thresholds | Need measurements on representative infrastructure |

---

## Recommended sequence

### Week 0: package hygiene
- adopt the reviewed copy
- assign owners
- turn critical findings into tracked work items
- agree on validation criteria

### Week 1-2: hard controls
- OQT AD gating and review checkpoints
- AOP query safety and circuit breaking
- PBPK parameter/resource controls
- CompTox provenance capture and audit trail hardening

### Week 3-4: shared architecture
- provenance envelope
- distributed tracing
- orchestration/evidence broker
- fix validation tests

---

## One-line posture

**Strong internal audit and planning pack; not yet a reproduced external assurance package.**
