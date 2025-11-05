from __future__ import annotations

from typing import Any, Dict, Optional


def sanitize_metadata(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Convert transport/resource metadata into JSON-serializable primitives.

    ctxpy returns dataclass instances (e.g., RateLimitInfo) inside the metadata
    payload. Downstream audit bundles expect plain dictionaries, so this helper
    normalizes nested structures while preserving the original keys.
    """

    def _convert(value: Any) -> Any:
        if hasattr(value, "__dataclass_fields__"):
            return {
                field: getattr(value, field)
                for field in value.__dataclass_fields__.keys()  # type: ignore[attr-defined]
            }
        if isinstance(value, dict):
            return {key: _convert(val) for key, val in value.items()}
        if isinstance(value, (list, tuple)):
            return [_convert(item) for item in value]
        return value

    if not metadata:
        return {}
    return {key: _convert(val) for key, val in metadata.items()}
