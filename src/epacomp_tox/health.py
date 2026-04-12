"""Connectivity helpers for the CTX API."""

from __future__ import annotations

import os
import urllib.error
import urllib.request
from typing import Dict, Literal, Optional, Tuple

from .config import get_api_key, get_base_url

# Health endpoints to probe in order. We fall back to the base URL if all
# explicit probes fail, since some CTX deployments do not expose a health path.
_PROBE_SUFFIXES: Tuple[str, ...] = ("health", "status", "")
_READINESS_PROBE_PATHS: Tuple[str, ...] = (
    "chemical/detail/search/by-dtxsid/DTXSID7020182",
    "hazard/toxval/search/by-dtxsid/DTXSID7020182",
    "bioactivity/assay/count",
)
ProbeMode = Literal["readiness", "reachability"]


def _resolve_api_key(
    api_key: Optional[str],
    *,
    require_api_key: bool,
    probe_mode: ProbeMode,
) -> Optional[str]:
    if api_key:
        return api_key
    try:
        return get_api_key()
    except ValueError as exc:
        if require_api_key:
            raise RuntimeError(
                f"CTX {probe_mode} probe requires CTX_API_KEY or EPA_COMPTOX_API_KEY"
            ) from exc
    return None


def _build_headers(api_key: Optional[str]) -> Dict[str, str]:
    headers = {"User-Agent": "epacomp-tox-mcp-health/1.0"}
    if api_key:
        headers["x-api-key"] = api_key
        headers["ctx_x_api_key"] = api_key
    return headers


def _iter_probe_urls(base_url: str, probe_mode: ProbeMode) -> Tuple[str, ...]:
    if probe_mode == "readiness":
        absolute = [
            os.environ.get("CTX_CHEMICAL_HEALTH_URL"),
            os.environ.get("CTX_HAZARD_HEALTH_URL"),
            os.environ.get("CTX_BIOACTIVITY_HEALTH_URL"),
        ]
        urls = tuple(
            url
            for url in absolute
            if url
        )
        if urls:
            return urls
        return tuple(f"{base_url}/{path}" for path in _READINESS_PROBE_PATHS)
    return tuple(
        base_url if not suffix else f"{base_url}/{suffix}" for suffix in _PROBE_SUFFIXES
    )


def check_ctx_health(
    *,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: float = 5.0,
    probe_mode: ProbeMode = "readiness",
) -> Dict[str, object]:
    """Perform a lightweight connectivity check against the CTX API.

    ``readiness`` mode proves authenticated upstream capability using stable API
    endpoints and only succeeds on a 2xx/3xx response. ``reachability`` mode is
    looser and accepts any non-5xx response from the generic health/status/base
    URL probes, which is useful for diagnostics when a deployment does not
    expose a dedicated health route.

    Args:
        api_key: API key to include via ``x-api-key`` header. Defaults to env-resolution.
        base_url: Base URL to target. Defaults to ``get_base_url()``.
        timeout: Maximum time (seconds) to wait for each probe request.
        probe_mode: ``readiness`` for authenticated capability checks or
            ``reachability`` for coarse network reachability checks.

    Returns:
        Mapping with ``ok`` flag, HTTP status code, and URL that answered.

    Raises:
        RuntimeError: If all probe attempts fail or do not satisfy the selected mode.
    """

    require_api_key = probe_mode == "readiness"
    resolved_api_key = _resolve_api_key(
        api_key,
        require_api_key=require_api_key,
        probe_mode=probe_mode,
    )
    resolved_base_url = (base_url or get_base_url()).rstrip("/")
    headers = _build_headers(resolved_api_key)

    last_error: Optional[Exception] = None

    for url in _iter_probe_urls(resolved_base_url, probe_mode):
        request = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                if 200 <= response.status < 400:
                    return {
                        "ok": True,
                        "status": response.status,
                        "url": url,
                        "probeMode": probe_mode,
                        "authenticated": require_api_key,
                    }
                if probe_mode == "reachability" and response.status < 500:
                    return {
                        "ok": True,
                        "status": response.status,
                        "url": url,
                        "probeMode": probe_mode,
                        "authenticated": False,
                    }
        except urllib.error.HTTPError as exc:
            if probe_mode == "reachability" and exc.code < 500:
                return {
                    "ok": True,
                    "status": exc.code,
                    "url": url,
                    "probeMode": probe_mode,
                    "authenticated": False,
                }
            last_error = exc
            if exc.code in {401, 403}:
                break
        except urllib.error.URLError as exc:
            last_error = exc

    error_detail = str(last_error) if last_error else "no additional details"
    raise RuntimeError(
        f"CTX {probe_mode} probe failed for base '{resolved_base_url}': {error_detail}"
    )
