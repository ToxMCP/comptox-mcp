"""Connectivity helpers for the CTX API."""

from __future__ import annotations

import urllib.error
import urllib.request
from typing import Dict, Optional, Tuple

from .config import get_api_key, get_base_url

# Health endpoints to probe in order. We fall back to the base URL if all
# explicit probes fail, since some CTX deployments do not expose a health path.
_PROBE_SUFFIXES: Tuple[str, ...] = ("health", "status", "")


def check_ctx_health(
    *,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: float = 5.0,
) -> Dict[str, object]:
    """Perform a lightweight connectivity check against the CTX API.

    The check succeeds if we obtain any non-5xx HTTP response from one of the
    probe endpoints. This intentionally treats 4xx codes (e.g. 404) as success
    because some CTX deployments return 404 for unknown routes while still
    confirming reachability.

    Args:
        api_key: API key to include via ``x-api-key`` header. Defaults to env-resolution.
        base_url: Base URL to target. Defaults to ``get_base_url()``.
        timeout: Maximum time (seconds) to wait for each probe request.

    Returns:
        Mapping with ``ok`` flag, HTTP status code, and URL that answered.

    Raises:
        RuntimeError: If all probe attempts fail or return 5xx errors.
    """

    resolved_api_key = api_key or get_api_key()
    resolved_base_url = (base_url or get_base_url()).rstrip("/")
    headers = {"x-api-key": resolved_api_key} if resolved_api_key else {}

    last_error: Optional[Exception] = None

    for suffix in _PROBE_SUFFIXES:
        url = resolved_base_url if not suffix else f"{resolved_base_url}/{suffix}"
        request = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                # Treat any non-5xx response as healthy; see docstring rationale.
                if response.status < 500:
                    return {"ok": True, "status": response.status, "url": url}
        except urllib.error.HTTPError as exc:
            if exc.code < 500:
                return {"ok": True, "status": exc.code, "url": url}
            last_error = exc
        except urllib.error.URLError as exc:
            last_error = exc

    error_detail = str(last_error) if last_error else "no additional details"
    raise RuntimeError(
        f"CTX health check failed for base '{resolved_base_url}': {error_detail}"
    )

