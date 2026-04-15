from __future__ import annotations

from unittest import mock

import pytest

from epacomp_tox import audit
from epacomp_tox.server import MCPServer
from epacomp_tox.transport.http import _build_request_context


class _FakeRequest:
    def __init__(self, headers=None, state=None):
        self.headers = headers or {}
        self.state = state or mock.Mock()


def test_request_context_generates_trace_id():
    request = _FakeRequest()
    ctx = _build_request_context(request)
    assert "traceId" in ctx
    assert len(ctx["traceId"]) == 36  # UUID4 length


def test_request_context_extracts_traceparent():
    request = _FakeRequest(
        headers={
            "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        }
    )
    ctx = _build_request_context(request)
    assert ctx["traceId"] == "4bf92f3577b34da6a3ce929d0e0e4736"


def test_emit_audit_event_includes_trace_id():
    """Directly exercise _emit_audit_event to ensure trace_id is propagated."""
    events = []
    audit.register_sink(events.append)
    try:
        server = MCPServer(api_key="fake")
        server._emit_audit_event(
            tool_name="test_tool",
            status="success",
            duration_ms=12.5,
            correlation_id="corr-1",
            session_id="sess-1",
            client_info={"name": "test"},
            trace_id="trace-abc-123",
            resource_name="test",
            params={"query": "water"},
        )
    finally:
        audit.clear_sinks()

    assert len(events) == 1
    assert events[0]["trace_id"] == "trace-abc-123"
    assert events[0]["correlation_id"] == "corr-1"
    assert audit.verify_event_hash(events[0]) is True
