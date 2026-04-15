from __future__ import annotations

import json
from pathlib import Path

import pytest

from epacomp_tox import audit
from epacomp_tox.orchestrator.audit import AuditBundleStore


class _CollectingSink:
    def __init__(self):
        self.events: list[dict] = []

    def __call__(self, event: dict) -> None:
        self.events.append(event)


@pytest.fixture(autouse=True)
def _clear_sinks():
    audit.clear_sinks()
    yield
    audit.clear_sinks()


def test_emit_with_sink_enriches_audit_metadata():
    sink = _CollectingSink()
    audit.register_sink(sink)

    audit.emit({"type": "test", "value": 42})

    assert len(sink.events) == 1
    event = sink.events[0]
    assert event["type"] == "test"
    assert event["value"] == 42
    assert "_audit" in event
    assert "contentHash" in event["_audit"]
    assert "previousHash" in event["_audit"]
    assert "timestamp" in event["_audit"]
    assert event["_audit"]["sequence"] == 1


def test_verify_event_hash_returns_true_for_valid_event():
    sink = _CollectingSink()
    audit.register_sink(sink)

    audit.emit({"type": "test", "value": 42})

    assert audit.verify_event_hash(sink.events[0]) is True


def test_verify_event_hash_returns_false_for_tampered_event():
    sink = _CollectingSink()
    audit.register_sink(sink)

    audit.emit({"type": "test", "value": 42})
    event = sink.events[0]
    event["value"] = 99  # tamper

    assert audit.verify_event_hash(event) is False


def test_verify_event_hash_returns_false_for_missing_audit_meta():
    assert audit.verify_event_hash({"type": "test"}) is False


def test_chain_linkage_previous_hash_matches_prior_content_hash():
    sink = _CollectingSink()
    audit.register_sink(sink)

    audit.emit({"type": "first"})
    audit.emit({"type": "second"})

    first_hash = sink.events[0]["_audit"]["contentHash"]
    second_previous = sink.events[1]["_audit"]["previousHash"]
    assert second_previous == first_hash


def test_clear_sinks_resets_chain():
    sink = _CollectingSink()
    audit.register_sink(sink)

    audit.emit({"type": "first"})
    first_hash = sink.events[0]["_audit"]["contentHash"]

    audit.clear_sinks()
    sink2 = _CollectingSink()
    audit.register_sink(sink2)

    audit.emit({"type": "second"})
    # After reset, previousHash should be zeros, not first_hash
    assert sink2.events[0]["_audit"]["previousHash"] == "0" * 64


def test_bundle_store_includes_chain_hashes(tmp_path: Path):
    store = AuditBundleStore(tmp_path)
    meta1 = store.save({"workflowRunId": "run-1", "data": "a"})
    meta2 = store.save({"workflowRunId": "run-2", "data": "b"})

    assert meta1["previousBundleHash"] == "0" * 64
    assert meta2["previousBundleHash"] == meta1["bundleChecksum"]

    # Chain manifest should reflect latest
    manifest = json.loads((tmp_path / "chain_manifest.json").read_text(encoding="utf-8"))
    assert manifest["lastBundleHash"] == meta2["bundleChecksum"]


def test_bundle_store_verify_chain_detects_tampering(tmp_path: Path):
    store = AuditBundleStore(tmp_path)
    store.save({"workflowRunId": "run-1", "data": "a"})
    store.save({"workflowRunId": "run-2", "data": "b"})

    valid, errors = store.verify_chain()
    assert valid is True
    assert errors == []

    # Tamper with a bundle file
    bundle_path = tmp_path / "run-1" / "bundle.json"
    bundle_path.write_text(json.dumps({"workflowRunId": "run-1", "data": "tampered"}), encoding="utf-8")

    valid, errors = store.verify_chain()
    assert valid is False
    assert any("checksum mismatch" in e for e in errors)
    assert any("run-1" in e for e in errors)


def test_bundle_store_verify_chain_detects_missing_file(tmp_path: Path):
    store = AuditBundleStore(tmp_path)
    store.save({"workflowRunId": "run-1", "data": "a"})

    # Delete bundle file
    (tmp_path / "run-1" / "bundle.json").unlink()

    valid, errors = store.verify_chain()
    assert valid is False
    assert any("bundle file missing" in e for e in errors)
