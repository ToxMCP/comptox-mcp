# ToxMCP Suite - Adversarial Security Audit Report (Reviewed Copy)

**Review date:** 2026-04-15  
**Scope:** `comptox-mcp`, `oqt-mcp`, `aop-mcp`, `pbpk-mcp`  
**Purpose:** Identify trust-boundary, availability, and integrity risks relevant to toxicology workflows

---

## Read this report carefully

The original security report had strong instincts but sometimes overstated exploit certainty.  
This reviewed copy keeps the high-value findings while making the following distinction explicit:

- **Observed:** insecure pattern directly visible in the audited material
- **Scenario:** plausible exploit or misuse path that depends on runtime preconditions
- **Operational consequence:** what the issue could mean in production if those preconditions hold

This report is therefore more conservative in wording, not weaker in substance.

---

## Executive summary

The most important security issues in the package are:

1. **Unsafe interpolation at trust boundaries**  
   Especially around query/template construction and any path where untrusted identifiers may influence model-facing text.

2. **Weak provenance/integrity controls around upstream dependence**  
   The suite relies on external sources and intermediate transformations that are not always strongly verifiable afterward.

3. **Insufficient resilience and rate/quotas for expensive operations**  
   Availability and integrity interact here: unstable systems are harder to trust and easier to misuse.

### Security posture after review
- **Critical findings remain:** yes
- **But some original exploit narratives are better read as scenarios:** also yes

---

## Finding register

| ID | Finding | Severity | Evidence basis | Confidence | Reviewed interpretation |
|---|---|---|---|---|---|
| SEC-01 | Unsafe query interpolation in `aop-mcp` | **Critical** | Observed + scenario | High / Medium | The pattern is real; exact exploit effect depends on which query parts are attacker-influenced and what the endpoint allows |
| SEC-02 | Untrusted identifier handling across prompt/agent boundaries | **High** | Observed + scenario | Medium | Important to mitigate now, even though full exploit demonstration still needs runtime tracing |
| SEC-03 | Upstream integrity/provenance controls are uneven | **High** | Observed + inferred | Medium | External dependence needs stronger internal verification and capture |
| SEC-04 | Authorization / workflow escalation surfaces deserve targeted review | **Medium / High** | Observed + inferred | Medium | Needs live-repo validation before stronger claims |
| SEC-05 | Resource exhaustion and denial-of-service paths are plausible | **High** | Observed | High | Large simulations, retries, or missing quotas can destabilize the system |
| SEC-06 | Offline / controlled-execution posture is underdefined | **High** | Observed + inferred | Medium | Important for high-assurance deployments and incident containment |

---

## SEC-01: Unsafe query interpolation in `aop-mcp`
**Severity:** **Critical**  
**Evidence basis:** Observed + scenario  
**Confidence:** High for the unsafe pattern; Medium for worst-case impact

The original package showed string-based templating for query generation. That is a valid high-priority security finding.

### What is directly supported
- query templates are rendered through string formatting
- this is unsafe if structural query fragments or control fields are influenced by untrusted input

### What should be stated more carefully
The reviewed copy avoids assuming destructive update outcomes such as graph deletion unless the runtime path and endpoint permissions are known.

### Better statement
> Unsafe interpolation is present. Depending on runtime data flow, this could permit query broadening, result manipulation, data exposure, or other unintended graph access. Destructive effects depend on whether update-capable operations are reachable.

### Correct mitigation pattern
Do not try to “sanitize everything” with regexes alone.

Instead:
- use fixed, allow-listed query plans
- bind only literals/URIs
- keep `ORDER BY`, `LIMIT`, graph patterns, and predicates on allow-lists
- separate read-only query paths from any privileged/update path

---

## SEC-02: Untrusted identifiers may influence model-facing text
**Severity:** **High**  
**Evidence basis:** Observed + scenario  
**Confidence:** Medium

The original report was directionally right to worry about prompt or instruction confusion from chemical names and related fields.  
The reviewed copy treats the full jailbreak claim as scenario-dependent until the exact prompt boundary is demonstrated.

### Why it still matters now
Because mitigation is relatively cheap and scientifically sensible:
- normalize Unicode
- strip control characters for LLM-facing contexts
- avoid passing free text directly into system or tool instructions
- carry identifiers as structured data
- regression-test with adversarial names and notes

### Important correction
Simple keyword blocking is not enough.  
The primary control should be **prompt structure and boundary isolation**, not only blacklists.

---

## SEC-03: Upstream integrity controls are uneven
**Severity:** **High**  
**Evidence basis:** Observed + inferred  
**Confidence:** Medium

The original report identified a real issue: results derived from upstream APIs or knowledge sources can be difficult to verify later if provenance is weak.

### Reviewed refinement
The right mitigation is not to assume that all providers support response signing.  
A better hierarchy of controls is:
1. authenticated transport where available
2. source/provenance capture
3. request/response hashing
4. internal caching or mirroring for replay
5. cross-source consistency checks for high-value conclusions
6. provider-side signing **if actually supported**

---

## SEC-04: Authorization and workflow escalation need targeted validation
**Severity:** **Medium / High**  
**Evidence basis:** Observed + inferred  
**Confidence:** Medium

The original report’s concern about permission boundaries remains useful, but this is an area where live-repo validation matters.  
Configuration alone is rarely enough to prove exploitability.

### What to verify
- how permissions are enforced at runtime
- whether tool composition can bypass intended gates
- which roles can launch expensive, destructive, or approval-relevant flows
- whether audit records capture denied and elevated actions

---

## SEC-05: DoS and exhaustion paths are plausible
**Severity:** **High**  
**Evidence basis:** Observed  
**Confidence:** High

The package identifies multiple cost-amplifying patterns:
- large PBPK workloads
- retry behavior on failing upstreams
- insufficient quotas or admission control
- incomplete cancellation/timeout semantics

These are not “mere performance issues.”  
In an analytical system, prolonged instability becomes a security and integrity problem because it encourages retries, bypasses, stale-data usage, and partial-result acceptance.

---

## SEC-06: Controlled/offline execution posture should be made explicit
**Severity:** **High**  
**Evidence basis:** Observed + inferred  
**Confidence:** Medium

The original report usefully raised the question of “secure mode” or constrained execution, but the reviewed copy frames it more practically:

- Which repos can operate without live external dependencies?
- Which assets must be mirrored or pre-approved?
- What logging, auth, and approval rules change in controlled mode?
- What is the incident-response posture if a supplier or upstream becomes untrusted?

This is important for regulated, confidential, or degraded-network settings.

---

## Attack-chain view

The original report’s attack chains were helpful conceptually. The reviewed copy keeps the model but phrases them as **scenario compositions**, not proof.

### Example composite scenario
1. untrusted identifier or query input crosses a weak boundary  
2. upstream retrieval/provenance is weak  
3. review checkpoints are missing or optional  
4. a polished artifact is produced  
5. the resulting conclusion appears more trustworthy than its evidence warrants

This is the core systemic security theme of the suite: **false confidence plus weak verification**.

---

## Immediate actions

1. **Fix trust-boundary handling**
   - query allow-lists
   - structured prompt inputs
   - control-character stripping for model-facing fields

2. **Improve provenance and integrity capture**
   - response hashes
   - retrieval metadata
   - clear actor/review state

3. **Add quotas and resilience controls**
   - population/job limits
   - bounded retries
   - circuit breakers
   - cancellation semantics

4. **Validate authorization pathways**
   - runtime permission tests
   - escalation-path review
   - denial auditability

---

## Final judgment

The original package correctly identified that ToxMCP’s biggest security risks are not only perimeter vulnerabilities. They are failures at **trust boundaries, provenance boundaries, and review boundaries**.

**Bottom line:** the reviewed copy supports several strong security findings, especially around query safety, prompt-boundary hygiene, upstream integrity capture, and exhaustion control. Some exploit narratives remain scenario-based and should be validated against the live repositories before external use.
