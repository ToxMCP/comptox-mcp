"""Track-B scientific-invariants governance for comptox-mcp.

This package holds the fail-closed bridge to the vendored, digest-pinned
schema-spine policy engine, the strict producer-emission-contract guard, and the
total native -> spine projection used by the scientific-invariants gate
(``scripts/run_scientific_invariants_gate.py``).

The gated released object is the SERVER-AUTHORED ``prioritize_risk_signals``
conclusion (``docs/contracts/schemas/risk/prioritize_risk_signals.response.schema.json``).
Unlike the bioactivity / chemical / exposure pass-through relays (which faithfully
echo external EPA CompTox / ccte data and assert no server-authored scientific
conclusion), ``prioritize_risk_signals`` adds an INTERPRETIVE layer ON TOP of the
relayed evidence: a margin-of-exposure ratio + a qualitative ``priorityBand``
risk-priority judgment + an anti-overclaim caveat/limitations surface. That makes
it a margin-of-exposure conclusion the spine canonicalizes as a
``BioactivityExposureRatioRecord.v1`` — an overclaim-able surface this gate guards.
Mirrors the proteomics / metabolomics / iata governance src-layout.
"""

from __future__ import annotations

__all__ = ["errors", "source_contract", "spine_bridge", "project_to_spine"]
