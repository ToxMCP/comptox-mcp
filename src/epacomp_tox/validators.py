from __future__ import annotations

from typing import Any, Dict, List, Union

try:
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover - optional dependency at runtime
    pd = None  # type: ignore


def to_serializable(obj: Any) -> Any:
    """Normalize common return types (e.g., pandas DataFrame) to JSON-serializable values."""
    if pd is not None and isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient="records")
    if pd is not None and isinstance(obj, pd.Series):
        return obj.to_dict()
    if hasattr(obj, "to_dict"):
        try:
            return obj.to_dict()
        except Exception:
            pass
    return obj


def ensure_object(value: Any, *, allow_list: bool = False) -> Dict[str, Any]:
    """Ensure the value is an object-like mapping; raise if not acceptable."""
    if isinstance(value, dict):
        return value
    if allow_list and isinstance(value, list):
        # Wrap list responses to a consistent object shape
        return {"items": value}
    raise TypeError("Expected object-like response")


def ensure_list(value: Any) -> List[Any]:
    """Ensure the value is a list; wrap singletons into a list when reasonable."""
    if isinstance(value, list):
        return value
    return [value]
