from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from epacomp_tox.assets import data_file

DEFAULT_MODEL_CARD_DIR = data_file("metadata", "model_cards")
PACKAGED_LAST_MODIFIED = "1970-01-01T00:00:00+00:00"


@dataclass
class ModelCardFilter:
    model_name: Optional[str] = None
    endpoint_contains: Optional[str] = None
    compliance: Optional[str] = None  # "approved" or "draft"


class ModelCardStore:
    """Simple file-backed store for CompTox model cards."""

    def __init__(self, directory: Optional[Path] = None):
        if directory is None:
            self.directory = DEFAULT_MODEL_CARD_DIR
            self._filesystem_backed = False
        else:
            self.directory = Path(directory)
            self.directory.mkdir(parents=True, exist_ok=True)
            self._filesystem_backed = True

    def list_cards(
        self,
        *,
        filters: Optional[ModelCardFilter] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        entries = list(self._iter_cards())
        filtered = self._apply_filters(entries, filters)
        start = int(cursor) if cursor else 0
        end = start + limit if limit else None
        page = filtered[start:end]
        next_cursor = None
        if end is not None and end < len(filtered):
            next_cursor = str(end)
        return page, next_cursor

    def _iter_cards(self) -> Iterable[Dict[str, Any]]:
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
                raw = path.read_text(encoding="utf-8")
                payload = json.loads(raw)
            except (
                OSError,
                json.JSONDecodeError,
            ):  # pragma: no cover - logged upstream
                continue
            checksum = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            if self._filesystem_backed:
                stat = path.stat()
                last_modified = datetime.fromtimestamp(stat.st_mtime).isoformat()
                path_value = str(path)
            else:
                last_modified = PACKAGED_LAST_MODIFIED
                path_value = (
                    f"package://epacomp_tox.data/metadata/model_cards/{path.name}"
                )
            yield {
                "card": payload,
                "checksum": checksum,
                "path": path_value,
                "lastModified": last_modified,
            }

    @staticmethod
    def _apply_filters(
        entries: Iterable[Dict[str, Any]], filters: Optional[ModelCardFilter]
    ) -> List[Dict[str, Any]]:
        if not filters:
            return list(entries)
        result: List[Dict[str, Any]] = []
        for entry in entries:
            card = entry["card"]
            if filters.model_name:
                model_name = card.get("modelDetails", {}).get("name", "")
                if filters.model_name.lower() not in model_name.lower():
                    continue
            if filters.endpoint_contains:
                endpoint = (
                    card.get("oecdValidationPrinciples", {})
                    .get("definedEndpoint", {})
                    .get("description", "")
                )
                if filters.endpoint_contains.lower() not in endpoint.lower():
                    continue
            if filters.compliance:
                status = _compute_compliance_status(card)
                if status != filters.compliance.lower():
                    continue
            result.append(entry)
        return result


def _compute_compliance_status(card: Dict[str, Any]) -> str:
    review = card.get("provenance", {}).get("reviewStatus", {})
    approved_by = review.get("approvedBy", [])
    if approved_by:
        return "approved"
    return "draft"
