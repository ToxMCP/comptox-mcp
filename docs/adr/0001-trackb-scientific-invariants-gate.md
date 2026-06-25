# ADR 0001 — Track-B scientific-invariants gate on `prioritize_risk_signals`

- Status: Accepted
- Date: 2026-06-25

## Context

comptox-mcp wraps the EPA CompTox Dashboard / ccte APIs. The ToxMCP fleet runs a
Track-B "scientific-invariants" release gate that vendors a digest-pinned copy of
the `ToxMCP/toxmcp-schema-spine` policy engine and asserts, on every RELEASED
object that carries a SERVER-AUTHORED scientific conclusion, that the conclusion
does not overclaim (it must declare its uncertainty, must not authorize
risk/regulatory downstream uses, must carry the anti-overclaim flags, etc.).

The first decision is **candidacy**: does comptox-mcp emit a released object that
asserts an overclaim-able scientific conclusion, or is every released object a
faithful pass-through relay of external CompTox/ccte data?

### Candidacy finding

Inspecting the actual response builders (`src/epacomp_tox/resources/*`):

- The **bioactivity / chemical / exposure / cheminformatics** tools
  (`get_bioactivity_summary_by_dtxsid`, `get_bioactivity_aop`,
  `get_bioactivity_assay`, `resolve_chemical_identifier`, `search_chemical`,
  `structure_file`, `toxprints`, `ghs_links`, …) are **faithful pass-through
  relays**. Their builders `_ensure_list` / `to_serializable` the upstream EPA
  CompTox / ccte response and assert no server-authored scientific conclusion.
  These are NON-candidate surfaces — there is no server-emitted scientific
  invariant to gate (like the admetlab API proxy).

- `prioritize_risk_signals` (`PrioritizationResource._build_prioritization`) is
  **different**. It AUTHORS a conclusion ON TOP of the relayed evidence: it
  computes a screening margin of exposure (minimum available AED ÷ maximum
  available SEEM general exposure), assigns a qualitative `priorityBand`
  (`higher` / `moderate` / `lower` / `inconclusive`) from that margin, and stamps
  an anti-overclaim `caveats` / `limitations` surface ("Screening only; this
  output is not a regulatory risk determination."). That server-authored
  band + ratio is an interpretation / qualification / downstream-use surface — an
  overclaim-able scientific conclusion.

→ **comptox-mcp IS a Track-B candidate, and `prioritize_risk_signals` is the only
gated object.** In ToxMCP schema-spine terms it is exactly a
`BioactivityExposureRatioRecord.v1`: a margin-of-exposure ratio with an
`interpretationClass` / `actionability`, an uncertainty + confidence-ceiling
disclosure, an explicit downstream-use authorization surface, and the mandatory
`notARiskConclusion` / `notARegulatoryConclusion` flags.

## Decision

Add a hardened Track-B gate ON `prioritize_risk_signals` ONLY:

1. **Vendored, digest-pinned engine** — `vendor/schema-spine/` is a byte-authentic
   copy of the canonical engine at gitSha
   `e0a6a0581efd8dfd5b10c2de14435d87769c5944` (the same tree used by the
   metabolomics / proteomics / iata gates). `scripts/vendor_verify.py` recomputes
   the sha256 of every vendored file vs `VENDORED_FROM.json` and hard-fails on any
   drift; the bridge ALSO fails closed at runtime on `VENDOR_DIGEST_MISMATCH`.

2. **Fail-closed bridge** (`src/epacomp_tox/governance/spine_bridge.py`) — shells
   out to the vendored `run-policy.mjs`; every failure mode (missing node, non-zero
   exit, timeout, empty/garbled stdout, unrecognized schemaId, digest mismatch) is
   a BLOCK, never a skip/pass. The recognized-schemaId guard closes the engine's
   silent `valid:true` no-op for unknown ids.

3. **Source-contract guard at the TOP of `run_gate`**
   (`src/epacomp_tox/governance/source_contract.py` +
   `schemas/governance/prioritize_risk_signals.emission.schema.json`) — every
   released response is validated against the producer's STRICT
   `additionalProperties:false` emission contract BEFORE any projection. The
   contract was reconstructed by RUNNING the real
   `PrioritizationResource.prioritize_risk_signals` across its dtxsid /
   resolved-identifier / inconclusive / all-missing paths (including the
   optional-field paths: `identityResolution` only on the resolved path,
   `selectedMetric` / `selectedMetrics` null on the missing path). The load-bearing
   strict surfaces are the packet root, the `prioritization` conclusion block,
   `hazardSignal`, `exposureSignal`, and the four evidence slices. Genuinely-open
   producer maps that spread upstream EPA fields or resolver state (`chemicalRef`,
   `identityResolution`, `provenanceSummary`, the `selectedMetric` /
   `selectedMetrics` bags, `priorityHeuristic`) are `additionalProperties:true` ON
   PURPOSE (the over-tighten lesson; the projection never reads a free key off
   them). A response carrying any undeclared field at a strict level is a
   `SOURCE_CONTRACT_VIOLATION` that BLOCKS and is NEVER projected — this closes the
   producer-emission-contract dead-arm class.

4. **Projection from DECLARED fields only**
   (`src/epacomp_tox/governance/project_to_spine.py`) — a total, deterministic map
   from the response onto a `BioactivityExposureRatioRecord`. Every spine field is
   derived from a DECLARED producer field; any unmapped enum / missing required
   field raises `ProjectionIncompleteError` (a BLOCK), never a safe-default.

## Advertised codes (each proven to BITE on an Ajv-valid, producer-emittable fault)

- **`BER_NOT_RISK_OR_REGULATORY`** — `allowedDownstreamUses` is derived from the
  producer's DECLARED authored conclusion text (`basis` + `supportingSignals` +
  `caveats` + `limitations`). A faithful screening output authorizes only
  `screening_prioritization`; a producer regression whose authored conclusion LEAKS
  a risk/regulatory authorization ("acceptable daily intake derivation", "safe
  level", "reference dose for risk characterization") is producer-emittable +
  emission-schema-VALID and makes this code bite. A NEGATED honest disclaimer
  ("…is not a regulatory risk determination") is not mistaken for an authorization.

- **`BER_UNCERTAINTY_AND_CEILING_REQUIRED`** — `uncertaintyRefs` /
  `confidenceCeilingRefs` are derived from the producer's DECLARED uncertainty
  disclosure (`caveats` + `knownDataGaps` + `limitations`). A faithful output
  always declares the standing screening caveat, so it passes; a regression that
  emits a non-inconclusive band but DROPS its disclosure (empty caveats + no data
  gaps + no limitations — emission-valid, since `caveats` has no `minItems`) makes
  this code bite.

## Honest-dropped (advertised == actual coverage)

- **`BER_REQUIRES_COMPARABILITY`** — fires only when `interpretationClass` is not a
  comparable class. Every producer band maps FAITHFULLY to a comparable class
  (`higher`/`moderate`/`lower` → `prioritization_context`; `inconclusive` →
  `requires_review`, an honest non-claim). Forcing it to fire would require an
  UNFAITHFUL projection (mapping the honest `inconclusive` band to a non-comparable
  class), which would falsely RED a pristine inconclusive packet. Not
  producer-reachable. **Re-introduce** if the producer ever grows a band/state that
  asserts a genuinely non-comparable interpretation.

- **AI-provenance family** (`AI_GENERATED_POD_REQUIRES_DOMAIN_REVIEW`, …) —
  `prioritize_risk_signals` is a DETERMINISTIC screening heuristic; the released
  object carries no AI / model-use / generation-provenance field. (The repo's
  `agentic_sdk` material is SAMPLES only, not a released-object field.) Any
  `AssessmentRun` projection would hardcode `aiUse='none'` and the AI codes could
  fire only on a synthetic projected-object mutation — a structurally-unreachable
  dead arm. No `AssessmentRun` is projected; no AI code is advertised.
  **Re-introduce** if a released object ever carries AI-derived content.

- The cross-object exposure-internal-exposure-BER linkage check is a multi-payload
  arm gated on a `HandoffEnvelope`; this released object is a single self-contained
  conclusion, so no envelope is projected and that arm stays dormant.

## Re-introduction trigger (candidacy)

If comptox-mcp ever adds an INTERPRETIVE layer to a currently-relayed object — e.g.
`get_bioactivity_summary_by_dtxsid` / `get_bioactivity_aop` starts emitting a
server-authored confidence / qualification / adversity / downstream-use assertion
ON TOP of the relayed ccte data, or a new tool authors a hazard/risk conclusion —
that object becomes a Track-B candidate and must be added to the gate corpus +
projection.

## Consequences

- The gate is GREEN on the pristine corpus (the real producer's emitted shape) and
  BLOCKS only on a producer-emittable regression or a contract violation.
- It is **additive**: a new `scientific-invariants` job in `ci.yml`; no existing
  workflow (`scientific-validation`, `codeql`, `live-interop-smoke`, `release-sbom`,
  `endpoint-check`, `docs`, `dependency-review`) is changed or dispatched.
- On the free-plan repo the gate is ADVISORY (no required-status-checks). **Promote**
  it to a required status check when the repo moves to a plan with branch
  protection / rulesets — the gate already exits non-zero on any blocking code.
