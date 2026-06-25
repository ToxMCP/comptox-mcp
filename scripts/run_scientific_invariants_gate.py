#!/usr/bin/env python3
"""Track-B scientific-invariants gate (vendored schema-spine engine).

Validates each RELEASED SERVER-AUTHORED conclusion against its producer's STRICT
emission contract, projects it onto its canonical ToxMCP schema-spine shape, runs
the vendored, digest-pinned spine policy engine over the projection via a
fail-closed Node bridge, aggregates every blocking finding, and EXITS NON-ZERO if
any public-release-blocking code fires.

WHICH RELEASED OBJECTS ARE GATED (exhaustive candidacy — see the ADR)
---------------------------------------------------------------------
comptox-mcp wraps the EPA CompTox Dashboard / ccte APIs. EVERY released object
across ``src/epacomp_tox/resources/*.py`` was classified FAITHFUL-RELAY vs
SERVER-AUTHORED-CONCLUSION (full table in docs/adr/0001). The bioactivity /
chemical / exposure / hazard / cheminformatics tools and the interop evidence
SUMMARIES (hazard/exposure/bioactivity slices, PBPK context bundle) are FAITHFUL
PASS-THROUGH RELAYS — they ``_ensure_list`` / slice / count the upstream CompTox /
ccte payload and assert no server-authored scientific conclusion. The TWO
SERVER-AUTHORED-CONCLUSION surfaces — both gated here — are:

  1. ``prioritize_risk_signals`` -> spine ``BioactivityExposureRatioRecord.v1``.
     AUTHORS a margin-of-exposure ratio + a qualitative ``priorityBand`` risk-
     priority judgment + an anti-overclaim caveat / limitations surface.

  2. ``aopLinkageSummary`` -> spine ``ReadAcrossJustification.v1``. AUTHORS a
     server-computed ``confidence`` block (numeric score + qualitative band
     high/moderate/low/none) + a per-mapping ``evidenceDirection`` assertion ON
     TOP of the relayed CompTox AOP crosswalk rows. Released BOTH standalone
     (``build_aop_linkage_summary``) AND embedded in
     ``assemble_comptox_evidence_pack`` (``payload["aopLinkageSummary"]``) — ONE
     projection covers both release sites. An AOP linkage with a server-computed
     confidence is CONTEXT / MEMBERSHIP, NOT established causality and NOT a
     regulatory determination, so it is projected as a ``context_only``,
     ``notARegulatoryConclusion:true`` read-across justification (anti-overclaim
     ceiling).

SOURCE-CONTRACT GUARD (the dead-arm fix, runs FIRST, per-surface)
-----------------------------------------------------------------
Before any projection, every source block is validated against its surface's
STRICT emission schema (``schemas/governance/*.emission.schema.json``,
``additionalProperties:false`` at the load-bearing server-authored levels — the
``prioritization`` conclusion block; the aopLinkageSummary ``confidence`` block +
each ``mappings[]`` entry). An object that violates the contract — including any
UNDECLARED field at a strict level — is a ``SOURCE_CONTRACT_VIOLATION`` that BLOCKS
and is NEVER projected. The released response schemas are
``additionalProperties:true``, so without this guard a gate could "advertise" codes
that only fire on an invented field the real producer never stamps — a dead arm.
This guard makes that class impossible.

On the PRISTINE corpus this gate is GREEN. Its job is to BLOCK if a future change
ever lets a producer-emittable regression into a released conclusion.

ADVERTISED, PRODUCER-REACHABLE scientific codes (every one self-proven to BITE on
an emission-schema-VALID, producer-emittable fault through the real bridge — see
tests/governance/test_scientific_invariants_gate.py):

  prioritize_risk_signals (BioactivityExposureRatioRecord):
    BER_NOT_RISK_OR_REGULATORY            (the screening conclusion's authored
                                           basis/caveat LEAKS a risk/regulatory
                                           downstream-use authorization)
    BER_UNCERTAINTY_AND_CEILING_REQUIRED  (a non-inconclusive band whose
                                           uncertainty / screening-ceiling
                                           disclosure was dropped)

  aopLinkageSummary (ReadAcrossJustification):
    CATEGORY_CLAIM_UNCERTAINTY_REQUIRED   (a moderate/high server-computed
                                           confidence band whose uncertainty
                                           disclosure — provenance note /
                                           limitations / data-gaps — was dropped)
    READ_ACROSS_ANALOG_OUTSIDE_DOMAIN     (an actionable (non-``none``) confidence
                                           band asserted while an upstream crosswalk
                                           row carries a NON-supportive
                                           ``evidenceDirection`` — the linkage is not
                                           adequate for an actionable claim)

HONEST-DROPPED (advertised == actual coverage; documented N/A + re-introduction
path in the governance ADR + projection docstring) — NOT advertised, because no
DECLARED field can make them bite on a producer-emittable conclusion without an
unfaithful projection:

    BER_REQUIRES_COMPARABILITY
        — every producer band maps FAITHFULLY to a comparable interpretationClass
          (higher/moderate/lower -> prioritization_context; inconclusive ->
          requires_review). No band asserts a genuinely non-comparable
          interpretation.
    STRUCTURAL_SIMILARITY_ONLY_OVERCLAIM / READ_ACROSS_WITHOUT_ANALOG_JUSTIFICATION
        — the AOP linkage is ALWAYS an empirical toxcast-aeid category crosswalk
          (``hypothesisType=empirical_category``); no producer-emittable state maps
          to ``structural_similarity_only`` without an unfaithful projection.
    The AI-provenance family (AI_GENERATED_POD_REQUIRES_DOMAIN_REVIEW, ...)
        — both gated surfaces are deterministic heuristics; neither released object
          carries an AI / model-use field; any AssessmentRun projection would
          hardcode aiUse='none' (a structurally-unreachable dead arm).

  Meta fail-closed (synthesized by the guard / bridge / projection):
    SOURCE_CONTRACT_VIOLATION, ENGINE_UNAVAILABLE, UNRECOGNIZED_SPINE_SCHEMA_ID,
    VENDOR_DIGEST_MISMATCH, PROJECTION_INCOMPLETE

This gate is ADVISORY on the free-plan repo (no required-status-checks). PROMOTE-
TO-BLOCKING PATH: when the repo moves to a plan with branch protection / rulesets,
mark the ``scientific-invariants`` CI job a required status check — the gate
already exits non-zero on any blocking code.

Exit codes:
    0 — every source object passed the contract + every projected object passed
        the engine (no blocking code fired)
    1 — at least one blocking code fired (release-blocking regression or contract
        violation)
    2 — usage / corpus-loading error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from epacomp_tox.governance import project_to_spine as projector  # noqa: E402
from epacomp_tox.governance import source_contract  # noqa: E402
from epacomp_tox.governance import spine_bridge as bridge  # noqa: E402
from epacomp_tox.governance.errors import (  # noqa: E402
    PROJECTION_INCOMPLETE,
    BlockingFinding,
    ProjectionIncompleteError,
)
from epacomp_tox.governance.source_contract import (  # noqa: E402
    AOP_LINKAGE_EMISSION_SCHEMA_PATH,
    PRIORITIZE_EMISSION_SCHEMA_PATH,
)

# --------------------------------------------------------------------------- #
# Surfaces — each GATED SERVER-AUTHORED released object is a "surface": its strict
# emission contract, the block to validate/project (the whole packet, or a named
# sub-block of it for the embedded evidence-pack copy), and its projection fn.
# --------------------------------------------------------------------------- #


def _identity(packet: dict[str, Any]) -> dict[str, Any]:
    return packet


def _aop_subblock(packet: dict[str, Any]) -> dict[str, Any]:
    """Extract the aopLinkageSummary sub-block from an evidence-pack payload (or
    return the packet itself if it already IS a standalone aopLinkageSummary)."""
    block = packet.get("aopLinkageSummary")
    return block if isinstance(block, dict) else packet


class Surface:
    """One gated SERVER-AUTHORED released-object surface."""

    def __init__(
        self,
        *,
        name: str,
        schema_path,
        select,
        project,
        id_field: str,
    ) -> None:
        self.name = name
        self.schema_path = schema_path
        self.select = select  # packet -> the strict block to validate/project
        self.project = project  # block -> list[spine object]
        self.id_field = id_field


SURFACES: dict[str, Surface] = {
    "prioritize_risk_signals": Surface(
        name="prioritize_risk_signals",
        schema_path=PRIORITIZE_EMISSION_SCHEMA_PATH,
        select=_identity,
        project=projector.project_packet,
        id_field="bioactivityExposureRatioRecordId",
    ),
    "aop_linkage_summary": Surface(
        name="aop_linkage_summary",
        schema_path=AOP_LINKAGE_EMISSION_SCHEMA_PATH,
        select=_aop_subblock,
        project=projector.project_aop_packet,
        id_field="readAcrossJustificationId",
    ),
}

# The released-object corpus: committed golden fixtures (relative to repo root),
# each tagged with its surface. These are real producer-emitted shapes (generated
# by running the REAL producer, not hand-stubbed); the gate must be GREEN on every
# one — AND each must pass its producer's strict emission contract. The aop entries
# cover BOTH the standalone build_aop_linkage_summary surface AND the embedded
# assemble_comptox_evidence_pack copy (one projection, two release sites).
DEFAULT_CORPUS: tuple[tuple[str, str], ...] = (
    (
        "tests/fixtures/governance/released/pristine_prioritize_risk_signals.json",
        "prioritize_risk_signals",
    ),
    (
        "tests/fixtures/governance/released/pristine_aop_linkage_summary.json",
        "aop_linkage_summary",
    ),
    (
        "tests/fixtures/governance/released/pristine_evidence_pack_aop_linkage.json",
        "aop_linkage_summary",
    ),
)

# The public-release-blocking scientific codes this gate asserts on. (Meta codes
# from errors.META_FAIL_CLOSED_CODES — including SOURCE_CONTRACT_VIOLATION — are
# ALWAYS blocking and need no listing.) Every code here is self-proven to BITE on
# a producer-emittable, emission-schema-VALID fault through the real bridge. Codes
# that key on a non-comparable interpretation or an AI trace are deliberately
# ABSENT — no declared field can make them bite on a real producer-emitted
# conclusion (honest-dropped; see the governance ADR + module docstrings).
BLOCKING_SCIENTIFIC_CODES: frozenset[str] = frozenset(
    {
        # prioritize_risk_signals -> BioactivityExposureRatioRecord
        "BER_NOT_RISK_OR_REGULATORY",
        "BER_UNCERTAINTY_AND_CEILING_REQUIRED",
        # aopLinkageSummary -> ReadAcrossJustification (the server-authored
        # confidence-band AOP linkage; context/membership, not causality/regulatory)
        "CATEGORY_CLAIM_UNCERTAINTY_REQUIRED",
        "READ_ACROSS_ANALOG_OUTSIDE_DOMAIN",
    }
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _project_objects(
    block: dict[str, Any], rel_path: str, surface: Surface
) -> list[tuple[str, dict[str, Any]]]:
    """Project one released surface block into its spine object(s)."""
    objects = surface.project(block)
    out: list[tuple[str, dict[str, Any]]] = []
    for obj in objects:
        schema_id = obj.get("schemaId", "")
        kind = schema_id.rsplit("/", 1)[-1].split(".")[0] or "object"
        ref = obj.get(surface.id_field) or "object"
        out.append((f"{rel_path}#{kind}#{ref}", obj))
    return out


def run_gate(corpus: list[tuple[str, str]], *, emit_json: bool = False) -> int:
    findings: list[tuple[str, BlockingFinding]] = []
    checked = 0
    for rel, surface_name in corpus:
        surface = SURFACES.get(surface_name)
        if surface is None:
            print(
                f"[scientific-invariants] FAIL: unknown surface {surface_name!r} "
                f"for corpus file {rel}",
                file=sys.stderr,
            )
            return 2
        path = REPO_ROOT / rel
        if not path.exists():
            print(
                f"[scientific-invariants] FAIL: corpus file missing: {rel}",
                file=sys.stderr,
            )
            return 2
        source = _load(path)
        # Select the strict block for this surface (the whole packet, or the
        # embedded aopLinkageSummary sub-block of an evidence pack).
        block = surface.select(source)

        # SOURCE-CONTRACT GUARD (runs FIRST, before any projection). An object that
        # fails the producer's strict emission contract — including any undeclared
        # field at a strict level — is a SOURCE_CONTRACT_VIOLATION that BLOCKS and
        # is NEVER projected.
        contract_finding = source_contract.validate_against_schema(
            block, corpus=rel, schema_path=surface.schema_path
        )
        if contract_finding is not None:
            findings.append((rel, contract_finding))
            continue

        try:
            projected = _project_objects(block, rel, surface)
        except ProjectionIncompleteError as exc:
            findings.append(
                (
                    rel,
                    BlockingFinding.meta(
                        PROJECTION_INCOMPLETE, exc.message, path=exc.path, corpus=rel
                    ),
                )
            )
            continue

        for label, obj in projected:
            checked += 1
            result = bridge.validate_object(obj)
            for finding in result.findings:
                findings.append((label, finding))

    blocking = [
        (label, f)
        for (label, f) in findings
        if f.origin == "meta" or f.code in BLOCKING_SCIENTIFIC_CODES
    ]

    if emit_json:
        print(
            json.dumps(
                {
                    "checkedObjects": checked,
                    "blocking": [
                        {"object": label, **f.as_dict()} for (label, f) in blocking
                    ],
                    "allFindings": [
                        {"object": label, **f.as_dict()} for (label, f) in findings
                    ],
                },
                indent=2,
            )
        )

    if blocking:
        print(
            f"[scientific-invariants] BLOCK — {len(blocking)} release-blocking "
            f"finding(s) across {checked} projected object(s):",
            file=sys.stderr,
        )
        for label, f in blocking:
            print(
                f"  - [{f.origin}] {f.code} @ {label} {f.path}: {f.message}",
                file=sys.stderr,
            )
        return 1

    print(
        f"[scientific-invariants] OK — {checked} projected object(s) passed the "
        f"vendored spine policy engine (no release-blocking code fired).",
        file=sys.stderr,
    )
    return 0


def _parse_corpus_arg(items: list[str]) -> list[tuple[str, str]]:
    """Parse ``--corpus`` entries of the form ``PATH:SURFACE`` (surface optional;
    defaults to prioritize_risk_signals for back-compat)."""
    out: list[tuple[str, str]] = []
    for item in items:
        if "::" in item:
            path, surface = item.rsplit("::", 1)
        else:
            path, surface = item, "prioritize_risk_signals"
        out.append((path, surface))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus",
        nargs="*",
        default=None,
        help="Released JSON files to validate + project, each optionally tagged "
        "PATH::SURFACE (surface one of: "
        f"{', '.join(sorted(SURFACES))}; default surface prioritize_risk_signals). "
        "Default: the standard multi-surface corpus.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a machine-readable JSON report to stdout.",
    )
    args = parser.parse_args(argv)
    corpus = (
        list(DEFAULT_CORPUS) if args.corpus is None else _parse_corpus_arg(args.corpus)
    )
    return run_gate(corpus, emit_json=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
