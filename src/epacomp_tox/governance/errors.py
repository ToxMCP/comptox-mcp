"""Blocking-failure model + meta fail-closed codes for the Track-B gate.

A ``BlockingFinding`` is the uniform shape the gate aggregates and that turns the
exit code non-zero. Two families of codes flow through it:

* SCIENTIFIC codes emitted by the vendored spine policy engine itself. For
  comptox-mcp the gated object is the server-authored ``prioritize_risk_signals``
  margin-of-exposure conclusion, projected onto a
  ``BioactivityExposureRatioRecord.v1``; the producer-reachable codes are
  ``BER_NOT_RISK_OR_REGULATORY`` (the conclusion authorized a risk/regulatory
  downstream use) and ``BER_UNCERTAINTY_AND_CEILING_REQUIRED`` (the conclusion
  dropped its uncertainty / screening-ceiling disclosure). These are passed
  through verbatim from the engine's ``failures[]``.

* META fail-closed codes synthesized by the *bridge* when it cannot trust the
  engine's verdict (engine missing/crashed/timed out, unrecognized schemaId,
  vendored-file tamper), by the *projection* when it cannot faithfully map a
  source object, or by the *source-contract guard* when a raw source packet
  violates the producer's strict emission contract. Every one of these BLOCKS —
  none is ever downgraded to a pass.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# --- META fail-closed codes (synthesized, never from the engine) -------------

#: Node missing / non-zero exit / empty or unparseable stdout / timeout.
ENGINE_UNAVAILABLE = "ENGINE_UNAVAILABLE"

#: The projected object's schemaId is not in the engine's recognized set, so a
#: ``valid:true`` from the engine would be a silent no-op. Treated as blocking.
UNRECOGNIZED_SPINE_SCHEMA_ID = "UNRECOGNIZED_SPINE_SCHEMA_ID"

#: A vendored engine file's sha256 does not match VENDORED_FROM.json (tamper).
VENDOR_DIGEST_MISMATCH = "VENDOR_DIGEST_MISMATCH"

#: The projection could not faithfully map a required field / unmapped enum.
PROJECTION_INCOMPLETE = "PROJECTION_INCOMPLETE"

#: The raw source packet failed the producer's STRICT emission contract (the
#: additionalProperties:false JSON schema mirroring the prioritize_risk_signals
#: response builder's real emitted shape). BLOCKS at the TOP of the gate, BEFORE
#: any projection, so a packet carrying an undeclared / schema-forbidden field is
#: never projected. This is the guard that closes the producer-emission-contract
#: dead-arm class (a code that bites only on a schema-INVALID fixture, never on a
#: real producer-emitted packet). The constant lives here, not in
#: source_contract.py, to avoid an import cycle; source_contract.py re-exports it.
SOURCE_CONTRACT_VIOLATION = "SOURCE_CONTRACT_VIOLATION"

#: Every meta code, for gate aggregation / documentation.
META_FAIL_CLOSED_CODES: frozenset[str] = frozenset(
    {
        ENGINE_UNAVAILABLE,
        UNRECOGNIZED_SPINE_SCHEMA_ID,
        VENDOR_DIGEST_MISMATCH,
        PROJECTION_INCOMPLETE,
        SOURCE_CONTRACT_VIOLATION,
    }
)


@dataclass(frozen=True)
class BlockingFinding:
    """One release-blocking finding (scientific or meta fail-closed)."""

    code: str
    message: str
    path: str = "$"
    #: "scientific" (from the engine) or "meta" (synthesized fail-closed).
    origin: str = "scientific"
    #: Free-form context (the source object id, the projected schemaId, etc.).
    context: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "path": self.path,
            "origin": self.origin,
            "context": dict(self.context),
        }

    @classmethod
    def meta(cls, code: str, message: str, **context: Any) -> "BlockingFinding":
        return cls(code=code, message=message, origin="meta", context=context)


class ProjectionIncompleteError(Exception):
    """Raised by the projection when a source object cannot be faithfully mapped.

    The gate catches this and records a ``PROJECTION_INCOMPLETE`` blocking
    finding — a missing required field or unmapped enum is NEVER silently
    defaulted to a safe branch.
    """

    def __init__(self, message: str, *, path: str = "$") -> None:
        super().__init__(message)
        self.message = message
        self.path = path
