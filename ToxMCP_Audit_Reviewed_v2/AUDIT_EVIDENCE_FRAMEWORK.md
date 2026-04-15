# ToxMCP Audit Evidence Framework

**Added in reviewed copy:** 2026-04-15  
**Purpose:** Make the package easier to defend internally and safer to reuse externally.

---

## Why this document exists

The original audit pack was strong on systems thinking, but it mixed together three different claim types:

1. **Directly observed code/schema facts**
2. **Architecture-level inferences**
3. **Scenario-based exploit or misuse narratives**

Those are all useful, but they should not be presented with the same certainty. This framework standardizes how the reviewed copy uses evidence, confidence, and severity language.

---

## Evidence taxonomy

| Label | Meaning | Typical example | How to read it |
|---|---|---|---|
| **Observed** | Directly quoted or paraphrased from code, schema, configuration, or documentation contained in the audited material | A function uses `str.format()` on a query template; a schema omits a required provenance field | Strongest class of claim in this package |
| **Observed + inferred** | A direct observation supports a broader architecture conclusion | Independent per-repo correlation IDs imply no end-to-end distributed trace | Usually strong, but still one step removed from a direct test |
| **Scenario** | A misuse or exploit path that depends on stated preconditions | A prompt-injection payload alters downstream reasoning *if* untrusted identifiers are interpolated into model prompts without isolation | Useful for threat modeling, not proof that exploitation was demonstrated |
| **Standards note** | A statement about a regulatory or protocol expectation from a public standard or guidance | Signature/record linking expectations under 21 CFR Part 11 | Read with deployment and intended-use context in mind |

---

## Confidence scale

| Confidence | Meaning |
|---|---|
| **High** | The claim is strongly grounded in the supplied material or an official standard, and only limited interpretation is required |
| **Medium** | The claim is plausible and supported, but exploitability, operational impact, or scope depends on assumptions that have not yet been validated |
| **Low** | The claim is directionally useful for red-teaming, but needs reproduction or source-repo verification before being presented as a hard finding |

---

## Severity language rules used in the reviewed copy

### Critical
Use only when the package shows a gap that is both material and near-core to the intended operating model, for example:
- integrity of scientific outputs
- inability to reconstruct or sign regulated records
- unbounded execution that can predictably destabilize the service
- unsafe interpolation at a trust boundary

### High
Use when the gap is significant, but one or more of these remains true:
- exploitability depends on preconditions
- compensating procedural controls may exist
- impact is serious but not necessarily suite-blocking

### Medium
Use when the gap is real but better framed as a design weakness, future migration cost, or a finding that still needs validation.

---

## Claim phrasing rules

The reviewed copy avoids the following unless directly demonstrated and scoped:

- "FDA rejection"
- "submission rejection"
- "certain"
- "production-ready code"
- destructive exploit claims such as graph deletion unless the endpoint is known to permit updates

Instead, the package prefers wording such as:

- "high risk of non-conformance for regulated use"
- "likely unacceptable for submission without compensating controls"
- "observed unsafe interpolation pattern"
- "reference implementation / implementation pattern"

---

## Validation states

Each major finding should eventually be paired with one or more of these:

| Validation state | Meaning |
|---|---|
| **Reproduced** | A proof of concept or deterministic reproduction exists |
| **Source-verified** | The claim was re-checked against the live repository, not just this audit bundle |
| **Fix-verified** | The proposed remediation was tested and shown to change behavior as intended |
| **Still open** | Needs follow-up before external use |

This reviewed copy improves wording and internal consistency, but it does **not** claim that all findings were reproduced or re-verified against the live repositories.

---

## Minimal standard before external use

Before using any finding externally, the package should include:

1. exact repository or commit reference
2. reproduction or test preconditions
3. expected behavior vs observed behavior
4. exploitability caveats
5. fix validation criteria

Until then, this package is best treated as a **carefully edited internal audit and remediation planning pack**.
