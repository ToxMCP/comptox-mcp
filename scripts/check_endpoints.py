#!/usr/bin/env python3
"""Endpoint smoke checker for EPA CompTox MCP dependencies."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class Endpoint:
    name: str
    url: str
    needs_api_key: bool = True
    description: Optional[str] = None


DEFAULT_ENDPOINTS: List[Endpoint] = [
    Endpoint(
        name="CTX Chemical API",
        url=os.environ.get(
            "CTX_CHEMICAL_HEALTH_URL",
            "https://comptox.epa.gov/ctx-api/chemical/detail/search/by-dtxsid/DTXSID7020182",
        ),
        description="Identifier resolution, structures, property lookups",
    ),
    Endpoint(
        name="CTX Hazard API",
        url=os.environ.get(
            "CTX_HAZARD_HEALTH_URL",
            "https://comptox.epa.gov/ctx-api/hazard/toxval/search/by-dtxsid/DTXSID7020182",
        ),
        description="ToxValDB, ToxRefDB, cancer, genetox, ADME/IVIVE, IRIS, PPRTV, HAWC",
    ),
    Endpoint(
        name="CTX Exposure API",
        url=os.environ.get(
            "CTX_EXPOSURE_HEALTH_URL",
            "https://comptox.epa.gov/ctx-api/exposure/product-data/puc",
        ),
        description="CPDat, SEEM, MMDB, HTTK",
    ),
    Endpoint(
        name="CTX Bioactivity API",
        url=os.environ.get(
            "CTX_BIOACTIVITY_HEALTH_URL",
            "https://comptox.epa.gov/ctx-api/bioactivity/assay/count",
        ),
        description="ToxCast/Tox21 assays, AOP mappings",
    ),
]


def _build_request(
    endpoint: Endpoint, api_key: Optional[str]
) -> urllib.request.Request:
    req = urllib.request.Request(endpoint.url)
    if endpoint.needs_api_key and api_key:
        req.add_header("x-api-key", api_key)
        req.add_header("ctx_x_api_key", api_key)
    req.add_header("User-Agent", "epacomp-tox-mcp-endpoint-check/1.0")
    return req


def check_endpoint(
    endpoint: Endpoint, *, api_key: Optional[str], timeout: float
) -> Dict[str, object]:
    req = _build_request(endpoint, api_key)
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency = time.time() - started
            status = resp.getcode()
            return {
                "name": endpoint.name,
                "url": endpoint.url,
                "status": status,
                "latency_ms": round(latency * 1000, 2),
                "ok": 200 <= status < 400,
                "error": None,
            }
    except urllib.error.HTTPError as exc:
        latency = time.time() - started
        return {
            "name": endpoint.name,
            "url": endpoint.url,
            "status": exc.code,
            "latency_ms": round(latency * 1000, 2),
            "ok": False,
            "error": exc.reason,
        }
    except urllib.error.URLError as exc:
        latency = time.time() - started
        return {
            "name": endpoint.name,
            "url": endpoint.url,
            "status": None,
            "latency_ms": round(latency * 1000, 2),
            "ok": False,
            "error": getattr(exc, "reason", str(exc)),
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check availability of upstream CompTox endpoints."
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.environ.get("ENDPOINT_CHECK_TIMEOUT", 5)),
        help="Per-endpoint timeout in seconds (default: 5)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of a human summary.",
    )
    parser.add_argument(
        "--no-api-key",
        action="store_true",
        help="Skip sending the API key header (useful for transports that do not require auth).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    api_key = (
        None
        if args.no_api_key
        else os.environ.get("CTX_API_KEY") or os.environ.get("EPA_COMPTOX_API_KEY")
    )

    results = [
        check_endpoint(ep, api_key=api_key, timeout=args.timeout)
        for ep in DEFAULT_ENDPOINTS
    ]
    failed = [item for item in results if not item["ok"]]

    if args.json:
        json.dump({"results": results}, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        for item in results:
            status = item["status"] if item["status"] is not None else "N/A"
            marker = "✅" if item["ok"] else "❌"
            line = f"{marker} {item['name']}: status={status} latency={item['latency_ms']}ms ({item['url']})"
            if item["error"]:
                line += f" - {item['error']}"
            print(line)

        if not api_key and not args.no_api_key:
            print(
                "⚠️  No API key detected in CTX_API_KEY/EPA_COMPTOX_API_KEY; endpoints may reject requests."
            )

    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
