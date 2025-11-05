from __future__ import annotations

import json
from pathlib import Path

from epacomp_tox.metadata.applicability import ApplicabilityDomainStore


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload))


def test_list_definitions(tmp_path: Path) -> None:
    directory = tmp_path / "ad"
    directory.mkdir()
    _write(directory / "a.json", {"model": "A", "version": "1", "criteria": []})
    _write(directory / "b.json", {"model": "B", "version": "1", "criteria": []})

    store = ApplicabilityDomainStore(directory=directory)
    page, next_cursor = store.list_definitions(limit=1)
    assert len(page) == 1
    assert next_cursor == "1"

    page2, next_cursor2 = store.list_definitions(limit=1, cursor=next_cursor)
    assert len(page2) == 1
    assert next_cursor2 is None


def test_get_definition(tmp_path: Path) -> None:
    directory = tmp_path / "ad"
    directory.mkdir()
    _write(directory / "test.json", {"model": "Target", "version": "1", "criteria": []})

    store = ApplicabilityDomainStore(directory=directory)
    entry = store.get_definition("target")
    assert entry
    assert entry["model"] == "Target"
