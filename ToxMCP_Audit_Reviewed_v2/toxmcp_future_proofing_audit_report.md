# ToxMCP Suite - Future-Proofing & Standards Audit Report (Reviewed Copy)

**Review date:** 2026-04-15  
**Scope:** `comptox-mcp`, `oqt-mcp`, `aop-mcp`, `pbpk-mcp`  
**Focus:** Migration resilience for MCP, schema evolution, ontology drift, and provider coupling

---

## Important update in this reviewed copy

The original report treated streaming and transport changes as mostly future events.  
This reviewed copy updates the framing:

- Streamable HTTP is already part of the public MCP specification lineage.
- The current public MCP roadmap is focused on **evolving transport and session handling for scale**, not on introducing a large set of new official transports.
- The highest-value future-proofing question for ToxMCP is therefore **migration resilience**, not speculative feature timing.

---

## Executive summary

The original package correctly identified that the suite has several durability risks:

1. **Transport/protocol logic is fragmented across repos**
2. **Schema/version handling is inconsistent**
3. **Ontology evolution is under-governed**
4. **Provider and model coupling is stronger than ideal**
5. **Binary/large artifact handling is not abstracted cleanly enough**

These are best understood as **migration-cost multipliers**.  
Even if every repo works today, the cost of adapting the suite to protocol, ontology, or provider change may be much higher than it needs to be.

---

## Finding register

| ID | Finding | Severity | Evidence basis | Confidence | Reviewed interpretation |
|---|---|---|---|---|---|
| FUT-01 | MCP transport handling is too repo-local | **High** | Observed | High | Transport change will likely require repeated work unless abstraction is shared |
| FUT-02 | Capability/version negotiation strategy is underdefined | **High** | Observed + standards note | Medium-High | Compatibility drift is likely as clients and servers evolve |
| FUT-03 | Schema evolution and registry discipline are insufficient | **High** | Observed | High | Cross-suite breakage risk grows as contracts change |
| FUT-04 | Ontology/version drift is under-managed | **High** | Observed + inferred | Medium-High | Historical comparability and interoperability may degrade over time |
| FUT-05 | Provider/model coupling is stronger than ideal | **Medium / High** | Observed | Medium-High | Supplier or API change could have outsized migration cost |
| FUT-06 | Binary/large artifact handling needs a clearer boundary | **Medium / High** | Observed + inferred | Medium | Performance and compatibility cost can rise as outputs get richer |

---

## FUT-01: MCP transport handling is too repo-local
**Severity:** **High**  
**Evidence basis:** Observed  
**Confidence:** High

The original report was right that transport logic is spread across repos.  
That means even modest protocol evolution can create duplicated upgrade work.

### Reviewed framing
This is not mainly a prediction about a specific future transport.  
It is a present-day software architecture issue:
- transport concerns are not centralized enough
- compatibility behavior is harder to test consistently
- protocol changes may require multiple parallel migrations

### Recommended control
Introduce a shared transport boundary or library that owns:
- protocol version selection
- capability negotiation
- request/response envelope handling
- streaming/session abstractions
- compatibility tests

---

## FUT-02: Capability and version negotiation need explicit policy
**Severity:** **High**  
**Evidence basis:** Observed + standards note  
**Confidence:** Medium-High

Hardcoded or uneven protocol-version handling increases:
- brittle client/server pairings
- ambiguous fallback behavior
- upgrade risk across repos

### Recommended control
- define a single suite-level compatibility policy
- make supported protocol versions discoverable
- test downgrade/upgrade behavior explicitly
- separate “what we support” from “what we prefer”

---

## FUT-03: Schema evolution discipline is insufficient
**Severity:** **High**  
**Evidence basis:** Observed  
**Confidence:** High

The original contract-layer and future-proofing work reinforce each other here.  
Version numbers appear, but the suite still needs a clearer answer to:
- where schemas are registered
- how new versions are discovered
- how breaking changes are communicated
- how older artifacts remain readable

### Recommended control
- maintain a schema registry or index
- document compatibility guarantees
- ship transformers or adapters for version transitions
- add contract tests at cross-repo boundaries

---

## FUT-04: Ontology evolution is under-managed
**Severity:** **High**  
**Evidence basis:** Observed + inferred  
**Confidence:** Medium-High

This is especially relevant for `aop-mcp`, but it affects the full suite whenever ontology-backed concepts appear in downstream records or reports.

### Risk pattern
- ontology or taxonomy changes upstream
- local normalization still succeeds syntactically
- semantic meaning or comparability changes silently
- historical artifacts become harder to compare or trust

### Recommended control
- persist ontology/version provenance
- define remapping/deprecation policy
- test historical artifact interpretation against changed ontology states

---

## FUT-05: Provider and model coupling should be loosened
**Severity:** **Medium / High**  
**Evidence basis:** Observed  
**Confidence:** Medium-High

The original package noted provider-specific assumptions in several places.  
That matters because:
- pricing can change
- APIs can shift
- naming and capabilities evolve
- fallback behavior can be unclear

### Recommended control
- define internal capability contracts rather than provider names
- keep provider adapters narrow
- record provider/model identity in provenance
- test fallback behavior intentionally, not incidentally

---

## FUT-06: Artifact and binary handling need a cleaner abstraction
**Severity:** **Medium / High**  
**Evidence basis:** Observed + inferred  
**Confidence:** Medium

As the suite produces richer artifacts, handling everything as JSON payloads or per-repo conventions can create:
- overhead
- streaming friction
- inconsistent client behavior
- duplicated logic

### Recommended control
- define a clear artifact abstraction
- separate metadata from large payload transport
- make artifact lineage and content-type handling consistent across repos

---

## What changed from the original report

### 1. Timing claims were softened
The reviewed copy avoids speculative statements tied to a single quarter unless backed by current public roadmap material.

### 2. “Streaming gap” became “migration resilience gap”
The stronger and more durable claim is not that one specific feature is missing.  
It is that the current suite structure makes protocol change expensive.

### 3. Standards handling was made less theatrical and more operational
The reviewed copy emphasizes:
- compatibility policy
- shared abstractions
- migration tests
- version provenance

---

## Recommended sequence

### Immediate
- define shared MCP compatibility policy
- centralize transport/version handling strategy
- define schema ownership and versioning rules

### Next
- add ontology/version provenance
- reduce provider-specific assumptions
- standardize artifact handling

### Then
- add compatibility and migration test suites across repos
- document deprecation policy and supported-version windows

---

## Final judgment

The original package was right to worry about future change, but the best frame is **migration resilience**, not speculative roadmap drama.

**Bottom line:** ToxMCP will be easier to evolve if transport, schema, ontology, and provider boundaries are made explicit now, while the suite is still small enough to refactor coherently.
