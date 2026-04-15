"""Lightweight audit event emitter with optional tamper-evident chain hashing."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Callable, Dict, List

logger = logging.getLogger(__name__)

AuditEvent = Dict[str, object]
AuditSink = Callable[[AuditEvent], None]

_sinks: List[AuditSink] = []
_previous_hash: str = "0" * 64
_sequence: int = 0


def register_sink(sink: AuditSink) -> None:
    """Register a callable that will receive audit events."""

    if sink not in _sinks:
        _sinks.append(sink)


def clear_sinks() -> None:
    """Remove all registered sinks (primarily for tests)."""

    _sinks.clear()
    _reset_chain()


def _reset_chain() -> None:
    global _previous_hash, _sequence
    _previous_hash = "0" * 64
    _sequence = 0


def _compute_content_hash(event: AuditEvent) -> str:
    """Compute SHA-256 hash of the canonical JSON representation."""
    payload = json.dumps(event, ensure_ascii=True, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _enrich_event(event: AuditEvent) -> AuditEvent:
    """Add tamper-evident audit metadata to an event."""
    global _previous_hash, _sequence
    content_hash = _compute_content_hash(event)
    _sequence += 1
    enriched = dict(event)
    enriched["_audit"] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sequence": _sequence,
        "contentHash": content_hash,
        "previousHash": _previous_hash,
    }
    _previous_hash = content_hash
    return enriched


def verify_event_hash(event: AuditEvent) -> bool:
    """Verify that an event's content hash matches its payload.

    Returns False if the event lacks audit metadata or if the recomputed
    hash does not match the stored hash.
    """
    audit_meta = event.get("_audit")
    if not isinstance(audit_meta, dict):
        return False
    stored_hash = audit_meta.get("contentHash")
    if not isinstance(stored_hash, str):
        return False
    # Compute hash from the original event without _audit metadata
    original = {k: v for k, v in event.items() if k != "_audit"}
    return _compute_content_hash(original) == stored_hash


def emit(event: AuditEvent) -> None:
    """Emit an audit event to registered sinks or log when none exist."""

    if not _sinks:
        logger.info("AUDIT_EVENT", extra={"event": event})
        return

    enriched = _enrich_event(event)

    for sink in list(_sinks):
        try:
            sink(enriched)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Audit sink %s failed: %s", sink, exc)
