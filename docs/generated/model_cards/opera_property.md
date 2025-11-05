# OPERA Property Predictions (v3.6.1)

## Summary
- **Schema Version:** 1.0
- **Model Type:** QSAR
- **Release Date:** 2025-02-20

## Intended Use
Supports exposure assessment workflows requiring physicochemical property estimates for organic chemicals.

### In Scope
- Neutral organic chemicals
- Screening-level exposure modelling

### Out of Scope
- Inorganic substances
- Highly ionized species

### Limitations
- Predictions outside training descriptor ranges may be unreliable.

## Applicability Domain
Descriptor range checks plus nearest-neighbor similarity enforced before prediction delivery.

### Enforcement Policy
- **Policy:** WARN
- **Error Codes:** OPERA_AD_WARN

### Criteria
- **Descriptor Range:** Each descriptor must fall within training min/max after scaling.
  - mode: min_max
- **Similarity:** Average Tanimoto similarity to top 5 training neighbors >= 0.6.
  - threshold: 0.6
  - neighbors: 5

### Confidence Bands
- **High** (min 0.75):
  - Auto-approve
- **Low** (min 0.5):
  - Escalate to SME

### Guardrail Definition (metadata/applicability_domains)
- **Policy:** WARN
- **Error Code:** OPERA_AD_WARN
- **Criteria:**
  - Descriptor Range: {"descriptors": ["atomCount", "bondCount", "polarSurfaceArea"], "range": {"mode": "min_max"}}
  - Similarity: {"metric": "tanimoto", "threshold": 0.6, "neighbors": 5}

## Performance Metrics
### Training / Validation
- R2: 0.92 | dataset=training

### External Validation
- RMSE: 0.31 | dataset=external | units=log
- RMSE: 0.45 | dataset=external | units=log mol/L

## Provenance
- **Source Repositories:**
  - https://github.com/kmansouri/OPERA
- **Approval Date:** n/a
- **Approved By:** Pending
- **Checksum:** SHA256 79af18b3515e9a1d69037e2a154c7c6088cf3fae8c388ff901abdadf5a304a52
