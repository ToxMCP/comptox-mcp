from __future__ import annotations

from epacomp_tox.server import MCPServer


def test_scrub_params_hashes_dtxsid():
    scrubbed = MCPServer._scrub_params_for_audit({"dtxsid": "DTXSID0000001"})
    assert scrubbed["dtxsid"].startswith("[HASH:")
    assert "DTXSID" not in scrubbed["dtxsid"]


def test_scrub_params_hashes_casrn():
    scrubbed = MCPServer._scrub_params_for_audit({"casrn": "50-00-0"})
    assert scrubbed["casrn"].startswith("[HASH:")


def test_scrub_params_hashes_smiles():
    scrubbed = MCPServer._scrub_params_for_audit({"smiles": "CCO"})
    assert scrubbed["smiles"].startswith("[HASH:")


def test_scrub_params_hashes_query_that_looks_like_casrn():
    scrubbed = MCPServer._scrub_params_for_audit({"query": "50-00-0"})
    assert scrubbed["query"].startswith("[HASH:")


def test_scrub_params_hashes_query_that_looks_like_smiles():
    scrubbed = MCPServer._scrub_params_for_audit({"query": "CCO"})
    assert scrubbed["query"].startswith("[HASH:")


def test_scrub_params_leaves_plaintext_query_alone():
    scrubbed = MCPServer._scrub_params_for_audit({"query": "water"})
    assert scrubbed["query"] == "water"


def test_scrub_params_is_deterministic():
    scrubbed1 = MCPServer._scrub_params_for_audit({"dtxsid": "DTXSID0000001"})
    scrubbed2 = MCPServer._scrub_params_for_audit({"dtxsid": "DTXSID0000001"})
    assert scrubbed1["dtxsid"] == scrubbed2["dtxsid"]


def test_scrub_params_hashes_nested_identifiers():
    scrubbed = MCPServer._scrub_params_for_audit(
        {
            "identifiers": ["DTXSID0000001", "DTXSID0000002"],
            "nested": {"casrn": "50-00-0"},
        }
    )
    assert all(s.startswith("[HASH:") for s in scrubbed["identifiers"])
    assert scrubbed["nested"]["casrn"].startswith("[HASH:")
