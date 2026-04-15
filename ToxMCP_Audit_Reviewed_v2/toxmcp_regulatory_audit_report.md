# ToxMCP Suite - Regulatory Survivability Audit Report (Reviewed Copy)

**Review date:** 2026-04-15  
**Scope:** `comptox-mcp`, `oqt-mcp`, `aop-mcp`, `pbpk-mcp`  
**Frameworks considered in the original package:** OECD GLP / data integrity expectations, 21 CFR Part 11, Annex 11, related regulated-use controls

---

## Read this report carefully

This reviewed copy preserves the original regulatory concerns but narrows the claim style.

It uses the following rule:

> The package can strongly identify **compliance-relevant design gaps**.  
> It cannot, from the audit material alone, guarantee a specific regulator’s decision in a specific submission context.

So this report prefers phrasing such as:
- **high risk of non-conformance**
- **likely unacceptable without compensating controls**
- **insufficient for defensible reconstruction**

and avoids categorical claims such as:
- automatic FDA rejection
- automatic submission rejection

---

## Executive summary

The ToxMCP suite shows meaningful awareness of provenance and auditability, but the package still identifies several gaps that would matter for regulated or high-assurance use:

1. **Historical reconstruction is incomplete**  
   The package does not show a suite-wide, fully reconstructable provenance envelope.

2. **Audit trail semantics are not yet strong enough**  
   Several components rely on mechanisms that look audit-like but are not clearly tamper-evident end to end.

3. **Electronic review/signature semantics are under-specified**  
   Draft authorship, review, and approval lineage are not yet represented robustly enough for stronger assurance contexts.

4. **Determinism and version capture remain uneven**  
   Reproducibility depends on environment, data/version, ordering, and serialization choices that are not consistently captured.

### Overall judgment
**Regulatory survivability is currently limited by provenance, reconstruction, and review-state design more than by any single missing field.**

---

## Finding register

| ID | Finding | Severity | Evidence basis | Confidence | Reviewed interpretation |
|---|---|---|---|---|---|
| REG-01 | Historical reconstruction / “time-machine” capability is incomplete | **Critical** | Observed + inferred | High | Hard to defend what happened, with what versions and conditions, after the fact |
| REG-02 | Audit trails are present but not uniformly tamper-evident | **Critical** | Observed | High | Audit-looking records are not yet equivalent to stronger integrity controls |
| REG-03 | Review/signature semantics are too weak for higher-assurance use | **Critical** | Observed | High | Identity, meaning, and content binding need strengthening |
| REG-04 | Determinism and canonicalization are uneven | **High** | Observed | High | Reproducibility can drift across runtime/environment changes |
| REG-05 | Upstream provenance capture is incomplete | **Critical** | Observed + inferred | Medium-High | External data dependence is not consistently reconstructable |
| REG-06 | Cross-suite provenance contracts are not unified | **High** | Observed + inferred | Medium-High | Even good local controls can fail if downstream artifacts do not preserve them |

---

## REG-01: Historical reconstruction is incomplete
**Severity:** **Critical**  
**Evidence basis:** Observed + inferred  
**Confidence:** High

The package’s “time-machine” concern remains one of its strongest findings.

### Why this matters
For defensible historical reconstruction, the system needs a record of:
- code version / commit
- package and environment state
- upstream data/version context
- input identity resolution
- model/tool versions
- human review/approval status
- final artifact lineage

The audited material shows fragments of this, but not a single suite-wide mechanism that makes reconstruction routine.

### Reviewed wording
This is best framed as:
- **high risk of non-conformance for regulated or high-assurance use**
- **insufficient historical defensibility without compensating controls**

---

## REG-02: Audit records are not yet uniformly tamper-evident
**Severity:** **Critical**  
**Evidence basis:** Observed  
**Confidence:** High

The original package persuasively identified places where audit events or draft metadata can exist without:
- strong content binding
- mandatory previous-hash linkage
- verification on read
- clearly immutable storage semantics

### Why this matters
An audit record is much more useful than a plain log line, but it is not equivalent to a verified integrity chain unless:
- the canonicalized content is defined,
- the chain is mandatory,
- and verification is part of normal operation.

---

## REG-03: Electronic review/signature semantics are underdeveloped
**Severity:** **Critical**  
**Evidence basis:** Observed  
**Confidence:** High

The package correctly highlighted missing or weak semantics around:
- reviewer identity
- signature meaning
- timestamp discipline
- signature-to-content linkage
- role or approval state

### Reviewed wording
This is a **strong compliance gap finding**.  
It is not, on its own, proof of a specific regulator outcome without intended-use and procedure context.

### Practical implication
If the system is meant to support high-assurance draft approval or regulated record workflows, signature and approval state need to be explicit, verified, and preserved in lineage.

---

## REG-04: Determinism and canonicalization need more discipline
**Severity:** **High**  
**Evidence basis:** Observed  
**Confidence:** High

The package’s best examples here include:
- floating-point serialization for hashed records
- ordering assumptions in query results
- lack of explicit random-seed or environment recording

### Why this matters
Two scientifically “same” runs can become operationally non-identical if:
- ordering differs,
- float serialization differs,
- environment changes are not captured,
- or a downstream artifact is regenerated under slightly different conditions.

---

## REG-05: Upstream provenance capture remains too weak
**Severity:** **Critical**  
**Evidence basis:** Observed + inferred  
**Confidence:** Medium-High

The package is strong in pointing out that upstream data dependence must be represented, not assumed.

### Important refinement in the reviewed copy
The correct requirement is **not** “invent version headers.”  
The requirement is to capture the strongest provenance and replay information the upstream actually makes available, and to supplement it internally where needed.

That may include:
- provider release/version identifiers
- snapshot identifiers
- response hashes
- retrieval timestamps
- request parameters
- internal cache keys or mirror snapshots

---

## REG-06: Cross-suite provenance contracts need to be unified
**Severity:** **High**  
**Evidence basis:** Observed + inferred  
**Confidence:** Medium-High

Local compliance-minded controls are less useful if downstream repos cannot reliably preserve:
- provenance fields
- review state
- uncertainty state
- version metadata
- signed-artifact lineage

This is where the regulatory and contract-layer audits reinforce each other.

---

## Recommended control architecture

### 1. Suite-wide provenance envelope
A single record model carried across repos, including:
- input identity
- upstream retrieval data
- code/runtime snapshot
- tool outputs and hashes
- review and approval state
- artifact lineage

### 2. Verified audit chain
Separate from ordinary developer logging:
- canonical event schema
- mandatory chaining
- content recomputation
- immutable or append-controlled storage semantics
- automated verification tests

### 3. Explicit review/signature model
For higher-assurance flows:
- actor identity
- role
- meaning
- time
- content linkage
- revocation or supersession model

---

## What to validate next

- intended regulated-use context for each repo and output type
- what external procedural controls already exist
- how draft approval is meant to work in practice
- which provenance fields survive cross-repo handoffs
- whether deterministic hashing and ordering assumptions hold across environments

---

## Final judgment

The original package was right to focus on provenance, reconstruction, and review-state design.  
Those remain the most important regulatory-survivability concerns in the suite.

**Bottom line:** the package strongly supports the claim that ToxMCP still needs a more robust integrity and provenance model before it can be treated as ready for regulated or similarly high-assurance use.
