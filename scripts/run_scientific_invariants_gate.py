#!/usr/bin/env python3
"""Track-B scientific-invariants gate (vendored schema-spine engine).

Validates each RELEASED ``prioritize_risk_signals`` response against the
producer's STRICT emission contract, projects it onto its canonical ToxMCP
schema-spine ``BioactivityExposureRatioRecord`` shape, runs the vendored,
digest-pinned spine policy engine over the projection via a fail-closed Node
bridge, aggregates every blocking finding, and EXITS NON-ZERO if any
public-release-blocking code fires.

WHY ONLY prioritize_risk_signals IS GATED (candidacy)
-----------------------------------------------------
comptox-mcp wraps the EPA CompTox Dashboard / ccte APIs. Its bioactivity /
chemical / exposure tools (``get_bioactivity_summary_by_dtxsid``,
``get_bioactivity_aop``, ``get_bioactivity_assay``, ``resolve_chemical_identifier``,
``ghs_links``, ``toxprints``, ``structure_file``, ``search_chemical`` …) are
FAITHFUL PASS-THROUGH RELAYS — they echo the upstream CompTox / ccte payload and
assert no server-authored scientific conclusion, so there is no server-emitted
scientific invariant to gate. ``prioritize_risk_signals`` is the one released
object that AUTHORS a conclusion ON TOP of the relayed evidence: a
margin-of-exposure ratio + a qualitative ``priorityBand`` risk-priority judgment +
an anti-overclaim caveat / limitations surface. That server-authored band+ratio is
the overclaim-able surface this gate guards; in spine terms it is a
``BioactivityExposureRatioRecord.v1``.

SOURCE-CONTRACT GUARD (the dead-arm fix, runs FIRST)
----------------------------------------------------
Before any projection, every source object is validated against the producer's
STRICT emission schema
(``schemas/governance/prioritize_risk_signals.emission.schema.json``,
``additionalProperties:false`` at the load-bearing packet-root / ``prioritization``
/ ``hazardSignal`` / ``exposureSignal`` / evidence-slice levels). An object that
violates the contract — including any UNDECLARED field at a strict level — is a
``SOURCE_CONTRACT_VIOLATION`` that BLOCKS and is NEVER projected. The released
response schema is ``additionalProperties:true``, so without this guard a gate
could "advertise" codes that only fire on an invented authorization field the real
``PrioritizationResource`` never stamps — a dead arm. This guard makes that class
impossible.

On the PRISTINE corpus this gate is GREEN. Its job is to BLOCK if a future change
ever lets a producer-emittable regression into a released conclusion.

ADVERTISED, PRODUCER-REACHABLE scientific codes (every one self-proven to BITE on
an emission-schema-VALID, producer-emittable fault through the real bridge — see
tests/governance/test_scientific_invariants_gate.py):

    BER_NOT_RISK_OR_REGULATORY            (the screening conclusion's authored
                                           basis/caveat LEAKS a risk/regulatory
                                           downstream-use authorization)
    BER_UNCERTAINTY_AND_CEILING_REQUIRED  (a non-inconclusive band whose
                                           uncertainty / screening-ceiling
                                           disclosure was dropped)

HONEST-DROPPED (advertised == actual coverage; documented N/A + re-introduction
path in the governance ADR + projection docstring) — NOT advertised, because no
DECLARED field can make them bite on a producer-emittable conclusion without an
unfaithful projection:

    BER_REQUIRES_COMPARABILITY
        — every producer band maps FAITHFULLY to a comparable interpretationClass
          (higher/moderate/lower -> prioritization_context; inconclusive ->
          requires_review). No band asserts a genuinely non-comparable
          interpretation.
    The AI-provenance family (AI_GENERATED_POD_REQUIRES_DOMAIN_REVIEW, ...)
        — prioritize_risk_signals is a deterministic screening heuristic; the
          released object carries no AI / model-use field; any AssessmentRun
          projection would hardcode aiUse='none' (a structurally-unreachable dead
          arm).

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

# The released-object corpus: committed golden prioritize_risk_signals fixtures
# (relative to repo root). These are real producer-emitted shapes (generated by
# running PrioritizationResource.prioritize_risk_signals, not hand-stubbed); the
# gate must be GREEN on every one — AND each must pass the producer's strict
# emission contract.
DEFAULT_CORPUS: tuple[str, ...] = (
    "tests/fixtures/governance/released/pristine_prioritize_risk_signals.json",
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
        "BER_NOT_RISK_OR_REGULATORY",
        "BER_UNCERTAINTY_AND_CEILING_REQUIRED",
    }
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _project_objects(
    source: dict[str, Any], rel_path: str
) -> list[tuple[str, dict[str, Any]]]:
    """Project one released response into its spine object(s)."""
    objects = projector.project_packet(source)
    out: list[tuple[str, dict[str, Any]]] = []
    for obj in objects:
        schema_id = obj.get("schemaId", "")
        kind = schema_id.rsplit("/", 1)[-1].split(".")[0] or "object"
        ref = obj.get("bioactivityExposureRatioRecordId") or "object"
        out.append((f"{rel_path}#{kind}#{ref}", obj))
    return out


def run_gate(corpus: list[str], *, emit_json: bool = False) -> int:
    findings: list[tuple[str, BlockingFinding]] = []
    checked = 0
    for rel in corpus:
        path = REPO_ROOT / rel
        if not path.exists():
            print(
                f"[scientific-invariants] FAIL: corpus file missing: {rel}",
                file=sys.stderr,
            )
            return 2
        source = _load(path)

        # SOURCE-CONTRACT GUARD (runs FIRST, before any projection). An object that
        # fails the producer's strict emission contract — including any undeclared
        # field at a strict level — is a SOURCE_CONTRACT_VIOLATION that BLOCKS and
        # is NEVER projected.
        contract_finding = source_contract.validate_source_packet(source, corpus=rel)
        if contract_finding is not None:
            findings.append((rel, contract_finding))
            continue

        try:
            projected = _project_objects(source, rel)
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus",
        nargs="*",
        default=list(DEFAULT_CORPUS),
        help="Released prioritize_risk_signals JSON files to validate + project "
        "(default: standard corpus).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a machine-readable JSON report to stdout.",
    )
    args = parser.parse_args(argv)
    return run_gate(args.corpus, emit_json=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
