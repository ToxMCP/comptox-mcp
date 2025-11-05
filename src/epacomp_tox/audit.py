"""Lightweight audit event emitter."""

from __future__ import annotations

import logging
from typing import Callable, Dict, List

logger = logging.getLogger(__name__)

AuditEvent = Dict[str, object]
AuditSink = Callable[[AuditEvent], None]

_sinks: List[AuditSink] = []


def register_sink(sink: AuditSink) -> None:
    """Register a callable that will receive audit events."""

    if sink not in _sinks:
        _sinks.append(sink)


def clear_sinks() -> None:
    """Remove all registered sinks (primarily for tests)."""

    _sinks.clear()


def emit(event: AuditEvent) -> None:
    """Emit an audit event to registered sinks or log when none exist."""

    if not _sinks:
        logger.info("AUDIT_EVENT", extra={"event": event})
        return

    for sink in list(_sinks):
        try:
            sink(event)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Audit sink %s failed: %s", sink, exc)
