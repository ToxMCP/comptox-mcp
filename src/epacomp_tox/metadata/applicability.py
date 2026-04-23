from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from epacomp_tox.assets import data_file

DEFAULT_AD_DIR = data_file("metadata", "applicability_domains")


class ApplicabilityDomainStore:
    """File-backed access to applicability domain reference data."""

    def __init__(self, directory: Optional[Path] = None):
        if directory is None:
            self.directory = DEFAULT_AD_DIR
            self._filesystem_backed = False
        else:
            self.directory = Path(directory)
            self.directory.mkdir(parents=True, exist_ok=True)
            self._filesystem_backed = True

    def list_definitions(
        self,
        *,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        entries = list(self._iter_defs())
        start = int(cursor) if cursor else 0
        end = start + limit if limit else None
        page = entries[start:end]
        next_cursor = None
        if end is not None and end < len(entries):
            next_cursor = str(end)
        return page, next_cursor

    def get_definition(self, model_name: str) -> Optional[Dict[str, Any]]:
        model_name_lower = model_name.lower()
        for entry in self._iter_defs():
            if entry["model"].lower() == model_name_lower:
                return entry
        return None

    def _iter_defs(self) -> Iterable[Dict[str, Any]]:
        paths = (
            sorted(self.directory.glob("*.json"))
            if self._filesystem_backed
            else sorted(
                (
                    entry
                    for entry in self.directory.iterdir()
                    if entry.is_file() and entry.name.endswith(".json")
                ),
                key=lambda entry: entry.name,
            )
        )
        for path in paths:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (
                OSError,
                json.JSONDecodeError,
            ):  # pragma: no cover - logged upstream
                continue
            if self._filesystem_backed:
                payload["path"] = str(path)
            else:
                payload["path"] = (
                    "package://epacomp_tox.data/metadata/"
                    f"applicability_domains/{path.name}"
                )
            yield payload
