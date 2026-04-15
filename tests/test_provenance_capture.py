from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest

from epacomp_tox.resources.base import BaseResource


class _DummyClient:
    def __init__(self, result):
        self._result = result
        self.last_metadata = {"status": 200, "request_id": "req-123"}

    def action(self):
        return self._result


class _TestResource(BaseResource):
    @property
    def name(self) -> str:
        return "test"

    @property
    def description(self) -> str:
        return "Test resource"

    def get_tools(self) -> List[Dict[str, Any]]:
        return []

    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        raise NotImplementedError

    def call_with_result(self, result):
        self.client = _DummyClient(result)
        return self._with_retry(lambda: self.client.action())

    def call_that_fails_then_succeeds(self, fail_times: int = 1):
        self.client = _DummyClient({"ok": True})
        attempts = [0]

        def _fn():
            attempts[0] += 1
            if attempts[0] <= fail_times:
                raise RuntimeError("transient")
            return {"ok": True}

        return self._with_retry(_fn)


def test_successful_call_captures_retrieved_at_and_response_hash():
    resource = _TestResource("api-key")
    result = resource.call_with_result({"data": "value"})

    assert result == {"data": "value"}
    # Backward compatibility: raw metadata is unchanged
    assert resource.get_last_metadata() == {"status": 200, "request_id": "req-123"}

    prov = resource.get_last_provenance()
    assert "retrieved_at" in prov
    assert "response_hash" in prov
    assert prov["retry_count"] == 0

    # Verify retrieved_at is a valid ISO timestamp
    dt = datetime.fromisoformat(prov["retrieved_at"].replace("Z", "+00:00"))
    assert dt.tzinfo == timezone.utc

    # Verify response_hash is a 64-char hex string
    assert len(prov["response_hash"]) == 64


def test_response_hash_is_deterministic_for_same_result():
    resource = _TestResource("api-key")
    resource.call_with_result({"data": "value"})
    hash1 = resource.get_last_provenance()["response_hash"]

    resource.call_with_result({"data": "value"})
    hash2 = resource.get_last_provenance()["response_hash"]

    assert hash1 == hash2


def test_response_hash_differs_for_different_results():
    resource = _TestResource("api-key")
    resource.call_with_result({"data": "value1"})
    hash1 = resource.get_last_provenance()["response_hash"]

    resource.call_with_result({"data": "value2"})
    hash2 = resource.get_last_provenance()["response_hash"]

    assert hash1 != hash2


def test_retry_count_is_zero_on_immediate_success():
    resource = _TestResource("api-key")
    resource.call_with_result({"ok": True})
    assert resource.get_last_provenance()["retry_count"] == 0


def test_retry_count_reflects_number_of_retries():
    resource = _TestResource("api-key")
    resource.call_that_fails_then_succeeds(fail_times=2)
    assert resource.get_last_provenance()["retry_count"] == 2
