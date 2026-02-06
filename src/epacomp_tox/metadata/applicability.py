from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

DEFAULT_AD_DIR = Path(Path.cwd(), "metadata", "applicability_domains")


class ApplicabilityDomainStore:
    """File-backed access to applicability domain reference data."""

    def __init__(self, directory: Optional[Path] = None):
        self.directory = Path(directory or DEFAULT_AD_DIR)
        self.directory.mkdir(parents=True, exist_ok=True)

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
        for path in sorted(self.directory.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (
                OSError,
                json.JSONDecodeError,
            ):  # pragma: no cover - logged upstream
                continue
            payload["path"] = str(path)
            yield payload
