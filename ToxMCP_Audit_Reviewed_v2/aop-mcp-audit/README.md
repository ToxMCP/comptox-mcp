# AOP-MCP Audit Package (Reviewed Copy)

**Repository:** `aop-mcp`  
**Package version cited in original audit:** `v0.8.1`  
**Review date:** 2026-04-15  
**Overall posture:** **High-to-critical for trust-boundary safety, draft integrity, and ontology evolution**

---

## How to read this reviewed copy

The original package correctly identified `aop-mcp` as an integration-heavy surface where:
- query safety
- upstream resilience
- draft/signature integrity
- ontology/schema drift

all matter at once.

This reviewed copy retains those concerns, but is stricter about exploit claims:
- **Observed** unsafe interpolation patterns are treated as hard findings
- destructive outcomes such as graph deletion are treated as **scenario-dependent** unless endpoint permissions are known

---

## Finding register

| ID | Finding | Severity | Evidence basis | Confidence | Reviewed interpretation |
|---|---|---|---|---|---|
| AOP-01 | Unsafe query templating / interpolation | **Critical** | Observed + scenario | High / Medium | A trust-boundary issue is present; exact exploit impact depends on runtime-controlled fields and endpoint permissions |
| AOP-02 | Upstream query failure handling lacks mature resilience controls | **High** | Observed | High | Failure cascades and latency amplification are plausible |
| AOP-03 | Draft metadata and signature semantics are not strong enough for high-assurance review flows | **Critical** | Observed | High | Review and approval lineage is weaker than it should be |
| AOP-04 | Checksum-chain verification needs stronger content binding and write/read validation | **Critical** | Observed | High | Draft history is not yet as tamper-evident as intended |
| AOP-05 | Ontology/version drift can break cross-suite meaning over time | **High** | Observed + inferred | Medium-High | Migration and comparability risk is real |

---

## Detailed findings

### AOP-01: Query templating should be redesigned around allow-listed query plans
**Severity:** **Critical**  
**Evidence basis:** Observed + scenario  
**Confidence:** High for unsafe interpolation, Medium for worst-case exploit impact

The package shows template rendering through Python string formatting. That is a legitimate trust-boundary concern.

### Reviewed wording
The safest defensible statement is:

> query construction includes unsafe interpolation patterns; query broadening, result manipulation, or unintended data exposure are plausible if structural fragments can be influenced by untrusted input.

Avoid assuming destructive update operations unless the endpoint is confirmed to allow them.

### Better mitigation pattern
Do **not** treat arbitrary query fragments as bindable parameters.

Use:
- fixed query templates selected from an allow-list
- safe binding only for literals/URIs
- allow-listed sort and limit options
- separate read-only query builders from any update-capable code path

---

### AOP-02: Upstream resilience controls are underdeveloped
**Severity:** **High**  
**Evidence basis:** Observed  
**Confidence:** High

The original package’s concern about circuit breaking, backoff, and graceful degradation remains sound.  
If the AOP upstream is unavailable or slow, repeated retries can amplify latency and user confusion.

### Recommended control
- bounded retries with jitter
- circuit-breaker/open-state behavior
- explicit error surface to callers
- cache or partial-result policy where scientifically acceptable
- telemetry for endpoint health and fallback path usage

---

### AOP-03: Draft approval semantics are not yet strong enough
**Severity:** **Critical**  
**Evidence basis:** Observed  
**Confidence:** High

The original package was right to highlight that draft metadata and authorship fields do not, by themselves, constitute strong review or approval lineage.

### Recommended control
- strong actor identity linkage
- signature meaning (`authored`, `reviewed`, `approved`, `rejected`)
- UTC timestamping
- content-hash binding
- verified chain between successive draft versions

### Reviewed wording
Use: **high risk of non-conformance for regulated or high-assurance review workflows**  
Avoid: categorical claims of inevitable regulatory outcome.

---

### AOP-04: Checksum verification should prove content integrity, not only compare stored values
**Severity:** **Critical**  
**Evidence basis:** Observed  
**Confidence:** High

A checksum field is helpful only when:
- the checksum is mandatory
- the algorithm is defined
- the content used to compute it is canonicalized
- the chain is verified on read
- mutations cannot silently sever lineage

This remains a strong and useful finding from the original pack.

---

### AOP-05: Ontology and schema drift need an explicit migration strategy
**Severity:** **High**  
**Evidence basis:** Observed + inferred  
**Confidence:** Medium-High

`aop-mcp` sits near an evolving ontology surface. That means long-lived interoperability requires more than normalization at read time.

### Recommended control
- record ontology/version provenance in artifacts
- maintain deprecation and remapping tables
- define migration tests for cross-suite schemas
- avoid burying semantic version assumptions inside tool logic

---

## Recommended sequence

### Immediate
- redesign unsafe query construction
- add resilience controls around SPARQL/upstream failure
- strengthen draft metadata and checksum semantics

### Next
- formalize ontology/version provenance
- add migration tests and compatibility policy
- align traceability with suite-wide provenance model

---

## Validation backlog specific to this repo

- confirm which query components can be influenced by untrusted input at runtime
- confirm endpoint permissions and whether any update semantics are reachable
- test checksum recomputation from draft content
- verify how ontology version changes propagate into downstream consumers

---

## Related documents

- `toxmcp_security_audit_report.md`
- `toxmcp_contract_audit_report.md`
- `toxmcp_regulatory_audit_report.md`
- `aop-mcp-audit/REMEDIATION_CODE.md`
