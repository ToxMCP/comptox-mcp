# GenRA Read-Across Workflow (v2.1.0)

## Summary
- **Schema Version:** 1.0
- **Model Type:** Read-Across
- **Release Date:** 2025-03-05

## Intended Use
Supports regulatory read-across decisions for data gap filling and hazard assessment.

### In Scope
- Organic chemicals with available ToxCast/ToxVal analogues

### Out of Scope
- Chemicals lacking sufficient analogue coverage
- Mixtures

### Limitations
- Requires SME review when analogue similarity < 0.7.

## Applicability Domain
Composite checks for analogue similarity, data completeness, and evidence diversity.

### Enforcement Policy
- **Policy:** BLOCK
- **Error Codes:** GENRA_AD_FAIL

### Criteria
- **Similarity:** At least three structural analogues with Tanimoto similarity >= 0.7.
  - threshold: 0.7
  - minAnalogues: 3
- **Coverage:** Analogues must span at least two evidence domains (in vivo, in vitro, in silico).
  - minDomains: 2
- **Expert Rule:** Mode-of-action tags must align across selected analogues.
  - allowableMismatch: 1

### Confidence Bands
- **Robust** (min 0.8):
  - Eligible for automated dossier generation
- **Limited** (min 0.5):
  - Requires SME justification and documentation

### Guardrail Definition (metadata/applicability_domains)
- **Policy:** BLOCK
- **Error Code:** GENRA_AD_FAIL
- **Criteria:**
  - Similarity: {"metric": "tanimoto", "threshold": 0.7, "minAnalogues": 3}
  - Coverage: {"requirements": ["in vivo", "in vitro"], "minimumDomains": 2}
  - Expert Rule: {"rule": "Mode of action tags must align", "allowableMismatch": 1}

## Performance Metrics
### Training / Validation
- Coverage: 0.78 | dataset=historical read-across cases

### External Validation
- Accuracy: 0.72 | dataset=case studies
- Precision: 0.69 | dataset=case studies

## Provenance
- **Source Repositories:**
  - https://github.com/epa/genra
- **Approval Date:** 2025-03-10
- **Approved By:** Regulatory Affairs Read-Across Committee
- **Checksum:** SHA256 3ce4ec4983d3e7c6b2089b967679f5fc293096750293eb98d2b211f780a1f95e
