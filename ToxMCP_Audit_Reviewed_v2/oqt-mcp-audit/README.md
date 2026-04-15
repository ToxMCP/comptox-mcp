# OQT-MCP Audit Package (Reviewed Copy)

**Repository:** `oqt-mcp`  
**Package version cited in original audit:** `v0.3.0`  
**Review date:** 2026-04-15  
**Overall posture:** **Critical for scientific review governance and output framing**

---

## How to read this reviewed copy

The strongest findings in `oqt-mcp` are not generic appsec findings. They are about:
- scientific review workflow design
- applicability-domain enforcement
- how confidence and provenance are communicated to users
- whether untrusted identifiers cross into agent or LLM contexts safely

This reviewed copy keeps those concerns, but distinguishes between:
- **Observed** implementation gaps
- **Observed + inferred** user-risk conclusions
- **Scenario** exploit narratives that still need prompt-boundary validation

---

## Finding register

| ID | Finding | Severity | Evidence basis | Confidence | Reviewed interpretation |
|---|---|---|---|---|---|
| OQT-01 | Applicability-domain checks are too easy to treat as narrative metadata | **Critical** | Observed + inferred | High | Out-of-domain predictions may be surfaced without hard workflow friction |
| OQT-02 | High-risk flows do not appear to require human review by default | **Critical** | Observed + inferred | High | Wrong identity or weak evidence can propagate into polished outputs |
| OQT-03 | PDF/report defaults do not foreground provenance and uncertainty strongly enough | **Critical** | Observed + inferred | High | Artifacts may look more final than they are |
| OQT-04 | Untrusted identifiers may cross into prompt/agent contexts without enough isolation | **High** | Observed + scenario | Medium | Needs runtime prompt-boundary validation, but deserves near-term mitigation |
| OQT-05 | Logs may capture sensitive identifiers too directly | **High** | Observed | High | Privacy/confidentiality controls need strengthening |
| OQT-06 | Workflow permissions and escalation paths deserve review | **Medium / High** | Observed + inferred | Medium | Important, but needs live-repo validation before stronger claims |

---

## Why this repo is central

`oqt-mcp` is where scientific judgment can become visually convincing very quickly.  
That makes it the most important place to embed:
- review checkpoints
- explicit uncertainty language
- provenance defaults
- safe handling of user-supplied identifiers

---

## Detailed findings

### OQT-01: Applicability-domain logic should gate decisions, not merely decorate them
**Severity:** **Critical**  
**Evidence basis:** Observed + inferred  
**Confidence:** High

The original package persuasively showed that AD information exists, but can still be treated as a side note rather than a decision gate.

### Why this matters
A user can be shown:
- a prediction value
- a confidence-ish narrative
- a professional artifact

without a strong enough system-level interruption when the chemical is poorly represented by the model domain.

### Recommended control
- introduce an explicit AD decision object
- separate `inside_domain`, `outside_domain`, and `unknown`
- require acknowledgement or manual approval before downstream reporting when outside or unknown
- carry AD status into every artifact header and summary

---

### OQT-02: Human review checkpoints should be first-class
**Severity:** **Critical**  
**Evidence basis:** Observed + inferred  
**Confidence:** High

The package’s original finding remains strong: a workflow that can proceed from search to output artifact with minimal user intervention is a governance risk in scientific settings.

### Minimum checkpoints worth enforcing
1. identity resolution / substance confirmation
2. applicability-domain assessment
3. final narrative/report approval

### Reviewed wording
The issue is not "automation is bad."  
The issue is that **automation without explicit review-state transitions can create false confidence**.

---

### OQT-03: Output defaults over-signal finality
**Severity:** **Critical**  
**Evidence basis:** Observed + inferred  
**Confidence:** High

The original audit’s criticism of “audit-ready” style outputs remains valid. Even when technically true that a PDF was generated, the user experience can imply:
- completeness
- validated provenance
- reviewed interpretation
- stable confidence

before those conditions are satisfied.

### Recommended control
Make the artifact itself carry its uncertainty:
- provenance table in the first page or header section
- model/tool versions
- AD status and warnings
- explicit human-review state
- draft / reviewed / approved marker
- unresolved evidence gaps section

---

### OQT-04: Treat chemical identifiers as untrusted text at LLM boundaries
**Severity:** **High**  
**Evidence basis:** Observed + scenario  
**Confidence:** Medium

The original package may have overstated exploit certainty, but it identified the right boundary.  
If chemical names, aliases, notes, or free-text identifiers are interpolated into prompts or agent instructions without structure, instruction confusion becomes plausible.

### Better mitigation than simple keyword blocking
- normalize Unicode
- remove control characters for LLM-facing contexts, including newlines unless explicitly needed
- pass identifiers as structured data, not concatenated prose
- visually and logically separate system instructions from user-supplied fields
- add regression tests with adversarial identifiers

### Important nuance
This should be treated as **high priority** even before full exploitation is demonstrated, because the cost of safer prompt construction is modest.

---

### OQT-05: Logging needs a stronger privacy model
**Severity:** **High**  
**Evidence basis:** Observed  
**Confidence:** High

The package’s privacy concern remains well supported. If identifiers, SMILES, or other sensitive fields are logged directly, confidentiality can be compromised even when the core workflow is correct.

### Recommended control
- classify fields by sensitivity
- hash or tokenize where operationally acceptable
- separate immutable audit records from developer/debug logs
- define retention and access boundaries

---

## Recommended sequence

### Immediate
- AD gating with explicit workflow consequences
- mandatory review checkpoints
- stronger artifact provenance and review state labeling
- prompt-boundary hardening for untrusted identifiers

### Next
- privacy-aware logging
- clearer permission model review
- validation tests covering wrong-identity and out-of-domain paths

---

## Validation backlog specific to this repo

- confirm prompt/agent boundary for all identifier-bearing fields
- test AD gating with representative in-domain / out-of-domain / ambiguous compounds
- validate PDF/report UX with scientist users
- review permission and escalation paths in the live repository

---

## Related documents

- `cognitive_ergonomics_audit_report.md`
- `toxmcp_adversarial_audit_report.md`
- `toxmcp_security_audit_report.md`
- `oqt-mcp-audit/REMEDIATION_CODE.md`
