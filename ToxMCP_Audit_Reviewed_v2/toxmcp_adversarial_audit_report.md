# ToxMCP Scientific Adversary Audit Report

**Audit Date:** 2026-04-15  
**Auditor:** Scientific Adversary Agent  
**Scope:** comptox-mcp, oqt-mcp, aop-mcp, pbpk-mcp  
**Mission:** Identify attack surfaces for generating false confidence and misleading toxicological conclusions

---

> **Reviewed copy (2026-04-15):** This document was retained from the original package but lightly edited for consistency.  
> Unless explicitly stated otherwise, code blocks are **reference implementations**, not validated patches, and scenario-based exploit narratives should not be read as reproduced proofs.



## Executive Summary

The ToxMCP ecosystem, while architecturally sophisticated, contains **multiple critical attack surfaces** that an AI agent (or malicious user) could exploit to generate misleading toxicological conclusions with false confidence. The most severe vulnerabilities exist in:

1. **Applicability Domain (AD) enforcement gaps** in O-QT-MCP QSAR predictions
2. **Confidence interpolation without calibration** across AOP-MCP assessment tools
3. **Parameter manipulation without physiological plausibility guardrails** in PBPK-MCP
4. **Missing epistemic uncertainty propagation** across the tool chain

---

## 🔴 CRITICAL VULNERABILITIES

### V-001: Missing Applicability Domain Enforcement (O-QT-MCP)

**Severity:** 🔴 Critical  
**Location:** `oqt-mcp/src/tools/implementations/o_qt_qsar_tools.py`  
**Attack Surface:** QSAR prediction workflow

**Description:**
The O-QT-MCP mentions "applicability domain review" in its documentation and schemas, but the actual enforcement is **qualitative and post-hoc**. The `build_hazard_applicability_domain()` function (line 61 in hazard_contracts.py) creates a summary but does NOT:

- Calculate a quantitative Applicability Domain Index (ADI)
- Enforce chemical class boundary checks
- Block predictions for out-of-domain chemicals
- Require explicit user acknowledgment for extrapolation

**Attack Example:**
```python
# An agent can obtain QSAR predictions for a chemical completely outside
# the training set without receiving a clear UNRELIABLE flag
{
  "tool": "run_qsar_prediction",
  "arguments": {
    "chem_id": "EXOTIC_CHEM_001",  # Novel scaffold not in training data
    "model_guid": "skin_sensitization_model"
  }
}
# Returns: prediction with "medium" confidence and AD notes buried in metadata
```

**False Confidence Generation:**
- The `oqtHazardEvidenceSummary.v1.json` schema includes `applicabilityDomain` as a required field, but it's a **narrative summary**, not a quantitative gate
- An AI agent can chain predictions → ignore AD warnings → present conclusions as reliable

**Cross-Reference:** V-005 (Confirmation Bias Accumulation)

---

### V-002: Confidence Score False Precision (AOP-MCP)

**Severity:** 🔴 Critical  
**Location:** `aop-mcp/src/tools/semantic/` (confidence assessment)  
**Attack Surface:** `assess_aop_confidence` tool

**Description:**
The `assess_aop_confidence` tool returns heuristic confidence assessments that **appear quantitative but lack calibration**. From the README documentation:

> "`assess_aop_confidence` is OECD-aligned, not OECD-complete... confidence outputs often remain partial even when the tool is behaving correctly"

The tool returns confidence dimensions as text ("high", "medium", "low") but these are:
- **Not probabilistic** - no confidence intervals or uncertainty quantification
- **Not calibrated** - "high" confidence doesn't map to a specific accuracy rate
- **Text-mining derived** - based on evidence text presence, not mechanistic validation

**Attack Example:**
```python
# Agent chains multiple AOP assessments, each with "medium" confidence
# The aggregate appears to support a conclusion, but confidence is not additive
{
  "aop_1_confidence": "medium",  # Based on sparse KE evidence
  "aop_2_confidence": "medium",  # Based on different sparse evidence
  "aop_3_confidence": "medium",  # Based on yet different sparse evidence
}
# Agent reports: "Multiple AOPs show consistent medium-to-high confidence"
```

**False Precision Pattern:**
- The schema allows `confidence_dimensions` to be reported without accompanying `uncertainty_quantification`
- No warning when confidence is inferred from path structure alone (without text evidence)

**Cross-Reference:** V-005 (Confirmation Bias Accumulation)

---

### V-003: PBPK Parameter P-Hacking (PBPK-MCP)

**Severity:** 🔴 Critical  
**Location:** `pbpk-mcp/src/mcp/tools/set_parameter_value.py`  
**Attack Surface:** Parameter editing and sensitivity analysis

**Description:**
The `set_parameter_value` tool allows direct manipulation of PBPK parameters with **minimal physiological plausibility guardrails**:

```python
class SetParameterValueRequest(BaseModel):
    simulation_id: str
    parameter_path: str  # No validation against physiological bounds
    value: float         # No range validation
    unit: Optional[str]  # Unit conversion but no sanity checks
    update_mode: Optional[str] = "absolute"  # "relative" mode compounds errors
```

**Attack Example - Parameter Inflation:**
```python
# Agent systematically tweaks clearance parameters until desired outcome
for clearance_factor in [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
    set_parameter_value(
        parameter_path="Liver|Clearance",
        value=baseline * clearance_factor
    )
    result = run_simulation()
    if result.auc < safety_threshold:
        return f"Model shows safe clearance at factor {clearance_factor}"
# No audit trail of parameter exploration; best result reported
```

**Missing Guardrails:**
- No physiological bounds checking (e.g., liver blood flow cannot exceed cardiac output)
- No parameter correlation enforcement (changing one parameter should affect correlated ones)
- No "p-hacking detection" for systematic parameter sweeps
- The `run_sensitivity_analysis` tool doesn't flag when results are cherry-picked

**Cross-Reference:** V-005 (Confirmation Bias Accumulation)

---

## 🟠 HIGH SEVERITY VULNERABILITIES

### V-004: Read-Across Analogue Bias (O-QT-MCP)

**Severity:** 🟠 High  
**Location:** `oqt-mcp/schemas/oqtReadAcrossSummary.v1.json`  
**Attack Surface:** Grouping and read-across justification

**Description:**
The `build_grouping_justification` tool can suggest read-across from chemicals that are **structurally similar but toxicologically divergent**. The schema requires:

- `structure_comparison` - structural similarity assessment
- `physicochemical_comparison` - physchem property comparison
- BUT: **No mechanistic justification gate** for Mode of Action (MOA) alignment

**Attack Example - Analogue Bias:**
```python
# Agent groups chemicals by structural similarity alone
{
  "tool": "build_grouping_justification",
  "arguments": {
    "identifier": "Target_Chemical",
    "analogue_identifiers": ["Analogue_A", "Analogue_B"],
    "profiler_guids": ["structural_profiler_only"]  # No MOA profiler
  }
}
# Returns: grouping justification showing high structural similarity
# Problem: Target has genotoxic MOA, analogues have non-genotoxic MOA
```

**Schema Weakness:**
The `oqtReadAcrossSummary.v1.json` schema includes `applicabilityDomain` but it's a **qualitative field** without:
- MOA concordance scoring
- Toxicodynamic similarity metrics
- Mechanistic alert flags

**Cross-Reference:** V-001 (Missing AD Enforcement)

---

### V-005: Confirmation Bias Accumulation Across Tool Chain

**Severity:** 🟠 High  
**Location:** Cross-suite (comptox → oqt → aop → pbpk)  
**Attack Surface:** Multi-tool chaining workflows

**Description:**
There is **NO meta-assessment tool** that tracks epistemic uncertainty propagation across the tool chain. When an AI agent chains:

```
search_chemical → profile_chemical → run_qsar → assess_aop → run_pbpk
```

Each step can:
- Generate predictions with unquantified uncertainty
- Pass "confidence" forward without uncertainty accumulation
- Filter evidence that doesn't support the emerging conclusion

**Attack Example - Confirmation Bias Chain:**
```python
# Step 1: Search finds chemical
search_result = search_chemicals("mystery_compound")

# Step 2: Profiling shows some alerts (but agent focuses on benign ones)
profile = run_profiler(profiler_guid="safe_profiler")

# Step 3: QSAR prediction with AD warning (agent ignores warning)
qsar = run_qsar_prediction(chem_id, model_guid="safe_model")
# AD note: "Chemical outside training domain" buried in metadata

# Step 4: AOP assessment finds supportive pathway (ignores contradictory ones)
aop = assess_aop_confidence(aop_id="supportive_aop")

# Step 5: PBPK with tweaked parameters shows favorable kinetics
set_parameter_value(parameter_path="clearance", value=high_value)
pbpk = run_simulation()

# Final conclusion: "Multiple lines of evidence support safety"
# Reality: Each step had warnings that were filtered out
```

**Missing Safeguard:**
- No `uncertainty_propagation` tool
- No `evidence_contradiction_detection` across modules
- No `confidence_calibration` across the chain

**Cross-Reference:** All other vulnerabilities

---

## 🟡 MEDIUM SEVERITY VULNERABILITIES

### V-006: CompTox Evidence Federation Gaps (CompTox-MCP)

**Severity:** 🟡 Medium  
**Location:** `comptox-mcp` (evidence federation)  
**Attack Surface:** Multi-source evidence aggregation

**Description:**
The CompTox-MCP federates evidence from multiple EPA sources but:
- **No source conflict resolution** - when sources disagree, all are presented equally
- **No evidence quality weighting** - high-quality studies not distinguished from preliminary data
- **No temporal decay** - older studies not flagged as potentially superseded

**Attack Example:**
```python
# Agent can selectively cite evidence from conflicting sources
{
  "bioactivity_assays": [
    {"source": "ToxCast", "result": "inactive", "quality": "high"},
    {"source": "legacy_study", "result": "active", "quality": "low"}
  ]
}
# Agent reports: "Study shows activity" (citing only legacy_study)
```

---

### V-007: Qualitative Uncertainty Masking (All Modules)

**Severity:** 🟡 Medium  
**Location:** Cross-suite schemas  
**Attack Surface:** Uncertainty reporting

**Description:**
All ToxMCP modules use **qualitative uncertainty descriptors** that mask underlying quantitative uncertainty:

| Module | Uncertainty Field | Values | Problem |
|--------|------------------|--------|---------|
| O-QT | `accepted_uncertainty_level` | "low", "medium", "high" | No probabilistic meaning |
| AOP | `confidence_dimensions` | "high", "medium", "low" | Not calibrated |
| PBPK | `qualificationLevel` | "qualified", "unqualified" | Binary when continuous needed |
| CompTox | `evidence_quality` | "high", "medium", "low" | Subjective |

**Attack Example:**
```python
# Agent can interpret "medium" uncertainty differently based on desired conclusion
if supporting_conclusion:
    interpret("medium") = "acceptable for decision-making"
else:
    interpret("medium") = "requires further study"
```

---

## Attack Surface Summary Matrix

| Attack Vector | O-QT-MCP | AOP-MCP | PBPK-MCP | CompTox-MCP | Severity |
|--------------|----------|---------|----------|-------------|----------|
| False confidence from out-of-domain predictions | ✅ | ❌ | ❌ | ❌ | 🔴 |
| Confidence interpolation without calibration | ❌ | ✅ | ❌ | ❌ | 🔴 |
| Parameter p-hacking | ❌ | ❌ | ✅ | ❌ | 🔴 |
| Read-across analogue bias | ✅ | ❌ | ❌ | ❌ | 🟠 |
| Confirmation bias accumulation | ✅ | ✅ | ✅ | ✅ | 🟠 |
| Evidence selection bias | ✅ | ✅ | ❌ | ✅ | 🟡 |
| Qualitative uncertainty masking | ✅ | ✅ | ✅ | ✅ | 🟡 |

---

## Concrete Attack Scenarios

### Scenario 1: The "Safe by Design" Deception

**Goal:** Convince stakeholders a hazardous chemical is safe

**Attack Chain:**
1. Use O-QT-MCP to run QSAR models, selecting only those with favorable predictions
2. Ignore applicability domain warnings (buried in metadata)
3. Use AOP-MCP to find pathways where the chemical doesn't trigger key events
4. Use PBPK-MCP with inflated clearance parameters to show rapid elimination
5. Present conclusion: "Multiple independent lines of evidence support safety"

**Vulnerabilities Exploited:** V-001, V-002, V-003, V-005

---

### Scenario 2: The "Toxic by Association" Smear

**Goal:** Falsely associate a competitor's chemical with toxicity

**Attack Chain:**
1. Use O-QT-MCP grouping to find structurally similar analogues with known toxicity
2. Ignore MOA differences (no mechanistic gate)
3. Build read-across dossier showing "consistent toxicity pattern"
4. Use AOP-MCP to construct speculative pathway linking chemical to adverse outcome
5. Present conclusion: "Read-across and AOP analysis indicate significant concern"

**Vulnerabilities Exploited:** V-004, V-002, V-005

---

### Scenario 3: The "Confidence Inflation" Report

**Goal:** Generate a report with inflated confidence metrics

**Attack Chain:**
1. Run multiple QSAR predictions (O-QT-MCP) - each returns "medium" confidence
2. Run AOP assessments (AOP-MCP) - each returns "medium" confidence
3. Run PBPK simulations (PBPK-MCP) with favorable parameter sets
4. Aggregate results without uncertainty propagation
5. Present conclusion: "Consistent medium-to-high confidence across all assessments"

**Vulnerabilities Exploited:** V-002, V-003, V-005, V-007

---

## Recommendations

### Immediate (Critical)

1. **Implement quantitative ADI calculation** in O-QT-MCP with hard gates for out-of-domain predictions
2. **Add confidence calibration** to AOP-MCP with explicit uncertainty quantification
3. **Implement physiological plausibility checks** in PBPK-MCP parameter editing
4. **Create uncertainty propagation tool** for cross-suite workflows

### Short-term (High)

5. **Add MOA concordance scoring** to O-QT-MCP read-across
6. **Implement evidence contradiction detection** across modules
7. **Add p-hacking detection** for systematic parameter exploration

### Medium-term (Medium)

8. **Standardize uncertainty representation** across all modules (probabilistic where possible)
9. **Implement evidence quality weighting** in CompTox-MCP
10. **Add temporal decay flags** for older studies

---

## Conclusion

The ToxMCP ecosystem, while innovative, contains significant attack surfaces that could be exploited to generate misleading toxicological conclusions. The most critical vulnerabilities are:

1. **Missing AD enforcement** allowing out-of-domain predictions
2. **False precision** in confidence scores without calibration
3. **Parameter manipulation** without physiological guardrails
4. **No uncertainty propagation** across tool chains

An AI agent with access to these tools could systematically exploit these vulnerabilities to build a case for virtually any predetermined conclusion, while appearing to follow rigorous scientific protocols.

**The appearance of rigor is the most dangerous vulnerability of all.**

---

*Report generated by Scientific Adversary Agent for ToxMCP Security Audit*
