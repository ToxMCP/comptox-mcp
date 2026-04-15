# ToxMCP Ecosystem - Comprehensive Adversarial Audit Report (Reviewed Copy)

**Review date:** 2026-04-15  
**Scope:** `comptox-mcp`, `oqt-mcp`, `aop-mcp`, `pbpk-mcp`  
**Intended use:** Internal planning, engineering prioritization, stakeholder briefing

---

## Review status

This reviewed copy preserves the original package’s core concerns while tightening:
- evidentiary language
- severity calibration
- remediation phrasing
- package-level consistency

It should be read together with:
- `AUDIT_EVIDENCE_FRAMEWORK.md`
- `REVISION_LOG.md`
- `VALIDATION_BACKLOG.md`

---

## Executive judgment

The ToxMCP audit bundle is **strong as an internal red-team and architecture review**, especially where it identifies cross-cutting risks around provenance, uncertainty, orchestration, and scientist-facing misuse.

The reviewed copy does **not** treat the package as a finished external audit. A number of findings remain best framed as:
- observed implementation gaps,
- architecture inferences,
- or scenario-based exploit narratives that still require reproduction.

### Bottom-line rating

| Use case | Assessment |
|---|---|
| Internal remediation planning | **Strong** |
| Cross-team prioritization | **Strong** |
| Leadership briefing | **Strong** |
| External diligence without further validation | **Limited** |
| Formal assurance / submission support | **Not yet** |

---

## Why the package is still valuable

The most important insight in the original work was correct: the main failure modes are not only classic software bugs. They are also:

- missing time-machine reconstruction
- confidence without calibration
- outputs that look authoritative without enough provenance
- cross-tool contradictions that no component is responsible for resolving
- uncertainty that grows across the workflow but is never represented explicitly

Those are real and important system-level risks for a toxicology workflow stack.

---

## Evidence and confidence summary

| ID | Finding | Severity | Evidence basis | Confidence | Reviewed wording |
|---|---|---|---|---|---|
| M-01 | Historical reconstruction and provenance gaps | **Critical** | Observed + inferred | High | High risk of being unable to reconstruct past outputs in a defensible way |
| M-02 | Missing or weak human review checkpoints in high-risk flows | **Critical** | Observed + inferred | High | High risk of false confidence and unreviewed downstream reporting |
| M-03 | Unsafe trust-boundary handling in query/prompt paths | **Critical / High** | Observed + scenario | High / Medium | Unsafe interpolation patterns are present; exploitability depends on actual runtime data flow |
| M-04 | No shared cross-suite orchestration / contradiction handling layer | **High** | Observed + inferred | Medium-High | Responsibility is documented but not implemented in the audited material |
| M-05 | Resource-control and resilience gaps | **High** | Observed | High | Service instability or degraded scientific throughput is plausible under stress |
| M-06 | Auditability, replay, and observability gaps | **High** | Observed + inferred | High | Debugging and post-hoc verification are materially harder than they should be |
| M-07 | Schema / protocol / ontology evolution risk | **High** | Observed + standards note | Medium-High | Migration cost is likely to be high without shared abstraction and versioning discipline |

---

## System-level findings

### M-01: Provenance and reconstruction are not yet first-class

Across the package, the strongest repeated concern is not merely "missing logs." It is the absence of a single, defensible record of:

- code version
- runtime environment
- input identity resolution
- upstream data/version context
- model/tool version
- human review state
- final signed or approved output

This matters because toxicology workflows often need more than replay. They need a **reconstructable explanation of what happened, when, with which inputs, under which software and data conditions**.

**Why this remains Critical:**  
The reviewed copy still considers this a critical suite-level gap because it affects integrity, auditability, and the ability to defend historical outputs.

**What changed in the wording:**  
The original package sometimes implied automatic regulatory failure. The reviewed copy instead states that this gap creates a **high risk of non-conformance and defensibility failure for regulated use**, subject to intended use and any external procedural controls.

---

### M-02: Human review is not reliably embedded where it matters most

The package is persuasive when it shows how scientist-facing automation can move from:
chemical identification → predictive tooling → PDF/report artifact  
without clearly enforced review checkpoints.

The issue is not that automation exists. The issue is that the package shows too many places where the workflow can appear "finished" before:
- chemical identity is confirmed
- applicability-domain boundaries are accepted
- contradictory evidence is surfaced
- confidence language is reviewed by a human

**Why this remains Critical:**  
Because the scientific and regulatory risk is not just wrong output; it is **wrong output wrapped in a professional-looking artifact**.

---

### M-03: Trust-boundary handling needs to be reworked, not just patched

Two areas matter here:

#### SPARQL/query safety
The audited material shows string-template interpolation for queries. That is a real code smell.  
However, the reviewed copy avoids overstating destructive impact unless runtime permissions and update semantics are known. The safest defensible claim is:

> unsafe interpolation is observed; query broadening, unauthorized data exposure, or result manipulation are plausible; destructive effects depend on endpoint permissions and whether update-capable operations are reachable.

#### Prompt/instruction boundary safety
The package also reasonably flags that chemical identifiers and similar text fields may cross into LLM- or agent-facing contexts.  
But the reviewed copy treats full prompt injection as **scenario-dependent** until the exact prompt boundary is demonstrated.

**Practical implication:**  
These should still be treated as near-term remediation items, because the mitigation cost is lower than the cost of being wrong later:
- bind literals safely
- allow-list structural query choices
- isolate untrusted text from system instructions
- prefer structured tool arguments over interpolated natural language

---

### M-04: Cross-suite orchestration responsibility is missing

This remains one of the most original and useful findings in the bundle.

The issue is not merely that there is no single "orchestrator service" file. It is that the audited material repeatedly implies a higher layer is responsible for:

- evidence deduplication
- contradiction detection
- cross-module narrative coherence
- schema translation and version negotiation
- final dossier assembly

Yet that responsibility is not concretely implemented in the package.

**Why this matters:**  
Without an explicit owner for cross-tool reasoning, each repo can be locally correct while the suite-level story is inconsistent.

---

### M-05: Resilience gaps are likely to surface under real load

The package identifies several plausible service-stability issues:
- no clear circuit-breaker behavior for SPARQL-like upstream failure paths
- insufficient quotas for large PBPK workloads
- retry logic that may amplify load
- limited replay/diff tooling for diagnosing divergent results

The reviewed copy retains these as **High** rather than inflating every one to Critical, because actual severity depends on deployment size, workload mix, and whether external infrastructure already enforces limits.

---

### M-06: Observability and replayability are under-designed

The original observability audit made a strong point: the suite is difficult to debug as a system, not just as four independent repos.

The most important issues are:
- no single trace across tools
- insufficient replay artifacts
- limited diffability of outputs
- incomplete privacy/sensitivity handling in logs

This is more than an operational inconvenience. It slows incident response, scientific debugging, and compliance evidence gathering.

---

### M-07: Future-proofing risk is real, but should be framed as migration resilience

The original package correctly identified fragmentation around:
- transport handling
- schema versioning
- ontology evolution
- provider coupling

The reviewed copy updates the framing: these are not just "future features missing." They are **migration resilience risks**.  
That is the more durable claim.

---

## Cross-cutting bridge components still worth building

The original master report recommended architectural bridge components. That remains the right direction.

### 1. Provenance and evidence ledger
A suite-wide component that records:
- input identity resolution
- upstream retrieval metadata
- code/runtime snapshot
- tool outputs and hashes
- review checkpoints
- final artifact lineage

### 2. Orchestration and evidence-broker layer
A single place to handle:
- schema mediation
- contradiction detection
- evidence deduplication
- confidence/uncertainty aggregation
- final narrative assembly rules

### 3. Policy and safe-execution layer
A shared layer for:
- authorization and review policies
- prompt/query trust-boundary handling
- rate limits and quotas
- audit and trace propagation
- secure offline/controlled execution modes where required

---

## Priority remediation plan

### Wave 0 - package hygiene and governance
- adopt this reviewed copy as the working baseline
- assign repo owners for each critical item
- agree on validation criteria before external use
- stop describing snippets as production-ready code

### Wave 1 - hard controls
- OQT: applicability-domain gating, review checkpoints, safer report defaults
- AOP: query safety redesign and resilience controls
- PBPK: bounds, quotas, and reproducibility metadata
- CompTox: provenance capture and tamper-evident audit design

### Wave 2 - shared architecture
- provenance envelope
- trace propagation
- orchestration/evidence broker
- schema/version registry decisions

### Wave 3 - external defensibility
- live-repo revalidation
- proof-of-concept or deterministic reasoning notes for each critical item
- fix verification tests
- commit or permalink references

---

## What should not be claimed yet

Until the validation backlog is complete, avoid saying that the package has already demonstrated:
- formal exploit reproduction for all security findings
- conclusive regulatory rejection outcomes
- production-ready remediation patches
- complete live-repo verification

---

## Final assessment

The original package had the right instincts and several genuinely strong insights.  
The reviewed copy makes it safer and more useful by separating:
- what is directly observed,
- what is inferred,
- and what remains a scenario that should be validated.

**Bottom line:** this is a strong internal audit and remediation planning bundle, and now a better one. It is still one validation step away from being an externally defensible assurance artifact.
