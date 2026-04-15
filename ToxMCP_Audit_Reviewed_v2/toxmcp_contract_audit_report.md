# ToxMCP Suite: Contract Layer Architecture Audit Report
## Cross-Suite Orchestration Analysis

**Audit Date:** 2026-04-15  
**Auditor:** Cross-Suite Orchestration Architect  
**Scope:** comptox-mcp, oqt-mcp, aop-mcp, pbpk-mcp

---

> **Reviewed copy (2026-04-15):** This document was retained from the original package but lightly edited for consistency.  
> Unless explicitly stated otherwise, code blocks are **reference implementations**, not validated patches, and scenario-based exploit narratives should not be read as reproduced proofs.



## Executive Summary

The ToxMCP suite demonstrates sophisticated modular architecture with clear domain boundaries, but critical gaps exist in the **Contract Layer** that prevent coherent cross-suite workflows. The "Swiss Army Knife" problem is real: each module is sharp individually, but they lack the integration mechanisms to form a *coherent argument*.

### Key Finding: Orchestrator Responsibility Is Documented but Not Implemented
The documentation repeatedly references a "downstream orchestrator" and "future ToxClaw orchestration layer" but **no such orchestrator exists** in the codebase. This is the single most critical architectural gap.

---

## 1. Contract Drift Analysis

### 🔴 CRITICAL: Evidence Block Structural Incompatibility

| Module | Evidence Block Structure | Incompatibility |
|--------|-------------------------|-----------------|
| **CompTox-MCP** | `hazardEvidenceSummary.v1.json` - Flat structure with `datasets[]`, `keyFindings[]` | No `evidenceBlocks` wrapper |
| **O-QT-MCP** | `oqtHazardEvidenceSummary.v1.json` - Nested `evidenceBlocks{endpointData, profiling, metabolism, qsar}` | Uses `evidenceBlock` with `status`, `basis`, `keyEvidence[]` |
| **AOP-MCP** | `get_ker.response.schema.json` - `evidence_blocks{biological_plausibility, empirical_support, quantitative_understanding}` | Uses `evidenceBlock` with `text`, `heuristic_call`, `basis` |

### Specific Contract Drift Examples

#### 1.1 Field Name Inconsistencies (camelCase vs snake_case)

```
CompTox:  "chemicalRef", "keyFindings", "sourceDataset"
O-QT:     "chemicalIdentity", "endpointSummaries", "evidenceBlocks"
AOP:      "overall_applicability", "evidence_blocks", "heuristic_call"
```

**File References:**
- `comptox-mcp/schemas/hazardEvidenceSummary.v1.json` (lines 16-45)
- `oqt-mcp/schemas/oqtHazardEvidenceSummary.v1.json` (lines 40-70)
- `aop-mcp/docs/contracts/schemas/read/get_ker.response.schema.json` (lines 125-134)

#### 1.2 Evidence Block Schema Mismatch

**O-QT `evidenceBlock` (lines 460-499):**
```json
{
  "summary": "string|null",
  "status": "coverageState",
  "basis": "string",
  "keyEvidence": ["string"],
  "references": ["referenceRecord"],
  "provenanceRecords": ["provenanceRecord"]
}
```

**AOP `evidenceBlock` (lines 160-171):**
```json
{
  "text": "string|null",
  "heuristic_call": "string",
  "basis": "string",
  "references": ["object"],
  "provenance": ["provenanceRecord"]
}
```

**Transformation Loss:** A CompTox hazard evidence block CANNOT be directly consumed by AOP-MCP draft authoring without field mapping:
- `keyFindings[]` -> `evidence_blocks` requires manual transformation
- `confidence` (0-1 float in CompTox) -> `heuristic_call` (string in AOP)
- No shared `provenanceRecord` structure

### 🟠 HIGH: Unit Mismatches

**CompTox hazard evidence:**
- Uses `"unit": "log_mg_kg"` (line 667 in interop.py)
- ToxValDB: `mg/kg`, `uM`, `ppm` (mixed)

**O-QT QSAR findings:**
- `"unit": "string"` (line 267-268 in oqtHazardEvidenceSummary.v1.json)
- No standardization enforced

**PBPK context:**
- HTTK: `L/h/kg`, `1/hr`
- ADME/IVIVE: `L/h/kg`

**Risk:** Downstream orchestrator must handle unit conversion without explicit metadata about unit systems.

### 🟠 HIGH: Ontology Versioning Conflicts

**AOP-MCP:**
- Uses AOP-Wiki RDF/SPARQL with OECD AOP-KB
- `assess_aop_confidence.response.schema.json` includes `oecd_alignment` field
- References "OECD-aligned" contracts throughout

**CompTox-MCP:**
- Uses internal AOP crosswalk (bioactivity_aop mappings)
- `aopLinkageSummary.v1.json` has different `mapping` structure

**Gap:** No shared ontology registry or version negotiation mechanism exists.

---

## 2. The Orchestrator Gap

### 🔴 CRITICAL: Missing Meta-Reasoning Layer

**Finding:** The "downstream orchestrator" is referenced 20+ times across documentation but **DOES NOT EXIST** in the codebase.

**Documentation References:**
- `oqt-mcp/docs/architecture.md` (line 47-56): "A downstream orchestrator sits above O-QT MCP"
- `oqt-mcp/docs/integration_orchestrators.md` (line 57): "Final suite-level evidence synthesis belongs in a downstream orchestrator"
- `comptox-mcp/docs/architecture_overview.md` (line 105): "future ToxClaw orchestration layer"

**What the Orchestrator Should Do (but doesn't exist):**
1. **Evidence Deduplication:** Prevent double-counting when CompTox and O-QT both report similar hazard findings
2. **Contradiction Detection:** Flag when CompTox says "non-toxic" but AOP suggests "liver injury via different pathway"
3. **Cross-Module Consistency:** Ensure PBPK simulation results align with hazard evidence
4. **Narrative Coherence:** Verify PDF report from O-QT doesn't contradict PBPK results

### 🟠 HIGH: No Narrative Consistency Checker

**Example Scenario:**
```
CompTox-MCP: "No genotoxicity signal detected in ToxCast assays"
AOP-MCP:     "AOP 42: Liver steatosis via PPARG activation"
O-QT-MCP:    "Profiler alert: potential DNA binding mechanism"
PBPK-MCP:    "High hepatic concentration predicted"
```

**Question:** Where is the component that detects the tension between "no genotoxicity" and "DNA binding mechanism"?

**Answer:** Nowhere. Each module operates in isolation.

### 🟡 MEDIUM: GenRA Orchestrator is Experimental-Only

**File:** `comptox-mcp/src/epacomp_tox/orchestrator/workflow.py`

The `GenRAOrchestrator` class exists but:
- Is marked as **experimental** in architecture docs
- Only handles CompTox-internal workflows
- Does NOT integrate with O-QT, AOP, or PBPK modules
- Has no cross-module transaction management

---

## 3. Transaction Boundaries

### 🔴 CRITICAL: No Cross-Module Rollback Mechanism

**Scenario Analysis:**

```
1. O-QT-MCP successfully generates grouping dossier
2. AOP-MCP fails to retrieve AOP (SPARQL timeout)
3. PBPK-MCP simulation completes
4. CompTox-MCP evidence pack assembly fails (API error)
```

**Current Behavior:**
- Each module operates independently
- No distributed transaction coordinator
- Partial results can be returned without context

**Risk:** System can produce **partial, misleading safety reports** with missing context.

**Evidence from Code:**
- `oqt-mcp/docs/architecture.md` (line 66): "Async queue and persistence layer remain roadmap work"
- `comptox-mcp/src/epacomp_tox/orchestrator/workflow.py` (lines 91-114): Error handling only within single workflow, no cross-module coordination

### 🟠 HIGH: PBPK Has Session Registry, Others Don't

**PBPK-MCP:**
- Has `mcp.session_registry` for simulation handles
- Supports job queue with Redis
- Has rollback via snapshot mechanism

**Other Modules:**
- No session registry
- No job persistence
- No rollback capability

**Gap:** Inconsistent state management across suite.

---

## 4. Schema Evolution Strategy

### 🔴 CRITICAL: No Schema Registry or Version Negotiation

**Current State:**

| Schema | Version | Version Detection |
|--------|---------|-------------------|
| `oqtWorkflowRecord.v1.json` | v1 | Hardcoded `const: "v1"` |
| `oqtHazardEvidenceSummary.v1.json` | v1 | Hardcoded `const: "v1"` |
| `hazardEvidenceSummary.v1.json` | v1 | In filename only |
| `aopLinkageSummary.v1.json` | v1 | In filename only |

**Problems:**
1. **No schema registry** - Consumers cannot discover available versions
2. **No version negotiation** - Cannot request `v1` vs `v2` at runtime
3. **Breaking changes undefined** - No migration path documented

**File References:**
- `oqt-mcp/schemas/oqtWorkflowRecord.v1.json` (lines 26-28): Hardcoded version
- `comptox-mcp/schemas/README.md`: "Portable schema versions are intentionally independent from package patch releases"

### 🟠 HIGH: Inconsistent Version Declaration Patterns

**O-QT Pattern (explicit):**
```json
"schemaName": { "const": "oqtWorkflowRecord" },
"schemaVersion": { "const": "v1" }
```

**CompTox Pattern (implicit):**
```json
"$id": "https://epa.gov/comptox/schemas/hazardEvidenceSummary.v1.json"
```

**AOP Pattern (none):**
```json
"$schema": "https://json-schema.org/draft/2020-12/schema"
// No version in schema itself
```

---

## 5. Integration Anti-Patterns Catalog

### Anti-Pattern 1: "Hope for the Best" Integration
**Evidence:** `comptox-mcp/src/epacomp_tox/orchestrator/workflow.py` (lines 388-411)
```python
try:
    evidence_pack = self.interop_resource.assemble_comptox_evidence_pack(...)
    aop_summary = self.interop_resource.build_aop_linkage_summary(...)
    pbpk_bundle = self.interop_resource.build_pbpk_context_bundle(...)
except Exception as exc:
    guardrails.append(...)
    return None
```

**Problem:** Interop attachments can fail silently; no retry or compensation logic.

### Anti-Pattern 2: "Every Module for Itself" Provenance
**CompTox Provenance:**
```json
{
  "sourceMcp": "epacomp-tox-mcp",
  "generatedAt": "timestamp",
  "sources": [...]
}
```

**O-QT Provenance:**
```json
{
  "workflowId": "string",
  "sourceSystem": "string",
  "generatedBy": "string",
  "generatedAt": "timestamp"
}
```

**AOP Provenance:**
```json
{
  "source": "string",
  "field": "string",
  "transformation": "string|null",
  "confidence": "string|null"
}
```

**Problem:** Three different provenance structures; no unified audit trail.

### Anti-Pattern 3: Ambiguous Orchestrator Ownership
The orchestrator is simultaneously:
- Essential for final synthesis (per docs)
- Non-existent in code
- Referenced as "future ToxClaw layer"

---

## 6. Swiss Army Knife Problem Assessment

### Can the Tools Form a Coherent Argument?

| Capability | Status | Gap |
|------------|--------|-----|
| Individual hazard assessment | Working | - |
| Individual AOP discovery | Working | - |
| Individual QSAR prediction | Working | - |
| Individual PBPK simulation | Working | - |
| Cross-module evidence fusion | Missing | No orchestrator |
| Contradiction detection | Missing | No meta-reasoning |
| Narrative consistency | Missing | No validation layer |
| Decision recommendation | Missing | Out of scope per design |

### The Core Issue

Each module correctly declares:
- `decisionBoundary.supportedDecisions`
- `decisionBoundary.prohibitedDecisions`
- `decisionOwner`

But there's **no consumer** of these declarations. The orchestrator that should read these boundaries and make cross-module decisions doesn't exist.

---

## 7. Recommendations

### Immediate (High Priority)

1. **Define the Orchestrator Interface**
   - Create `toxmcp-orchestrator` repository
   - Define contract for cross-module evidence fusion
   - Implement contradiction detection engine

2. **Standardize Evidence Blocks**
   - Create `toxmcp-evidence-schema` shared package
   - Unify `evidenceBlock` structure across all modules
   - Version all schemas with explicit negotiation

3. **Implement Transaction Coordination**
   - Add saga pattern for cross-module workflows
   - Define compensation actions for each module
   - Create unified session registry

### Medium Term

4. **Build Meta-Reasoning Layer**
   - Implement confidence aggregation across modules
   - Create ontology alignment service
   - Build narrative consistency validator

5. **Schema Registry**
   - Deploy central schema registry
   - Implement version negotiation protocol
   - Add schema compatibility testing

---

## Appendix: File Reference Index

### Schema Files Analyzed
- `comptox-mcp/schemas/hazardEvidenceSummary.v1.json`
- `comptox-mcp/schemas/aopLinkageSummary.v1.json`
- `comptox-mcp/schemas/comptoxEvidencePack.v1.json`
- `oqt-mcp/schemas/oqtHazardEvidenceSummary.v1.json`
- `oqt-mcp/schemas/oqtReadAcrossSummary.v1.json`
- `oqt-mcp/schemas/oqtWorkflowRecord.v1.json`
- `aop-mcp/docs/contracts/schemas/read/get_ker.response.schema.json`
- `aop-mcp/docs/contracts/schemas/read/assess_aop_confidence.response.schema.json`

### Documentation Files Analyzed
- `oqt-mcp/docs/architecture.md`
- `oqt-mcp/docs/integration_orchestrators.md`
- `oqt-mcp/docs/cross_suite_alignment_2026.md`
- `comptox-mcp/docs/architecture_overview.md`
- `aop-mcp/docs/architecture.md`
- `pbpk-mcp/docs/mcp-bridge/architecture.md`

### Code Files Analyzed
- `comptox-mcp/src/epacomp_tox/orchestrator/workflow.py`
- `comptox-mcp/src/epacomp_tox/orchestrator/offline.py`
- `comptox-mcp/src/epacomp_tox/resources/interop.py`

---

## Summary of Findings by Severity

### 🔴 Critical (4)
1. **Missing Orchestrator:** The downstream orchestrator referenced throughout docs does not exist
2. **Evidence Block Incompatibility:** CompTox, O-QT, and AOP use incompatible evidence block structures
3. **No Cross-Module Rollback:** Partial failures can produce misleading safety reports
4. **No Schema Registry:** No version negotiation or discovery mechanism

### 🟠 High (5)
1. **No Narrative Consistency Checker:** No component validates coherence across module outputs
2. **Unit Mismatches:** Different unit systems without conversion metadata
3. **Inconsistent Version Patterns:** Each module uses different version declaration
4. **Inconsistent State Management:** PBPK has session registry; others don't
5. **Ontology Versioning Conflicts:** No shared ontology registry

### 🟡 Medium (2)
1. **GenRA Orchestrator is Experimental:** Internal-only, not cross-module
2. **Provenance Structure Divergence:** Three different provenance formats

---

**Audit Complete**
