from __future__ import annotations

import json
from importlib import resources
from typing import Any, Dict, Iterable, Optional

DATA_PACKAGE = "epacomp_tox.data"


def data_root() -> Any:
    """Return the packaged runtime data root."""
    return resources.files(DATA_PACKAGE)


def data_file(*parts: str) -> Any:
    """Return a Traversable for a packaged runtime data file or directory."""
    current = data_root()
    for part in parts:
        current = current.joinpath(part)
    return current


def read_json(*parts: str) -> Dict[str, Any]:
    """Read JSON from a packaged runtime data file."""
    return json.loads(data_file(*parts).read_text(encoding="utf-8"))


def iter_data_files(
    *parts: str, suffix: Optional[str] = None, recursive: bool = False
) -> Iterable[Any]:
    """Iterate packaged runtime data files in deterministic name order."""
    base = data_file(*parts)
    if not base.is_dir():
        return
    for entry in sorted(base.iterdir(), key=lambda item: item.name):
        if entry.name.startswith("."):
            continue
        if entry.is_dir():
            if recursive:
                yield from iter_data_files(
                    *parts, entry.name, suffix=suffix, recursive=True
                )
            continue
        if suffix is None or entry.name.endswith(suffix):
            yield entry
