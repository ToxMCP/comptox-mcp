"""Total, deterministic projection: prioritize_risk_signals -> schema-spine.

The schema-spine policy engine dispatches solely on ``payload.schemaId``; this
server's overclaim-able released object is the SERVER-AUTHORED
``prioritize_risk_signals`` conclusion, whose ``prioritization`` block is, in
spine terms, exactly a ``BioactivityExposureRatioRecord.v1`` — a margin-of-exposure
ratio (``berValue``) carrying a qualitative interpretation (``interpretationClass``
/ ``actionability``), an uncertainty / confidence-ceiling disclosure, an explicit
downstream-use authorization surface (``allowedDownstreamUses`` /
``prohibitedDownstreamUses``), and the mandatory ``notARiskConclusion`` /
``notARegulatoryConclusion`` anti-overclaim flags. Running the engine on the raw
camelCase response is a silent ``valid:true`` no-op. **This projection is where the
gate's correctness lives.**

WHY prioritize_risk_signals IS A CANDIDATE (and the relays are not)
------------------------------------------------------------------
The bioactivity / chemical / exposure tools (``get_bioactivity_summary_by_dtxsid``,
``get_bioactivity_aop``, ``get_bioactivity_assay``, ``resolve_chemical_identifier``,
``ghs_links`` …) are FAITHFUL PASS-THROUGH RELAYS: they ``_ensure_list`` /
``to_serializable`` the upstream EPA CompTox / ccte response and assert no
server-authored scientific conclusion. ``prioritize_risk_signals`` is different:
``PrioritizationResource._build_prioritization`` AUTHORS a conclusion ON TOP of the
relayed evidence — it computes a margin of exposure (minAED / maxSEEM), assigns a
qualitative ``priorityBand`` (higher / moderate / lower / inconclusive), and stamps
an anti-overclaim caveat / limitations surface. That server-authored band+ratio is
the overclaim-able surface this gate guards.

DECLARED-FIELD DISCIPLINE (the dead-arm fix)
--------------------------------------------
The producer's released schema is ``additionalProperties:true`` at the response
root and on ``prioritization``, so a gate could "advertise" codes that read an
invented authorization field the REAL producer never stamps — a dead arm. The
``source_contract`` guard now BLOCKS any object carrying such an undeclared field
at the strict packet-root / ``prioritization`` / ``hazardSignal`` / ``exposureSignal``
levels BEFORE projection, and this projection derives EVERY spine field from a
DECLARED producer field ONLY. The producer's declared ``prioritization`` fields
(verified by running ``PrioritizationResource.prioritize_risk_signals``):

  priorityBand, marginOfExposure, hazardPointOfDeparture, hazardUnit,
  exposureEstimate, exposureUnit, signalDirection, priorityHeuristic, basis,
  supportingSignals, caveats

plus the response-level ``limitations`` and ``knownDataGaps``.

WHAT IS PRODUCER-REACHABLE (advertised) AND WHAT IS HONEST-DROPPED
------------------------------------------------------------------
The engine's ``BioactivityExposureRatioRecord`` arm carries THREE single-object
codes (policy-validator.mjs lines 1220-1232). Reachability against THIS producer:

  * BER_NOT_RISK_OR_REGULATORY  (ADVERTISED) — fires when ``allowedDownstreamUses``
    contains a risk / regulatory / safe / ADI/RfD/TDI/... token. This projection
    derives ``allowedDownstreamUses`` from the producer's DECLARED authored
    conclusion text (``basis`` + ``supportingSignals`` + ``caveats`` +
    ``limitations``): a faithful screening output authorizes only
    ``screening_prioritization``, but a producer regression whose authored basis /
    caveat LEAKS a risk/regulatory authorization (e.g. "acceptable daily intake
    derivation", "safe level") is producer-emittable + emission-schema-VALID and
    makes this code BITE. This is the central anti-overclaim invariant: the
    screening conclusion must not silently authorize a risk/regulatory downstream
    use.

  * BER_UNCERTAINTY_AND_CEILING_REQUIRED  (ADVERTISED) — fires when
    ``uncertaintyRefs`` OR ``confidenceCeilingRefs`` lack a substantive ref. This
    projection derives both ref arrays from the producer's DECLARED uncertainty
    disclosure (``caveats`` + ``knownDataGaps`` + ``limitations``); a faithful
    screening output ALWAYS declares the standing screening caveat
    ("Screening only; this output is not a regulatory risk determination.") so the
    refs are substantive and it PASSES. A producer regression that emits a
    non-inconclusive band but DROPS its uncertainty / screening-ceiling disclosure
    (empty caveats + no data gaps) is producer-emittable + emission-schema-VALID
    (``caveats`` has no minItems) and makes this code BITE.

  * BER_REQUIRES_COMPARABILITY  (HONEST-DROPPED) — fires only when
    ``interpretationClass`` is NOT one of {screening_context, prioritization_context,
    requires_review}. This projection FAITHFULLY maps EVERY producer band to one of
    those passing classes (higher/moderate/lower -> prioritization_context;
    inconclusive -> requires_review, an honest non-claim). There is NO
    producer-emittable band that faithfully maps to ``not_interpretable`` /
    ``not_assessed``, so forcing this code to fire would require an UNFAITHFUL
    projection (mapping the honest ``inconclusive`` band to a non-comparable class),
    which would falsely RED a pristine inconclusive packet. Not producer-reachable
    -> NOT advertised. Re-introduce if the producer ever grows a band/state that
    asserts a genuinely non-comparable interpretation.

THE AI-PROVENANCE ARM IS N/A FOR THIS SERVER (honest-dropped; see ADR).
``prioritize_risk_signals`` is a DETERMINISTIC screening heuristic
(``_build_prioritization``): min-AED / max-SEEM ratio + threshold banding. The
released object carries NO AI / model-use / LLM / generation-provenance field. Any
``AssessmentRun`` projection would HARDCODE ``aiUse='none'`` and the AI codes could
fire only on a synthetic projected-object mutation — a structurally unreachable
dead arm. So no ``AssessmentRun`` is projected and no AI code is advertised. Nor is
a ``HandoffEnvelope`` projected, so the engine's cross-object
exposure-internal-exposure-BER linkage check (a multi-payload arm) stays dormant —
this released object is a single self-contained conclusion.

Design contract (non-negotiable):

* TOTAL & DETERMINISTIC — same input always yields the same projected object; no
  clocks, no randomness, no hidden defaults.
* FAITHFUL, never safe-defaulted — every projected field is DERIVED from a
  DECLARED source field. The downstream-use authorization + uncertainty disclosure
  come ONLY from the producer's declared authored conclusion text.
* ANY unmapped enum / missing required field raises ``ProjectionIncompleteError``
  (a BLOCK). It is NEVER silently defaulted to a safe branch.
"""

from __future__ import annotations

import re
from typing import Any

from epacomp_tox.governance.errors import ProjectionIncompleteError

# --- spine schemaIds ---------------------------------------------------------

BER_SCHEMA_ID = (
    "https://schemas.ngra.ai/toxmcp/BioactivityExposureRatioRecord.v1.schema.json"
)
MEASUREMENT_VALUE_SCHEMA_ID = (
    "https://schemas.ngra.ai/toxmcp/MeasurementValue.v1.schema.json"
)

#: The producer's generatedBy marker (provenanceSummary.generatedBy) and the
#: declared band enum, mirrored from PrioritizationResource.
_GENERATED_BY = "prioritize_risk_signals"
_PRIORITY_BANDS: frozenset[str] = frozenset(
    {"higher", "moderate", "lower", "inconclusive"}
)

# The risk/regulatory authorization lexicon mirrors the engine's
# INTERNAL_EXPOSURE_BLOCKED_DOWNSTREAM_USE_PATTERN (policy-validator.mjs line 68):
# a faithful screening conclusion must not author any of these as a downstream-use
# authorization. We scan the producer's authored conclusion text for an asserted
# (non-negated) risk/regulatory use and, if present, surface it verbatim in
# allowedDownstreamUses so the engine's BER_NOT_RISK_OR_REGULATORY bites.
_RISK_REGULATORY_AUTHORIZATION = re.compile(
    r"\b("
    r"risk assessment|risk determination|risk characteriz|risk[- ]?based decision|"
    r"regulatory (?:determination|decision|submission|acceptance)|"
    r"acceptable daily intake|reference dose|derived no effect level|"
    r"tolerable daily intake|margin of exposure (?:limit|threshold)|"
    r"health[- ]?based guidance|guidance value|threshold of toxicological concern|"
    r"safe (?:dose|level|exposure|threshold)|permitted daily exposure|"
    r"occupational exposure limit|market authoriz|"
    r"adi|rfd|tdi|dnel|oel|hbgv|pde|mrl|ttc"
    r")\b",
    re.IGNORECASE,
)

# A negation lead so an honest disclaimer ("this is NOT a regulatory risk
# determination") is never mistaken for an authorization. Mirrors the spirit of the
# engine's NEGATION_LEAD.
_NEGATION_NEAR = re.compile(
    r"\b(not|no|without|cannot|never|nor|n't|excludes?|prohibit(?:ed|s)?|"
    r"must not|does not|do not|is not|are not)\b[^.;:]{0,40}$",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _require(condition: bool, message: str, path: str = "$") -> None:
    if not condition:
        raise ProjectionIncompleteError(message, path=path)


def _prioritization(packet: dict[str, Any]) -> dict[str, Any]:
    block = packet.get("prioritization")
    _require(
        isinstance(block, dict),
        "Response has no object `prioritization` block; refusing to safe-default.",
        path="$.prioritization",
    )
    return block  # type: ignore[return-value]


def _priority_band(block: dict[str, Any]) -> str:
    band = block.get("priorityBand")
    _require(
        isinstance(band, str) and band in _PRIORITY_BANDS,
        f"Unmapped / missing priorityBand {band!r}; refusing to safe-default.",
        path="$.prioritization.priorityBand",
    )
    return band  # type: ignore[return-value]


def _chemical_id(packet: dict[str, Any]) -> str:
    ref = packet.get("chemicalRef")
    if isinstance(ref, dict):
        dtxsid = ref.get("dtxsid")
        if isinstance(dtxsid, str) and dtxsid.strip():
            return dtxsid.strip()
    _require(
        False,
        "Response has no chemicalRef.dtxsid; refusing to safe-default.",
        path="$.chemicalRef.dtxsid",
    )
    raise AssertionError  # unreachable


def _is_negated(text: str, match_start: int) -> bool:
    """True iff a negation lead appears in the run-up to ``match_start``."""
    window = text[max(0, match_start - 60) : match_start]
    return bool(_NEGATION_NEAR.search(window))


def _authored_conclusion_strings(
    packet: dict[str, Any], block: dict[str, Any]
) -> list[str]:
    """The producer's DECLARED authored conclusion text, in deterministic order.

    These are the only free-text surfaces the server itself AUTHORS (not relayed
    upstream data): the screening ``basis``, the ``supportingSignals``, the
    ``caveats``, and the response-level ``limitations``. The projection reads
    downstream-use authorizations + uncertainty disclosure off these declared
    fields only.
    """
    out: list[str] = []
    basis = block.get("basis")
    if isinstance(basis, str) and basis.strip():
        out.append(basis.strip())
    for key, src in (
        ("supportingSignals", block),
        ("caveats", block),
        ("limitations", packet),
    ):
        seq = src.get(key)
        if isinstance(seq, list):
            for item in seq:
                if isinstance(item, str) and item.strip():
                    out.append(item.strip())
    return out


def _allowed_downstream_uses(
    packet: dict[str, Any], block: dict[str, Any]
) -> list[str]:
    """Faithful downstream-use authorization derived from the DECLARED authored text.

    A faithful screening conclusion authorizes ONLY ``screening_prioritization``.
    If the producer's authored conclusion text ASSERTS (non-negated) a
    risk/regulatory downstream use, that exact phrase is surfaced as an authorized
    use so the engine's ``BER_NOT_RISK_OR_REGULATORY`` bites — the anti-overclaim
    invariant. An honest disclaimer ("not a regulatory risk determination") is
    negated and therefore NOT surfaced.
    """
    leaked: list[str] = []
    for text in _authored_conclusion_strings(packet, block):
        for m in _RISK_REGULATORY_AUTHORIZATION.finditer(text):
            if not _is_negated(text, m.start()):
                phrase = m.group(0).lower()
                if phrase not in leaked:
                    leaked.append(phrase)
    return ["screening_prioritization", *leaked]


def _uncertainty_refs(packet: dict[str, Any], block: dict[str, Any]) -> list[str]:
    """Faithful uncertainty refs from the DECLARED uncertainty disclosure.

    Derived from the producer's declared ``caveats`` + response-level
    ``knownDataGaps``. A faithful screening output ALWAYS declares the standing
    screening caveat, so this is substantive and PASSES. A producer regression that
    drops all caveats + declares no data gap yields no substantive ref -> the
    engine's ``BER_UNCERTAINTY_AND_CEILING_REQUIRED`` bites.
    """
    refs: list[str] = []
    for caveat in block.get("caveats") or []:
        if isinstance(caveat, str) and caveat.strip():
            refs.append(f"comptox:uncertainty:caveat:{_slug(caveat)}")
    for gap in packet.get("knownDataGaps") or []:
        if isinstance(gap, str) and gap.strip():
            refs.append(f"comptox:uncertainty:data-gap:{_slug(gap)}")
    return refs


def _confidence_ceiling_refs(
    packet: dict[str, Any], block: dict[str, Any]
) -> list[str]:
    """Faithful confidence-ceiling refs from the DECLARED limitations + caveats.

    The producer's declared ``limitations`` (and caveats) are exactly the
    confidence-ceiling disclosure ("screening prioritization, not final risk
    characterization"). A faithful output declares them, so refs are substantive
    and PASS. A regression dropping them yields no substantive ref ->
    ``BER_UNCERTAINTY_AND_CEILING_REQUIRED`` bites.
    """
    refs: list[str] = []
    for lim in packet.get("limitations") or []:
        if isinstance(lim, str) and lim.strip():
            refs.append(f"comptox:ceiling:limitation:{_slug(lim)}")
    for caveat in block.get("caveats") or []:
        if isinstance(caveat, str) and caveat.strip():
            refs.append(f"comptox:ceiling:caveat:{_slug(caveat)}")
    return refs


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text.strip().lower()).strip("-")[:80] or "x"


def _interpretation_class(band: str) -> str:
    """FAITHFUL band -> interpretationClass.

    higher/moderate/lower are computed screening-priority bands ->
    ``prioritization_context``; ``inconclusive`` is an honest non-claim the producer
    emits when core inputs are missing/incompatible -> ``requires_review`` (a
    passing class). Both are comparable classes so a pristine packet PASSES; see the
    BER_REQUIRES_COMPARABILITY honest-drop note in the module docstring.
    """
    if band in ("higher", "moderate", "lower"):
        return "prioritization_context"
    return "requires_review"  # inconclusive


def _actionability(band: str) -> str:
    return (
        "prioritization"
        if band in ("higher", "moderate", "lower")
        else "requires_review"
    )


def _ber_basis(block: dict[str, Any]) -> str:
    """FAITHFUL berBasis: the producer computes a screening ratio (min-AED/max-SEEM)
    when inputs are present, else nothing was computed."""
    moe = block.get("marginOfExposure")
    return (
        "screening_ratio"
        if isinstance(moe, (int, float)) and not isinstance(moe, bool)
        else "not_assessed"
    )


def _calculation_method(block: dict[str, Any]) -> str:
    moe = block.get("marginOfExposure")
    return (
        "screening"
        if isinstance(moe, (int, float)) and not isinstance(moe, bool)
        else "not_assessed"
    )


def _measurement_value(packet: dict[str, Any], block: dict[str, Any]) -> dict[str, Any]:
    """Project the producer's marginOfExposure -> spine MeasurementValue.

    A numeric MoE is a faithful ``numeric`` magnitude; a null MoE (inconclusive)
    is a faithful ``not_reported`` value. No magnitude is ever fabricated.
    """
    moe = block.get("marginOfExposure")
    sid = _chemical_id(packet)
    if isinstance(moe, (int, float)) and not isinstance(moe, bool):
        return {
            "schemaId": MEASUREMENT_VALUE_SCHEMA_ID,
            "measurementId": f"comptox:moe:{sid}",
            "valueType": "numeric",
            "originalValue": moe,
            "originalUnit": "dimensionless",
            "normalizedValue": moe,
            "normalizedUnit": "dimensionless",
            "qualifier": "approximately",
            "censoring": "none",
            "uncertainty": [],
        }
    return {
        "schemaId": MEASUREMENT_VALUE_SCHEMA_ID,
        "measurementId": f"comptox:moe:{sid}",
        "valueType": "not_reported",
        "originalValue": "not_assessed",
        "originalUnit": "dimensionless",
        "normalizedValue": "not_assessed",
        "normalizedUnit": "dimensionless",
        "qualifier": "not_reported",
        "censoring": "not_assessed",
        "uncertainty": [],
    }


def _limitations(packet: dict[str, Any], block: dict[str, Any]) -> list[str]:
    """Carry the producer's DECLARED limitations + caveats through as BER
    limitation strings (>=1 required by the spine schema).

    Faithful: derive from the response-level ``limitations`` plus the conclusion
    ``caveats``. If somehow none are declared, emit the canonical screening
    non-claim statement, never a fabricated placeholder."""
    out: list[str] = []
    for lim in packet.get("limitations") or []:
        if isinstance(lim, str) and lim.strip():
            out.append(lim.strip())
    for caveat in block.get("caveats") or []:
        if isinstance(caveat, str) and caveat.strip():
            out.append(caveat.strip())
    seen: set[str] = set()
    deduped: list[str] = []
    for item in out:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    if not deduped:
        deduped.append(
            "Screening prioritization signal only; not a point of departure, "
            "margin-of-exposure risk conclusion, adversity, or regulatory decision."
        )
    return deduped


# ---------------------------------------------------------------------------
# projection
# ---------------------------------------------------------------------------


def project_bioactivity_exposure_ratio(
    packet: dict[str, Any], *, ber_id: str | None = None
) -> dict[str, Any]:
    """Project a prioritize_risk_signals response -> spine BioactivityExposureRatioRecord.

    Every field is derived from a DECLARED producer field; the two advertised
    codes (BER_NOT_RISK_OR_REGULATORY, BER_UNCERTAINTY_AND_CEILING_REQUIRED) are
    reachable on producer-emittable, emission-schema-VALID faults. The record is
    always emitted with the mandatory ``notARiskConclusion`` /
    ``notARegulatoryConclusion`` flags true (the producer's screening conclusion is,
    by construction, neither a risk nor a regulatory determination), and a non-empty
    ``prohibitedDownstreamUses`` so the anti-overclaim boundary is explicit.
    """
    _require(
        isinstance(packet, dict),
        "Source response is not an object; refusing to safe-default.",
        path="$",
    )
    _require(
        (
            packet.get("provenanceSummary", {}).get("generatedBy") == _GENERATED_BY
            if isinstance(packet.get("provenanceSummary"), dict)
            else False
        ),
        "Response provenanceSummary.generatedBy is not 'prioritize_risk_signals'; "
        "refusing to project a non-prioritization object.",
        path="$.provenanceSummary.generatedBy",
    )
    block = _prioritization(packet)
    band = _priority_band(block)
    sid = _chemical_id(packet)

    return {
        "schemaId": BER_SCHEMA_ID,
        "bioactivityExposureRatioRecordId": ber_id or f"comptox:ber:{sid}",
        "podRef": f"comptox:hazard-pod:{sid}",
        "internalExposureRef": f"comptox:seem-exposure:{sid}",
        "comparabilityQualificationRef": f"comptox:comparability:{sid}",
        "berValue": _measurement_value(packet, block),
        "berBasis": _ber_basis(block),
        "calculationMethod": _calculation_method(block),
        "uncertaintyRefs": _uncertainty_refs(packet, block),
        "confidenceCeilingRefs": _confidence_ceiling_refs(packet, block),
        "interpretationClass": _interpretation_class(band),
        "actionability": _actionability(band),
        "allowedDownstreamUses": _allowed_downstream_uses(packet, block),
        "prohibitedDownstreamUses": [
            "risk_characterization",
            "regulatory_decision",
            "safe_level_or_reference_dose_derivation",
            "margin_of_exposure_risk_conclusion",
        ],
        "requiredReviewState": "machine_checked",
        "limitations": _limitations(packet, block),
        "notARiskConclusion": True,
        "notARegulatoryConclusion": True,
    }


def project_packet(packet: dict[str, Any]) -> list[dict[str, Any]]:
    """Project one released prioritize_risk_signals response to its spine object(s).

    A single self-contained server-authored conclusion -> a single
    ``BioactivityExposureRatioRecord``. (No AssessmentRun / HandoffEnvelope is
    emitted; their codes key on source fields the producer does not declare — see
    the module docstring.)
    """
    return [project_bioactivity_exposure_ratio(packet)]
