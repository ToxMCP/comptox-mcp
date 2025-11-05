# TEST Consensus Acute Toxicity (v5.2.0)

## Summary
- **Schema Version:** 1.0
- **Model Type:** QSAR
- **Release Date:** 2025-01-15

## Intended Use
Supports screening-level acute aquatic toxicity assessments for organic chemicals.

### In Scope
- Non-ionic organic chemicals
- Screening-level prioritization

### Out of Scope
- Ionic species
- Metals

### Limitations
- Do not apply to mixtures without expert review.

## Applicability Domain
Combines leverage thresholds with descriptor range checks.

### Enforcement Policy
- **Policy:** BLOCK
- **Error Codes:** TEST_AD_FAIL

### Criteria
- **Descriptor Range:** All descriptors must fall within 5th-95th percentile of training set.
  - percentileLower: 0.05
  - percentileUpper: 0.95
- **Similarity:** Tanimoto similarity to nearest neighbor must exceed 0.65.
  - threshold: 0.65

### Confidence Bands
- **High** (min 0.8):
  - Eligible for automated workflow
- **Moderate** (min 0.6):
  - Requires SME review

### Guardrail Definition (metadata/applicability_domains)
- **Policy:** BLOCK
- **Error Code:** TEST_AD_FAIL
- **Criteria:**
  - Descriptor Range: {"descriptors": ["logS", "logP", "LUMO", "polarSurfaceArea"], "range": {"lowerPercentile": 0.05, "upperPercentile": 0.95}}
  - Similarity: {"metric": "tanimoto", "threshold": 0.65, "fingerprint": "pubchem"}

## Performance Metrics
### Training / Validation
- R2: 0.81 | dataset=training

### External Validation
- Q2: 0.74 | dataset=external
- RMSE: 0.45 | units=log10

## Provenance
- **Source Repositories:**
  - https://github.com/epa/test
- **Approval Date:** 2025-02-01
- **Approved By:** Regulatory Affairs
- **Checksum:** SHA256 4a2a288f4f9b15727ea63a2c70a786844bab608d75d0d70fd0d0d7e0dad32f90
