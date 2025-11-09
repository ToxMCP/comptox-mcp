from __future__ import annotations

from typing import Any, Dict, List


def _is_pandas_dataframe(obj: Any) -> bool:
    module = getattr(obj.__class__, "__module__", "")
    name = getattr(obj.__class__, "__name__", "")
    return module.startswith("pandas") and name == "DataFrame"


def _is_pandas_series(obj: Any) -> bool:
    module = getattr(obj.__class__, "__module__", "")
    name = getattr(obj.__class__, "__name__", "")
    return module.startswith("pandas") and name == "Series"


def to_serializable(obj: Any) -> Any:
    """Normalize common return types (e.g., pandas DataFrame) to JSON-serializable values."""
    if _is_pandas_dataframe(obj):
        return obj.to_dict(orient="records")
    if _is_pandas_series(obj):
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
