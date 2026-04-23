# Portable CompTox Schemas

The `schemas/` directory publishes portable evidence objects for cross-suite handoff.

- `docs/contracts/schemas/`: MCP response wrappers for live tool responses.
- `schemas/`: portable objects that downstream MCPs and orchestrators can consume without depending on a specific transport call.

Portable schema versions are intentionally independent from package patch releases.
For example, a package cleanup release may tighten docs, tests, or release tooling
without changing the `*.v1.json` portable object family.

Current portable objects:

- `chemicalIdentityRecord.v1.json`
- `hazardEvidenceSummary.v1.json`
- `exposureEvidenceSummary.v1.json`
- `bioactivityEvidenceSummary.v1.json`
- `aopLinkageSummary.v1.json`
- `pbpkContextBundle.v1.json`
- `comptoxEvidencePack.v1.json`
- `comptox_model_card.schema.json`

Design rules:

- Objects are lean and composable.
- CompTox owns evidence ingress and handoff packaging, not downstream AOP semantics or PBPK execution outputs.
- Model-card semantics are reused from `comptox_model_card.schema.json` instead of cloned into a second schema family.
- Example instances live under `schemas/examples/` and are validated in tests.
