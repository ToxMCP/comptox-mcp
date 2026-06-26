# ADR 0001 — Track-B scientific-invariants gate on comptox-mcp server-authored conclusions

- Status: Accepted
- Date: 2026-06-25
- Revised: 2026-06-25 — scope correction. The original ADR claimed
  `prioritize_risk_signals` was "the ONLY gated released object". That candidacy
  recon was **not exhaustive**: `InteropResource._build_aop_linkage_summary` also
  AUTHORS a scientific conclusion (a server-computed `confidence` score + band +
  a per-mapping `evidenceDirection`) and is released BOTH standalone
  (`build_aop_linkage_summary`) AND embedded inside
  `assemble_comptox_evidence_pack` (`payload["aopLinkageSummary"]`). Both were
  left UNGATED. This revision enumerates EVERY released object, classifies each,
  and gates the second server-authored surface too.

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

### Exhaustive candidacy classification

EVERY released object across `src/epacomp_tox/resources/*.py` was inspected at its
actual response builder and classified **FAITHFUL-RELAY** (a pass-through of
external CompTox/ccte data, asserting no server-authored conclusion) vs
**SERVER-AUTHORED-CONCLUSION** (invents a score / band / qualification /
downstream-use / anti-overclaim surface). The full table:

| Resource file | Released object(s) | Classification | Gated? |
|---|---|---|---|
| `hazard.py` | `search_hazard`, `batch_search_hazard`, `get_hazard_toxval`/`batch_*`, `get_hazard_skin_eye`/`batch_*`, `get_hazard_cancer_summary`/`batch_*`, `get_hazard_genetox_summary`/`details`/`batch_*`, `get_hazard_adme_ivive`, `get_hazard_pprtv`, `get_hazard_iris`, `get_hazard_hawc`, `get_hazard_toxref`/`batch_*` | FAITHFUL-RELAY — every method is `_with_retry(client.X) → _ensure_list`; "summary" names are upstream CompTox endpoint names, not server scores | No (audited relay) |
| `bioactivity.py` | `search_bioactivity_terms`, `get_bioactivity_summary_by_dtxsid`/`aeid`/`tissue`, `get_bioactivity_data`/`batch_*`, `get_bioactivity_aed`/`batch_*`, `get_bioactivity_assay`, `batch_get_bioactivity_assay_annotations`, `get_bioactivity_assay_count`/`chemicals`, `get_bioactivity_aop`, `get_bioactivity_analytical_qc` | FAITHFUL-RELAY — pass-through of ccte bioactivity/AOP-crosswalk rows | No (audited relay) |
| `chemical.py` | `search_chemical`/`batch_*`, `resolve_chemical_identifier`, `get_chemical_details`/`batch_*`, `search_msready`, `get_chemical_fate_summary`/`details`, `get_chemical_extra_data`, `opsin_convert_name`, `indigo_convert_molfile` | FAITHFUL-RELAY — identity resolution + structure conversion echo upstream; `resolve_*` reports the resolver's own `searchModeUsed`, not a scientific judgment | No (audited relay) |
| `chemical_list.py` | `get_public_list_names`, `get_full_list` | FAITHFUL-RELAY | No (audited relay) |
| `cheminformatics.py` | (descriptor/structure helpers) | FAITHFUL-RELAY | No (audited relay) |
| `exposure.py` | `search_cpdat`, `search_httk`, `get_cpdat_vocabulary`, `search_qsurs`, `search_exposures` (+ helpers) | FAITHFUL-RELAY — pass-through of CPDat/HTTK/SEEM/QSUR rows | No (audited relay) |
| `metadata.py` | `metadata_get_model_card`, `metadata_list_applicability_domain`, `metadata_get_applicability_domain` | FAITHFUL-RELAY — echoes committed model-card / AD metadata | No (audited relay) |
| `interop.py` — evidence SUMMARIES | `assemble_comptox_evidence_pack`'s `hazardEvidenceSummary`, `exposureEvidenceSummary`, `bioactivityEvidenceSummary`; `build_pbpk_context_bundle` (`pbpkContextBundle`) | FAITHFUL-RELAY — slice / `recordCount` / `assayCount` / `activeAssayCount` are arithmetic COUNTS of upstream-flagged hitcalls + verbatim record bags; no server-invented score/band/qualification | No (audited relay) |
| `prioritization.py` | **`prioritize_risk_signals`** | **SERVER-AUTHORED-CONCLUSION** — `_build_prioritization` computes a margin of exposure (min AED ÷ max SEEM), assigns a qualitative `priorityBand`, stamps anti-overclaim caveats | **YES** → `BioactivityExposureRatioRecord.v1` |
| `interop.py` — AOP linkage | **`aopLinkageSummary`** (released standalone via `build_aop_linkage_summary` AND embedded in `assemble_comptox_evidence_pack["aopLinkageSummary"]`) | **SERVER-AUTHORED-CONCLUSION** — `_build_aop_linkage_summary` authors a numeric `confidence.score` (`0.2·[assays] + 0.1·len(mappings)`, capped 0.95), a qualitative `confidence.band` (`high`/`moderate`/`low`/`none` via `_confidence_band`), and a per-mapping `evidenceDirection` assertion ON TOP of the relayed crosswalk rows | **YES** → `ReadAcrossJustification.v1` |

→ **comptox-mcp IS a Track-B candidate. TWO released objects author a scientific
conclusion and are BOTH gated** (`prioritize_risk_signals` and `aopLinkageSummary`);
every other released object is an audited FAITHFUL-RELAY. The `aopLinkageSummary`
block is released at TWO sites (standalone + embedded in the evidence pack) but is
the SAME core builder, so ONE projection + ONE strict contract covers both.

In schema-spine terms:

- `prioritize_risk_signals` → `BioactivityExposureRatioRecord.v1`: a
  margin-of-exposure ratio with an `interpretationClass` / `actionability`, an
  uncertainty + confidence-ceiling disclosure, an explicit downstream-use
  authorization surface, and the mandatory `notARiskConclusion` /
  `notARegulatoryConclusion` flags.
- `aopLinkageSummary` → `ReadAcrossJustification.v1`: a category/grouping
  justification linking the chemical to AOP key events via an EMPIRICAL
  toxcast-aeid crosswalk, carrying a server-computed confidence. An AOP linkage
  with a server-computed confidence is **context / membership, NOT established
  causality and NOT a regulatory determination**, so it is projected with
  `targetClaimClass = context_only`, `hypothesisType = empirical_category`, and
  `notARegulatoryConclusion = true` (the anti-overclaim + confidence-ceiling +
  AOP-context-not-KER-evidence ceiling).

## Decision

Add a hardened Track-B gate over the TWO server-authored surfaces
(`prioritize_risk_signals` and `aopLinkageSummary`); leave every audited relay
ungated:

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

3. **Per-surface source-contract guard at the TOP of `run_gate`**
   (`src/epacomp_tox/governance/source_contract.py` + one strict emission schema
   per surface) — each released block is validated against ITS surface's STRICT
   `additionalProperties:false` emission contract BEFORE any projection. The shared
   validator core is `validate_against_schema(block, schema_path=…)`; each contract
   was reconstructed by RUNNING the real producer (including optional-field paths).

   - `schemas/governance/prioritize_risk_signals.emission.schema.json` — strict at
     the packet root, the `prioritization` conclusion block, `hazardSignal`,
     `exposureSignal`, and the four evidence slices. Genuinely-open producer maps
     (`chemicalRef`, `identityResolution`, `provenanceSummary`, the
     `selectedMetric` / `selectedMetrics` bags, `priorityHeuristic`) are
     `additionalProperties:true` ON PURPOSE (the over-tighten lesson).
   - `schemas/governance/aop_linkage_summary.emission.schema.json` — strict
     (`additionalProperties:false`) at the SERVER-AUTHORED `confidence` conclusion
     block (`score` / `band` / `basis`) and each `mappings[]` entry (whose
     `evidenceDirection` is the per-linkage direction assertion). The block ROOT is
     `additionalProperties:true` ON PURPOSE: the standalone response (annotated by
     `_annotate_public_payload`) carries extra envelope fields
     (`provenanceSummary` / `limitations` / `knownDataGaps` / `generatedFromTools` /
     `identityResolution`) that the embedded copy does not, so over-tightening the
     root would falsely reject one of the two faithful emissions; the relay bags
     (`chemicalRef`, `supportingAssays` items, `provenance`) are also open. The gate
     validates the standalone response root directly, and EXTRACTS the
     `aopLinkageSummary` sub-block from an evidence pack before validating.

   A block carrying any undeclared field at a strict level is a
   `SOURCE_CONTRACT_VIOLATION` that BLOCKS and is NEVER projected — closing the
   producer-emission-contract dead-arm class for both surfaces.

4. **Projection from DECLARED fields only**
   (`src/epacomp_tox/governance/project_to_spine.py`) — total, deterministic maps:
   `project_packet` → `BioactivityExposureRatioRecord`, and
   `project_aop_packet` → `ReadAcrossJustification`. Every spine field is derived
   from a DECLARED producer field; any unmapped enum / missing required field raises
   `ProjectionIncompleteError` (a BLOCK), never a safe-default. For the AOP linkage,
   the anti-overclaim mapping pins `hypothesisType = empirical_category`,
   `targetClaimClass = context_only`, `notARegulatoryConclusion = true`, and tracks
   the producer's authored band faithfully (`high → strong`, `moderate → moderate`,
   `low → weak`, `none → context_only`).

## Advertised codes (each proven to BITE on an Ajv-valid, producer-emittable fault)

### `prioritize_risk_signals` → `BioactivityExposureRatioRecord`

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

### `aopLinkageSummary` → `ReadAcrossJustification`

- **`CATEGORY_CLAIM_UNCERTAINTY_REQUIRED`** — fires when a moderate/high
  server-computed confidence band (a "high read-across claim") carries no
  substantive `uncertaintyRefs`. `uncertaintyRefs` are derived from the DECLARED
  disclosure surfaces present on BOTH the standalone and embedded forms
  (`provenance.notes`) plus the standalone-only `limitations` / `knownDataGaps`.
  (`confidence.basis` is DELIBERATELY excluded — it is a fixed boilerplate legend
  that is `minLength≥1`-required, so deriving a ref off it would make the refs
  unconditionally substantive, a dead arm.) A faithful linkage always carries the
  standing "CompTox-side linkage only; downstream mechanistic normalization belongs
  in aop-mcp" note, so it passes; a regression that emits a moderate/high band but
  DROPS the disclosure (empty `notes`, no `minItems`) makes this code bite.

- **`READ_ACROSS_ANALOG_OUTSIDE_DOMAIN`** — fires when `analogAdequacy` is not
  `adequate_with_limitations` while `actionability` is not `none`. `analogAdequacy`
  is `adequate_with_limitations` ONLY when the linkage has real mappings AND every
  mapping asserts a SUPPORTIVE `evidenceDirection`. A faithful supportive linkage is
  adequate + actionable (passes), or has no mappings → `not_assessed` + `none`
  (passes). The producer-emittable fault: a non-`none` confidence band (actionable)
  asserted while an upstream crosswalk row carries a NON-supportive `evidenceDirection`
  (`refutes` / `inconclusive` / `contradicts`) — emission-valid, since
  `evidenceDirection` rides verbatim from the relayed row — makes this code bite.
  This is the central anti-overclaim invariant: an actionable AOP-context confidence
  band may not be asserted over non-supportive / absent linkage evidence.

## Honest-dropped (advertised == actual coverage)

- **`BER_REQUIRES_COMPARABILITY`** — fires only when `interpretationClass` is not a
  comparable class. Every producer band maps FAITHFULLY to a comparable class
  (`higher`/`moderate`/`lower` → `prioritization_context`; `inconclusive` →
  `requires_review`, an honest non-claim). Forcing it to fire would require an
  UNFAITHFUL projection (mapping the honest `inconclusive` band to a non-comparable
  class), which would falsely RED a pristine inconclusive packet. Not
  producer-reachable. **Re-introduce** if the producer ever grows a band/state that
  asserts a genuinely non-comparable interpretation.

- **`STRUCTURAL_SIMILARITY_ONLY_OVERCLAIM` / `READ_ACROSS_WITHOUT_ANALOG_JUSTIFICATION`**
  (ReadAcrossJustification) — fire only when `hypothesisType ==
  structural_similarity_only` AND the claim is high. The `aopLinkageSummary` linkage
  is ALWAYS an empirical toxcast-aeid category crosswalk
  (`hypothesisType = empirical_category`); no producer-emittable state maps to
  `structural_similarity_only` without an unfaithful projection. **Re-introduce** if
  `_build_aop_linkage_summary` ever grows a structure-similarity-only linkage mode.

- **AI-provenance family** (`AI_GENERATED_POD_REQUIRES_DOMAIN_REVIEW`, …) — BOTH
  gated surfaces are DETERMINISTIC heuristics; neither released object carries an
  AI / model-use / generation-provenance field. (The repo's `agentic_sdk` material
  is SAMPLES only, not a released-object field.) Any `AssessmentRun` projection
  would hardcode `aiUse='none'` and the AI codes could fire only on a synthetic
  projected-object mutation — a structurally-unreachable dead arm. No `AssessmentRun`
  is projected; no AI code is advertised. **Re-introduce** if a released object ever
  carries AI-derived content.

- The cross-object exposure-internal-exposure-BER linkage check is a multi-payload
  arm gated on a `HandoffEnvelope`; both released objects are single self-contained
  conclusions, so no envelope is projected and that arm stays dormant.

## Re-introduction triggers (candidacy)

- If comptox-mcp ever adds an INTERPRETIVE layer to a currently-relayed object —
  e.g. `get_bioactivity_summary_by_dtxsid` / `get_bioactivity_aop` /
  `metadata_get_applicability_domain` starts emitting a server-authored confidence /
  qualification / adversity / downstream-use assertion ON TOP of the relayed ccte
  data, or one of the interop evidence SUMMARIES (`hazardEvidenceSummary`,
  `exposureEvidenceSummary`, `bioactivityEvidenceSummary`, `pbpkContextBundle`)
  grows a server-computed score/band/qualification rather than a verbatim
  slice/count — that object becomes a Track-B candidate and must be added to the
  gate corpus + projection.
- If `_build_aop_linkage_summary` ever raises its claim ceiling above AOP CONTEXT
  (e.g. it begins asserting mechanistic_support / causal_support / a KER-evidence
  claim, or maps a confidence band to a regulatory determination), the projection's
  `targetClaimClass = context_only` ceiling and the honest-dropped
  structural-similarity codes must be revisited.

## Consequences

- The gate is GREEN on the pristine corpus (the real producers' emitted shapes —
  the `prioritize_risk_signals` response plus BOTH aopLinkageSummary release sites:
  the standalone `build_aop_linkage_summary` response and the embedded
  `assemble_comptox_evidence_pack["aopLinkageSummary"]` sub-block) and BLOCKS only
  on a producer-emittable regression or a contract violation. The committed corpus
  is byte-stable (timestamp/trace provenance fields normalized to a sentinel the
  projection never reads); CI regenerates it and runs `git diff --exit-code` to
  prove the projections are TOTAL & DETERMINISTIC.
- It is **additive**: a new `scientific-invariants` job in `ci.yml`; no existing
  workflow (`scientific-validation`, `codeql`, `live-interop-smoke`, `release-sbom`,
  `endpoint-check`, `docs`, `dependency-review`) is changed or dispatched.
- On the free-plan repo the gate is ADVISORY (no required-status-checks). **Promote**
  it to a required status check when the repo moves to a plan with branch
  protection / rulesets — the gate already exits non-zero on any blocking code.
