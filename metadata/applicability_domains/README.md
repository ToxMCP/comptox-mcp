# Applicability Domain Reference Data

Machine-readable definitions for applicability domain (AD) guardrails. Each JSON file aligns with a predictive model card and provides detailed parameters used by `PredictiveServiceBase` implementations during AD enforcement.

Conventions:
- One JSON per model (e.g., `test_consensus_ad.json`, `opera_property_ad.json`, `genra_read_across_ad.json`).
- Each file contains descriptors, thresholds, similarity parameters, and references.
- Files should be versioned alongside model cards and validated in CI (Task 2.5).
