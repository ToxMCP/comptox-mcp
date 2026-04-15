# ToxMCP Suite - Cognitive Ergonomics Audit Report

**Auditor:** Cognitive Ergonomics Designer  
**Date:** April 2026  
**Scope:** comptox-mcp, oqt-mcp, aop-mcp, pbpk-mcp  

---

> **Reviewed copy (2026-04-15):** This document was retained from the original package but lightly edited for consistency.  
> Unless explicitly stated otherwise, code blocks are **reference implementations**, not validated patches, and scenario-based exploit narratives should not be read as reproduced proofs.



## Executive Summary

This audit identifies **critical cognitive ergonomics failures** in the ToxMCP ecosystem that could lead scientists to erroneous conclusions. The suite enables rapid "audit-ready" PDF generation without adequate safeguards, creating a dangerous illusion of scientific rigor.

### Key Finding: The "Foot-Gun" Pattern

The ToxMCP suite provides powerful automation for toxicology workflows but lacks critical guardrails that prevent non-programmer scientists from:
1. Accepting ambiguous chemical identifications
2. Trusting unverified PDF outputs as "audit-ready"
3. Proceeding without human verification of critical assumptions
4. Conflating units across different measurement contexts

---

## 🔴 CRITICAL FINDINGS

### CR-001: No Mandatory Scientific Review Mode for Autonomous Chains

**Severity:** 🔴 CRITICAL  
**File:** `oqt-mcp/src/tools/implementations/workflow_runner.py` (lines 60-98)  
**Cross-ref:** CR-002, CR-003

**Issue:** The workflow runner can fully automate a safety assessment from chemical search to PDF generation without requiring human verification of critical assumptions at any point.

```python
# From workflow_runner.py - WorkflowParams class
class WorkflowParams(BaseModel):
    identifier: str = Field(..., description="Chemical identifier")
    search_type: str = Field("auto", description="How to interpret the identifier")
    # ... no mandatory review checkpoint parameter
    qsar_mode: str = Field("recommended", description="QSAR execution preset")
```

**How Scientists Could Be Misled:**
- A non-programmer scientist could run `run_workflow` with a chemical name
- The system could resolve to the wrong chemical (e.g., wrong isomer)
- QSAR predictions would run on the wrong substance
- A PDF would be generated with "audit-ready" claims
- The scientist would have no indication that verification was needed

**Missing Safeguard:** There is no `require_human_review: true` parameter that forces a pause for verification before proceeding to predictive modeling.

---

### CR-002: PDF Generator Lacks Provenance Tables by Default

**Severity:** 🔴 CRITICAL  
**File:** `oqt-mcp/src/utils/pdf_generator.py` (lines 1-104)  
**Cross-ref:** CR-001, HG-001

**Issue:** The PDF generator creates "audit-ready" reports without mandatory provenance tables showing data sources, versions, and confidence levels.

```python
# From pdf_generator.py - _build_content function
lines = [
    "O-QT MCP Workflow Report",
    "",
    f"Generated: {datetime.utcnow().isoformat(timespec='seconds')}Z",
    "",
]
lines.append("Summary")
# ... NO provenance table included by default
```

**How Scientists Could Be Misled:**
- PDF appears professional and complete
- No visible indication of which QSAR models were used
- No version information for the OECD QSAR Toolbox
- No confidence intervals or applicability domain warnings visible
- Scientist presents PDF to regulators as "audit-ready" evidence

**Missing Safeguard:** No `include_provenance_table: true` default parameter.

---

### CR-003: Confirmation Bias Amplification Through Rapid PDF Generation

**Severity:** 🔴 CRITICAL  
**File:** `oqt-mcp/src/tools/implementations/workflow_runner.py` (lines 330-392)  
**Cross-ref:** CR-001, MD-001

**Issue:** The system generates PDFs quickly without any "red team" analysis that would surface contradictory evidence or alternative hypotheses.

```python
# From workflow_runner.py - artifact generation
artifacts = {
    "json": _build_artifact_entry(...),
    "markdown": _build_artifact_entry(...),
    "pdf": _build_artifact_entry(...),  # Always generates PDF
}
```

**How Scientists Could Be Misled:**
- First result is presented as "the" result
- No automatic generation of alternative interpretations
- No highlighting of data gaps or conflicting evidence
- PDF format creates false sense of finality
- Scientist stops investigating after seeing first "positive" result

**Missing Safeguard:** No `generate_alternative_hypotheses: true` option or `include_contradictory_evidence: true` parameter.

---

## 🟠 HIGH SEVERITY FINDINGS

### HG-001: Chemical Search Defaults to "auto" Without Warning

**Severity:** 🟠 HIGH  
**File:** `oqt-mcp/src/tools/implementations/o_qt_qsar_tools.py` (lines 61-67)  
**Cross-ref:** CR-001

**Issue:** The `search_chemicals` tool defaults to `search_type: "auto"` which may silently match the wrong chemical.

```python
class ChemicalSearchParams(BaseModel):
    query: str = Field(..., description="The search term")
    search_type: str = Field(
        "auto",  # DEFAULT DANGER: Auto-detection can be wrong
        description="Type of search (e.g., 'auto', 'name', 'cas', 'smiles')."
    )
```

**How Scientists Could Be Misled:**
- Scientist searches for "benzene" with default "auto" mode
- System might interpret as SMILES instead of name
- Returns wrong chemical or no results
- Scientist concludes chemical not in database
- Or worse: proceeds with incorrect chemical identification

**Concrete Example:**
```python
# User searches for CAS "50-00-0" (formaldehyde)
# search_type="auto" might interpret as SMILES "50-00-0"
# Returns no results or wrong chemical
search_chemicals(query="50-00-0", search_type="auto")  # DANGEROUS
```

**Missing Safeguard:** No warning when "auto" detection is uncertain; no explicit confirmation of chemical identity before proceeding.

---

### HG-002: AOP Version Not Captured in get_aop Output

**Severity:** 🟠 HIGH  
**File:** `aop-mcp/src/server/tools/aop.py` (lines 52-70)  
**Cross-ref:** MD-001

**Issue:** The `get_aop` tool fetches current AOP-Wiki data without capturing the specific version or timestamp, making reproducibility impossible.

```python
class GetAopInput(BaseModel):
    aop_id: str  # No version parameter

async def get_aop(params: GetAopInput) -> dict[str, Any]:
    wiki_adapter = get_aop_wiki_adapter()
    db_adapter = get_aop_db_adapter()
    core_record, assessment_record, stressor_records = await asyncio.gather(
        wiki_adapter.get_aop(params.aop_id),  # No version specified
        wiki_adapter.get_aop_assessment(params.aop_id),
        db_adapter.list_stressor_chemicals_for_aop(params.aop_id),
    )
```

**How Scientists Could Be Misled:**
- Scientist runs assessment in January, AOP has 3 key events
- AOP is updated in March with new key event
- Scientist re-runs same query in April
- Results are different but no warning is given
- Scientist doesn't realize conclusions have changed
- Regulatory submission contains inconsistent assessments

**Missing Safeguard:** No `version` parameter; no `retrieved_at` timestamp in output; no warning when AOP has been modified since last retrieval.

---

### HG-003: Unit Fields Present But Not Validated

**Severity:** 🟠 HIGH  
**File:** `pbpk-mcp/src/mcp_bridge/routes/simulation.py` (lines 200-218)  
**Cross-ref:** MD-002

**Issue:** Unit fields exist in the schema but there's no validation to prevent unit confusion errors.

```python
class SetParameterValueRequest(GetParameterValueRequest):
    value: float
    unit: Optional[str] = None  # Present but not validated
    update_mode: Optional[str] = Field(default="absolute", alias="updateMode")
    comment: Optional[str] = None
    confirm: Optional[bool] = None
```

**How Scientists Could Be Misled:**
- Scientist sets liver volume to "1.5" with unit "L" (liters)
- System expects "mL" (milliliters)
- Simulation runs with 1000x wrong volume
- PK parameters are calculated incorrectly
- No error is raised; results appear valid

**Missing Safeguard:** No unit validation against expected units; no conversion warnings; no dimensional analysis.

---

### HG-004: Confirmation System Can Be Bypassed

**Severity:** 🟠 HIGH  
**File:** `pbpk-mcp/src/mcp_bridge/security/confirmation.py` (lines 1-38)  
**Cross-ref:** CR-001

**Issue:** The confirmation system for critical operations relies on a simple header check that can be easily bypassed by automated agents.

```python
_TRUE_VALUES = {"true", "1", "yes", "y", "confirmed"}

def is_confirmed(request: Request) -> bool:
    header_value = request.headers.get(CONFIRMATION_HEADER)
    if not header_value:
        return False
    return header_value.split(",")[0].strip().lower() in _TRUE_VALUES
```

**How Scientists Could Be Misled:**
- Agent chain includes `confirm: true` in all requests
- Critical operations proceed without actual human review
- Scientist believes system has "guardrails"
- In reality, guardrails are cosmetic only

**Missing Safeguard:** No out-of-band confirmation (e.g., email, separate UI); no rate limiting on confirmations; no audit of who confirmed.

---

## 🟡 MEDIUM SEVERITY FINDINGS

### MD-001: Temporal Confusion in AOP Assessment

**Severity:** 🟡 MEDIUM  
**File:** `aop-mcp/src/server/tools/aop.py` (lines 152-291)  
**Cross-ref:** HG-002

**Issue:** The `assess_aop_confidence` tool aggregates evidence without tracking when each piece of evidence was added or modified.

```python
async def assess_aop_confidence(params: AssessAopConfidenceInput) -> dict[str, Any]:
    # ... fetches current data
    confidence_dimensions = _build_confidence_dimensions(aop, key_event_details, ker_details)
    # No temporal metadata about when evidence was added
```

**How Scientists Could Be Misled:**
- Assessment shows "strong" empirical support
- Scientist doesn't realize evidence was added last week
- Previous assessment from 3 months ago showed "moderate"
- No way to track when confidence changed or why

**Missing Safeguard:** No `evidence_timestamp` field; no `assessment_version` tracking.

---

### MD-002: Unit Ambiguity in PK Parameter Output

**Severity:** 🟡 MEDIUM  
**File:** `pbpk-mcp/src/mcp_bridge/routes/simulation.py` (lines 314-326)  
**Cross-ref:** HG-003

**Issue:** PK parameter units are returned as strings without standardized formatting, risking misinterpretation.

```python
class PkMetricModel(CamelModel):
    parameter: str
    unit: Optional[str] = None  # Free text, not validated
    cmax: Optional[float] = Field(default=None, alias="cmax")
    tmax: Optional[float] = Field(default=None, alias="tmax")
    auc: Optional[float] = Field(default=None, alias="auc")
```

**How Scientists Could Be Misled:**
- AUC returned as "10" with unit "mg/L*h"
- Scientist interprets as "10 mg/(L*h)" when it's "(10 mg/L)*h"
- Dosing calculations are off by orders of magnitude

**Missing Safeguard:** No standardized unit format (e.g., UCUM); no unit validation; no dimensional analysis.

---

### MD-003: Fallback Search Mode Silently Changes Results

**Severity:** 🟡 MEDIUM  
**File:** `comptox-mcp/src/epacomp_tox/resources/chemical.py` (lines 450-547)  
**Cross-ref:** HG-001

**Issue:** The `resolve_chemical_identifier` tool uses fallback search modes without requiring explicit user acknowledgment.

```python
def resolve_chemical_identifier(
    self,
    *,
    identifier: str,
    identifier_type: Optional[str] = None,
    allow_fallback: bool = False,  # Must be explicitly set to True
    max_candidates: int = 5,
) -> Dict[str, Any]:
```

**How Scientists Could Be Misled:**
- Scientist sets `allow_fallback=True` to handle edge cases
- Exact match fails, fallback to "contains" returns multiple candidates
- System returns "ambiguous" status but scientist's script ignores it
- First candidate is used without verification
- Wrong chemical proceeds through workflow

**Missing Safeguard:** No mandatory pause when fallback is used; no requirement to explicitly select from candidates.

---

### MD-004: QSAR Mode "recommended" Is Opaque

**Severity:** 🟡 MEDIUM  
**File:** `oqt-mcp/src/tools/implementations/workflow_runner.py` (lines 75-78)  
**Cross-ref:** CR-001

**Issue:** The default `qsar_mode: "recommended"` doesn't explain which models are selected or why.

```python
qsar_mode: str = Field(
    "recommended",  # What does "recommended" mean?
    description="QSAR execution preset (`recommended`, `all`, or `none`).",
)
```

**How Scientists Could Be Misled:**
- Scientist uses default "recommended" mode
- Doesn't realize only 3 of 15 available models were run
- Reports "QSAR analysis complete" when it was partial
- Regulator assumes comprehensive analysis was performed

**Missing Safeguard:** No transparency about which models are in "recommended" set; no warning when models are excluded.

---

## CROSS-REFERENCE MATRIX

| Finding | CR-001 | CR-002 | CR-003 | HG-001 | HG-002 | HG-003 | HG-004 | MD-001 | MD-002 | MD-003 | MD-004 |
|---------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|
| CR-001  | -      | X      | X      | X      |        |        | X      |        |        |        | X      |
| CR-002  | X      | -      | X      |        |        |        |        |        |        |        |        |
| CR-003  | X      | X      | -      |        |        |        |        | X      |        |        |        |
| HG-001  | X      |        |        | -      |        |        |        |        |        | X      |        |
| HG-002  |        |        |        |        | -      |        |        | X      |        |        |        |
| HG-003  |        |        |        |        |        | -      |        |        | X      |        |        |
| HG-004  | X      |        |        |        |        |        | -      |        |        |        |        |
| MD-001  |        |        | X      |        | X      |        |        | -      |        |        |        |
| MD-002  |        |        |        |        |        | X      |        |        | -      |        |        |
| MD-003  |        |        |        | X      |        |        |        |        |        | -      |        |
| MD-004  | X      |        |        |        |        |        |        |        |        |        | -      |

---

## RECOMMENDATIONS

### Immediate Actions Required

1. **Implement Mandatory Scientific Review Mode**
   - Add `require_human_review: true` parameter to all workflow tools
   - Require explicit acknowledgment before proceeding to predictive modeling
   - Log reviewer identity and timestamp

2. **Add Provenance Tables to All PDFs**
   - Include data sources, versions, retrieval timestamps
   - List all models used with confidence intervals
   - Show applicability domain warnings prominently

3. **Implement Red Team Analysis**
   - Generate alternative hypotheses automatically
   - Surface contradictory evidence
   - Include confidence intervals and uncertainty quantification

4. **Add Version Tracking to AOP Tools**
   - Include `retrieved_at` timestamp in all outputs
   - Warn when AOP has been modified since last retrieval
   - Support explicit version selection

5. **Implement Unit Validation**
   - Use standardized unit formats (UCUM)
   - Validate units against expected dimensions
   - Require explicit unit confirmation for critical parameters

---

## CONCLUSION

The ToxMCP suite provides powerful automation capabilities but currently prioritizes convenience over scientific rigor. The lack of mandatory verification steps, combined with rapid PDF generation, creates a dangerous "foot-gun" pattern where well-intentioned scientists can unknowingly produce erroneous assessments.

**The most critical issue is the absence of a mandatory scientific review mode.** An autonomous agent can currently execute a complete safety assessment workflow—from ambiguous chemical search to "audit-ready" PDF—without any human verification of critical assumptions.

Without these safeguards, the ToxMCP suite risks becoming a tool for generating convincing-looking but potentially erroneous toxicology assessments.

---

*Report generated by Cognitive Ergonomics Designer*  
*For the ToxMCP Ecosystem Orchestrator*
