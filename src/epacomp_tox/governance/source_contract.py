"""Fail-closed PRODUCER EMISSION-CONTRACT validation for the Track-B gate.

Before projecting a released ``prioritize_risk_signals`` response onto the spine,
the gate MUST validate the raw source object against the producer's STRICT
emission contract — the ``additionalProperties:false`` JSON schema at
``schemas/governance/prioritize_risk_signals.emission.schema.json``.

WHY THIS GUARD EXISTS (the dead-arm root cause it closes)
---------------------------------------------------------
A gate that projects FIRST and validates never (or validates a projected object,
not the source object) can "advertise" public-release-blocking codes whose only
trigger is a SOURCE field the producer's own contract cannot carry. Such a code
bites only on a hand-crafted, schema-INVALID fixture (one carrying an undeclared
field) and NEVER on an object the real producer emits — a DEAD ARM.

The comptox ``prioritize_risk_signals`` released schema
(``docs/contracts/schemas/risk/prioritize_risk_signals.response.schema.json``) is
``additionalProperties:true`` at the response root and at the ``prioritization``
block — it would accept extra fields. A gate that read an invented downstream-use
or authorization field off such a response could "advertise" codes that only fire
on a fixture the published schema tolerates but the REAL producer
(``PrioritizationResource._build_prioritization``) never stamps.

This module is the structural fix. The strict emission schema declares EVERY
field the real producer serializes (verified by RUNNING
``PrioritizationResource.prioritize_risk_signals`` across its dtxsid /
resolved-identifier / inconclusive / all-missing paths, not a stale fixture) and
forbids any other at the load-bearing packet-root / ``prioritization`` /
``hazardSignal`` / ``exposureSignal`` / evidence-slice levels
(``additionalProperties:false``). Every source object is validated against it at
the TOP of ``run_gate`` BEFORE any projection. An object that FAILS the contract
is a ``SOURCE_CONTRACT_VIOLATION`` meta finding that BLOCKS (exit 1) and is NEVER
projected / safe-defaulted. A smuggled undeclared field (an authorization flag, a
``riskDetermination`` block, any field outside the declared set on the conclusion
block) is rejected here, so the dead-arm class cannot silently return.

(Genuinely-open producer maps — ``chemicalRef`` / ``identityResolution`` /
``provenanceSummary`` (spread upstream EPA CompTox identity + resolver state), the
``selectedMetric`` / ``selectedMetrics`` evidence bags (spread the upstream
ccte / SEEM / HTTK / MMDB / CPDat record fields verbatim), and ``priorityHeuristic``
(a fixed heuristic legend) — are declared ``additionalProperties:true`` ON PURPOSE:
over-tightening them would falsely reject a faithful emission, the over-tighten
lesson. They are NOT a load-bearing strict surface; the projection never reads a
free key off them.)

FAIL-CLOSED / DEPENDENCY-FREE
-----------------------------
The validator is a small, self-contained Draft-07 *subset* checker covering
exactly the keywords the emission schema uses (``$ref`` to
``#/definitions/<name>``, ``definitions``, ``type`` (string OR a
``[type, "null"]`` union), ``properties``, ``required``, ``enum``, ``const``,
``additionalProperties``, ``items``, ``minItems``, ``minLength``, ``minimum``,
``format: date-time``). It depends on nothing outside the standard library, so the
guard can never be silently skipped because an optional dependency is missing. A
schema we cannot load, or a keyword we do not recognise appearing in the schema, is
itself treated as a hard block (we refuse to under-validate).
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from epacomp_tox.governance.errors import SOURCE_CONTRACT_VIOLATION, BlockingFinding

__all__ = [
    "SOURCE_CONTRACT_VIOLATION",
    "validate_source_packet",
    "validate_against_schema",
    "PRIORITIZE_EMISSION_SCHEMA_PATH",
    "AOP_LINKAGE_EMISSION_SCHEMA_PATH",
]

# .../src/epacomp_tox/governance/source_contract.py
# -> repo root is parents[3].
_REPO_ROOT = Path(__file__).resolve().parents[3]
_GOVERNANCE_SCHEMA_DIR = _REPO_ROOT / "schemas" / "governance"

#: The prioritize_risk_signals producer STRICT emission contract (the original,
#: whole-packet-root contract). Kept as the default of ``validate_source_packet``
#: for backward compatibility.
PRIORITIZE_EMISSION_SCHEMA_PATH = (
    _GOVERNANCE_SCHEMA_DIR / "prioritize_risk_signals.emission.schema.json"
)
#: The aopLinkageSummary producer STRICT emission contract — the SERVER-AUTHORED
#: confidence-band conclusion surface embedded in BOTH build_aop_linkage_summary
#: and assemble_comptox_evidence_pack (validated against the aopLinkageSummary
#: block).
AOP_LINKAGE_EMISSION_SCHEMA_PATH = (
    _GOVERNANCE_SCHEMA_DIR / "aop_linkage_summary.emission.schema.json"
)

# Back-compat alias used by the original prioritize gate path.
_EMISSION_SCHEMA_PATH = PRIORITIZE_EMISSION_SCHEMA_PATH

# The exact, bounded set of Draft-07 keywords the emission schema uses. If the
# schema ever grows a keyword outside this set, the loader REFUSES it
# (fail-closed: we will not silently under-validate a contract we cannot fully
# enforce).
_SUPPORTED_KEYWORDS: frozenset[str] = frozenset(
    {
        "$schema",
        "$id",
        "$ref",
        "definitions",
        "title",
        "description",
        "type",
        "properties",
        "required",
        "enum",
        "const",
        "additionalProperties",
        "items",
        "minItems",
        "minLength",
        "minimum",
        "format",
        "default",
    }
)

# RFC3339 date-time. Tolerant of an offset or a ``Z`` zone; requires a real
# T-separated time. A non-conforming string is a contract violation.
_DATE_TIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|[+-]\d{2}:\d{2})$"
)


class SchemaUnsupportedError(Exception):
    """The emission schema uses a keyword the validator does not enforce.

    Raised at load time so the gate fails closed rather than under-validating.
    """


def _assert_supported(node: Any, where: str) -> None:
    """Recursively confirm every schema node uses only enforced keywords.

    Structure-aware: ``properties`` and ``definitions`` map NAMES (arbitrary, not
    keywords) to subschemas, so we recurse into their VALUES only; ``items`` is
    itself a subschema; ``enum`` / ``const`` / ``required`` carry data values
    (not subschemas), so they are NOT recursed into. A subschema using any
    keyword outside ``_SUPPORTED_KEYWORDS`` is a hard fail.
    """
    if not isinstance(node, dict):
        return
    for key in node:
        if key not in _SUPPORTED_KEYWORDS:
            raise SchemaUnsupportedError(
                f"Emission schema uses unsupported keyword {key!r} at {where}; "
                "the source-contract validator refuses to under-validate."
            )
    for container in ("properties", "definitions"):
        sub = node.get(container)
        if isinstance(sub, dict):
            for pname, subschema in sub.items():
                _assert_supported(subschema, f"{where}.{container}.{pname}")
    items = node.get("items")
    if isinstance(items, dict):
        _assert_supported(items, f"{where}.items")


@lru_cache(maxsize=8)
def _load_emission_schema(schema_path: Path) -> dict[str, Any]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if not isinstance(schema, dict):
        raise SchemaUnsupportedError("Emission schema root is not an object.")
    _assert_supported(schema, "$")
    return schema


def _emission_schema() -> dict[str, Any]:
    """The original prioritize_risk_signals emission schema (back-compat)."""
    return _load_emission_schema(PRIORITIZE_EMISSION_SCHEMA_PATH)


def _resolve_ref(node: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
    """Resolve a local ``$ref`` of the form ``#/definitions/<name>``.

    Only the bounded local-definitions form the emission schema actually uses is
    supported; any other ``$ref`` form is a hard block.
    """
    ref = node.get("$ref")
    if not isinstance(ref, str) or not ref.startswith("#/definitions/"):
        raise SchemaUnsupportedError(
            f"Unsupported $ref form {ref!r}; the source-contract validator only "
            "resolves local #/definitions/<name> references."
        )
    name = ref[len("#/definitions/") :]
    definitions = root.get("definitions")
    if not isinstance(definitions, dict) or name not in definitions:
        raise SchemaUnsupportedError(
            f"$ref target {ref!r} is not present in the schema's definitions."
        )
    target = definitions[name]
    if not isinstance(target, dict):
        raise SchemaUnsupportedError(f"$ref target {ref!r} is not an object schema.")
    return target


def _type_ok(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "null":
        return value is None
    return False


def _type_matches(value: Any, expected: Any) -> bool:
    """Match ``value`` against a string ``type`` OR a ``[type, ...]`` union.

    The emission contract uses ``["number", "null"]`` / ``["string", "null"]`` /
    ``["object", "null"]`` for the producer's genuinely-nullable conclusion fields
    (``marginOfExposure``, ``hazardUnit``, the metric bags, ...). A union of
    non-string entries, or an unknown type token, is a schema we refuse to
    under-validate.
    """
    if isinstance(expected, str):
        return _type_ok(value, expected)
    if isinstance(expected, list):
        if not all(isinstance(t, str) for t in expected):
            raise SchemaUnsupportedError(
                f"Unsupported non-string type entry in union {expected!r}."
            )
        return any(_type_ok(value, t) for t in expected)
    raise SchemaUnsupportedError(f"Unsupported type form {expected!r}.")


def _validate(
    node: dict[str, Any],
    value: Any,
    path: str,
    errors: list[str],
    root: dict[str, Any],
) -> None:
    """Validate ``value`` against schema ``node`` (Draft-07 subset)."""
    if "$ref" in node:
        _validate(_resolve_ref(node, root), value, path, errors, root)
        return

    expected_type = node.get("type")
    if expected_type is not None and not _type_matches(value, expected_type):
        errors.append(f"{path}: expected type {expected_type!r}")
        return  # type mismatch makes deeper checks meaningless

    if "const" in node and value != node["const"]:
        errors.append(f"{path}: expected const {node['const']!r}")

    if "enum" in node and value not in node["enum"]:
        errors.append(f"{path}: value {value!r} not in enum {node['enum']!r}")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = node.get("minimum")
        if isinstance(minimum, (int, float)) and not isinstance(minimum, bool):
            if value < minimum:
                errors.append(f"{path}: less than minimum {minimum}")

    if isinstance(value, str):
        min_len = node.get("minLength")
        if isinstance(min_len, int) and len(value) < min_len:
            errors.append(f"{path}: shorter than minLength {min_len}")
        fmt = node.get("format")
        if fmt == "date-time" and not _DATE_TIME_RE.match(value):
            errors.append(f"{path}: not an RFC3339 date-time")

    if isinstance(value, dict):
        props: dict[str, Any] = node.get("properties", {}) or {}
        for req in node.get("required", []) or []:
            if req not in value:
                errors.append(f"{path}: missing required property {req!r}")
        # additionalProperties:false is the load-bearing strict guard — an
        # undeclared field is a contract violation here, which is exactly what
        # closes the dead-arm class (a smuggled authorization / riskDetermination
        # field on the conclusion block fails here). When additionalProperties is
        # true / omitted (the genuinely-open producer maps), no extra-property
        # check runs — by design.
        if node.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    errors.append(
                        f"{path}: additional property {key!r} is not permitted "
                        "(producer emission contract is additionalProperties:false)"
                    )
        for key, subschema in props.items():
            if key in value and isinstance(subschema, dict):
                _validate(subschema, value[key], f"{path}.{key}", errors, root)

    if isinstance(value, list):
        min_items = node.get("minItems")
        if isinstance(min_items, int) and len(value) < min_items:
            errors.append(f"{path}: fewer than minItems {min_items}")
        item_schema = node.get("items")
        if isinstance(item_schema, dict):
            for idx, item in enumerate(value):
                _validate(item_schema, item, f"{path}[{idx}]", errors, root)


def validate_against_schema(
    source: Any, *, corpus: str, schema_path: Path
) -> BlockingFinding | None:
    """Validate one raw source object against a named STRICT emission schema.

    Returns a ``SOURCE_CONTRACT_VIOLATION`` blocking meta finding if the object
    fails the contract (including any undeclared / schema-forbidden field at a
    strict ``additionalProperties:false`` level), else ``None``.

    A schema we cannot load / fully enforce is itself a hard block (fail-closed).
    This is the multi-surface entry point: each gated SERVER-AUTHORED surface
    (prioritize_risk_signals, aopLinkageSummary, ...) supplies its own strict
    contract path; the validator core is shared.
    """
    try:
        schema = _load_emission_schema(schema_path)
    except (OSError, json.JSONDecodeError, SchemaUnsupportedError) as exc:
        return BlockingFinding.meta(
            SOURCE_CONTRACT_VIOLATION,
            f"Producer emission schema could not be loaded/enforced: {exc}",
            path="$",
            corpus=corpus,
        )

    errors: list[str] = []
    try:
        _validate(schema, source, "$", errors, schema)
    except SchemaUnsupportedError as exc:
        return BlockingFinding.meta(
            SOURCE_CONTRACT_VIOLATION,
            f"Producer emission schema could not be fully enforced: {exc}",
            path="$",
            corpus=corpus,
        )
    if errors:
        return BlockingFinding.meta(
            SOURCE_CONTRACT_VIOLATION,
            "Source object violates the producer's strict emission contract "
            f"({schema_path.name}): " + "; ".join(errors[:8]),
            path=errors[0].split(":", 1)[0] if errors else "$",
            corpus=corpus,
        )
    return None


def validate_source_packet(source: Any, *, corpus: str) -> BlockingFinding | None:
    """Validate a raw ``prioritize_risk_signals`` response against its STRICT
    emission contract (the original gate path; unchanged behaviour).
    """
    return validate_against_schema(
        source, corpus=corpus, schema_path=PRIORITIZE_EMISSION_SCHEMA_PATH
    )
