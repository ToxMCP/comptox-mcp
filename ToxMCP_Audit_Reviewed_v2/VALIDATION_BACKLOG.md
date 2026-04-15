# ToxMCP Audit Validation Backlog

**Purpose:** Convert the reviewed audit pack into a more externally defensible package.

---

## Priority 0 - validation required before external sharing

| ID | Finding | What to validate | Output needed |
|---|---|---|---|
| V0-1 | SPARQL unsafe interpolation | Confirm whether structural query fragments, `ORDER BY`, `LIMIT`, or graph patterns can be influenced by untrusted input at runtime | Minimal PoC, affected code path, safe-vs-unsafe query examples |
| V0-2 | Prompt / instruction injection via chemical identifiers | Trace whether untrusted identifiers are interpolated into model prompts or agent instructions without structured isolation | Prompt boundary diagram, example payload, before/after mitigation test |
| V0-3 | Part 11 / Annex 11 readiness gap | Confirm intended regulated use, signature requirements, and whether procedural controls already exist outside the repos | Control mapping, gap matrix, intended-use memo |
| V0-4 | Upstream provenance/version capture | Verify what the external providers actually expose for versioning, snapshots, and response metadata | Provider capability matrix, proposed internal pinning strategy |
| V0-5 | Population/OOM thresholds | Run controlled load tests on representative worker sizes | Memory/latency curves, safe defaults, enforced limits |

---

## Priority 1 - should be reproduced soon

| ID | Finding | What to validate | Output needed |
|---|---|---|---|
| V1-1 | Audit chain integrity | Recompute hashes from stored content and confirm mismatch behavior | Unit/integration tests |
| V1-2 | Deterministic hashing for PBPK events | Cross-platform serialization check for floats, NaN, infinity, and ordering | Regression test matrix |
| V1-3 | Distributed tracing gap | Run a multi-tool workflow and confirm whether a single trace can be reconstructed | Trace propagation test |
| V1-4 | Scientific review checkpoints | Confirm that high-risk workflow states can be paused, reviewed, and resumed cleanly | UX flow and test cases |
| V1-5 | Container/runtime hardening risk | Validate actual attack surface for file parsing, package installation, and runtime privileges | Threat model plus runtime config review |

---

## Priority 2 - packaging and governance

| ID | Task | Why it matters |
|---|---|---|
| V2-1 | Replace inherited line references with live-repo permalinks or commit hashes | External readers can verify claims |
| V2-2 | Add fix verification criteria to each critical item | Prevents “remediation theater” |
| V2-3 | Create a machine-readable finding register | Easier tracking across repos |
| V2-4 | Add sign-off owners and due dates | Turns the pack into an execution tool |

---

## Suggested working rule

Do not present a finding as externally validated until it has:
1. a code or config location in the live repository
2. stated preconditions
3. a reproduction or reasoning note
4. a test for the proposed fix
