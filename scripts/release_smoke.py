#!/usr/bin/env python3
"""Release-oriented live smoke runner for the public CompTox MCP surface."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse, urlunparse

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


class ReleaseSmokeError(RuntimeError):
    """Raised when the release-oriented smoke encounters a validation failure."""


@dataclass
class SmokeSummary:
    endpoint: str
    server_version: str
    healthz: Dict[str, Any]
    readyz: Dict[str, Any]
    manifest: Dict[str, Any]
    resolve_exact: Dict[str, Any]
    resolve_ambiguous: Dict[str, Any]
    resolve_not_found: Dict[str, Any]
    prioritization: Dict[str, Any]
    interop: Dict[str, Any]
    websocket: Dict[str, Any]


def _payload_dtxsid(payload: Dict[str, Any]) -> Optional[str]:
    for key in ("chemicalIdentity", "chemicalRef", "chemicalIdentityRef"):
        value = payload.get(key)
        if isinstance(value, dict):
            dtxsid = value.get("dtxsid")
            if isinstance(dtxsid, str):
                return dtxsid
    return None


def _derive_url(endpoint: str, suffix: str) -> str:
    parsed = urlparse(endpoint)
    path = parsed.path.rstrip("/")
    if path.endswith("/mcp"):
        path = path[: -len("/mcp")] + suffix
    else:
        path = path + suffix
    return urlunparse(parsed._replace(path=path))


def _http_json(url: str, *, timeout: float = 15.0) -> Dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return {
                "status_code": response.status,
                "body": json.loads(response.read().decode("utf-8")),
            }
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ReleaseSmokeError(f"{url} returned HTTP {exc.code}: {detail}") from exc


def _rpc(
    endpoint: str, method: str, params: Dict[str, Any], *, request_id: int
) -> Dict[str, Any]:
    payload = json.dumps(
        {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
    ).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=payload,
        headers={"content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            decoded = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ReleaseSmokeError(
            f"MCP method {method!r} returned HTTP {exc.code}: {detail}"
        ) from exc

    if "error" in decoded:
        raise ReleaseSmokeError(
            f"MCP method {method!r} returned JSON-RPC error: {json.dumps(decoded['error'])}"
        )
    return decoded["result"]


async def _websocket_smoke(
    ws_url: str, *, require_version: Optional[str] = None
) -> Dict[str, Any]:
    import websockets

    async with websockets.connect(ws_url, open_timeout=15) as websocket:
        await websocket.send(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {
                            "name": "release-smoke",
                            "version": "1.0.0",
                        },
                    },
                }
            )
        )
        initialize = json.loads(await websocket.recv())
        server_version = initialize["result"]["serverInfo"].get("version")
        if require_version and server_version != require_version:
            raise ReleaseSmokeError(
                "WebSocket initialize reported an unexpected server version: "
                f"expected {require_version!r}, got {server_version!r}."
            )

        initialized_notification_seen = False
        try:
            maybe_notification = await asyncio.wait_for(websocket.recv(), timeout=0.2)
            notification = json.loads(maybe_notification)
            initialized_notification_seen = (
                notification.get("method") == "notifications/initialized"
            )
        except asyncio.TimeoutError:
            pass

        await websocket.send(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "resolve_chemical_identifier",
                        "arguments": {"identifier": "50-00-0"},
                    },
                }
            )
        )

        tool_response: Optional[Dict[str, Any]] = None
        while tool_response is None:
            message = json.loads(await websocket.recv())
            if message.get("id") == 2:
                tool_response = message

        structured = tool_response["result"]["structuredContent"]
        if structured.get("status") != "resolved":
            raise ReleaseSmokeError(
                "WebSocket resolve_chemical_identifier did not resolve the exact CAS smoke probe."
            )

        return {
            "serverInfo": initialize["result"]["serverInfo"],
            "initializedNotificationSeen": initialized_notification_seen,
            "resolvedStatus": structured.get("status"),
            "resolvedDtxsid": structured.get("canonicalDtxsid"),
        }


def run_release_smoke(
    endpoint: str, *, require_version: Optional[str] = None
) -> SmokeSummary:
    healthz = _http_json(_derive_url(endpoint, "/healthz"))
    if healthz["status_code"] != 200 or healthz["body"].get("status") != "ok":
        raise ReleaseSmokeError(f"Unexpected /healthz payload: {healthz}")

    readyz = _http_json(_derive_url(endpoint, "/readyz"))
    ready_body = readyz["body"]
    if readyz["status_code"] != 200 or ready_body.get("status") != "ok":
        raise ReleaseSmokeError(f"Unexpected /readyz payload: {readyz}")
    ctx_payload = ready_body.get("ctx", {})
    if not ctx_payload.get("ok") or ctx_payload.get("probeMode") != "readiness":
        raise ReleaseSmokeError(f"/readyz did not return a readiness probe: {readyz}")

    initialize = _rpc(
        endpoint,
        "initialize",
        {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "release-smoke", "version": "1.0.0"},
        },
        request_id=1,
    )
    server_version = initialize["serverInfo"].get("version")
    if require_version and server_version != require_version:
        raise ReleaseSmokeError(
            "HTTP initialize reported an unexpected server version: "
            f"expected {require_version!r}, got {server_version!r}."
        )
    tools = _rpc(endpoint, "tools/list", {}, request_id=2)
    resources = _rpc(endpoint, "resources/list", {}, request_id=3)

    tool_count = len(tools.get("tools", []))
    resource_count = len(resources.get("resources", []))
    if tool_count < 10 or resource_count < 5:
        raise ReleaseSmokeError(
            f"Unexpectedly small MCP catalog: tools={tool_count}, resources={resource_count}"
        )

    manifest = _rpc(
        endpoint,
        "tools/call",
        {"name": "get_contract_manifest", "arguments": {}},
        request_id=4,
    )["structuredContent"]
    if manifest["server"]["toolCount"] != tool_count:
        raise ReleaseSmokeError("Manifest tool count does not match tools/list output.")

    resolve_exact = _rpc(
        endpoint,
        "tools/call",
        {"name": "resolve_chemical_identifier", "arguments": {"identifier": "50-00-0"}},
        request_id=5,
    )["structuredContent"]
    if (
        resolve_exact.get("status") != "resolved"
        or resolve_exact.get("searchModeUsed") != "equals"
    ):
        raise ReleaseSmokeError(f"Exact resolution smoke failed: {resolve_exact}")

    resolve_ambiguous = _rpc(
        endpoint,
        "tools/call",
        {
            "name": "resolve_chemical_identifier",
            "arguments": {
                "identifier": "bisphenol",
                "identifier_type": "name",
                "allow_fallback": True,
                "max_candidates": 3,
            },
        },
        request_id=6,
    )["structuredContent"]
    if resolve_ambiguous.get("status") != "ambiguous":
        raise ReleaseSmokeError(
            f"Partial-name ambiguity smoke failed: {resolve_ambiguous}"
        )

    resolve_not_found = _rpc(
        endpoint,
        "tools/call",
        {
            "name": "resolve_chemical_identifier",
            "arguments": {
                "identifier": "notarealchem123",
                "identifier_type": "name",
                "allow_fallback": True,
                "max_candidates": 3,
            },
        },
        request_id=7,
    )["structuredContent"]
    if resolve_not_found.get("status") != "not_found":
        raise ReleaseSmokeError(f"Not-found smoke failed: {resolve_not_found}")

    prioritization = _rpc(
        endpoint,
        "tools/call",
        {
            "name": "prioritize_risk_signals",
            "arguments": {"dtxsid": "DTXSID7020182"},
        },
        request_id=8,
    )["structuredContent"]
    if prioritization.get("chemicalRef", {}).get("dtxsid") != "DTXSID7020182":
        raise ReleaseSmokeError(f"Prioritization smoke failed: {prioritization}")

    evidence_pack = _rpc(
        endpoint,
        "tools/call",
        {
            "name": "assemble_comptox_evidence_pack",
            "arguments": {"dtxsid": "DTXSID2020006", "max_assays": 5},
        },
        request_id=9,
    )["structuredContent"]
    aop_summary = _rpc(
        endpoint,
        "tools/call",
        {
            "name": "build_aop_linkage_summary",
            "arguments": {"dtxsid": "DTXSID2020006", "max_assays": 5},
        },
        request_id=10,
    )["structuredContent"]
    pbpk_bundle = _rpc(
        endpoint,
        "tools/call",
        {
            "name": "build_pbpk_context_bundle",
            "arguments": {"dtxsid": "DTXSID2020006"},
        },
        request_id=11,
    )["structuredContent"]

    if _payload_dtxsid(evidence_pack) != "DTXSID2020006":
        raise ReleaseSmokeError("Evidence-pack smoke returned the wrong chemical.")
    if (
        "knownDataGaps" not in evidence_pack
        or "generatedFromTools" not in evidence_pack
    ):
        raise ReleaseSmokeError(
            "Evidence-pack smoke is missing additive provenance fields."
        )
    if _payload_dtxsid(aop_summary) != "DTXSID2020006":
        raise ReleaseSmokeError("AOP smoke returned the wrong chemical.")
    if _payload_dtxsid(pbpk_bundle) != "DTXSID2020006":
        raise ReleaseSmokeError("PBPK smoke returned the wrong chemical.")

    websocket_summary = asyncio.run(
        _websocket_smoke(
            _derive_url(endpoint, "/mcp/ws")
            .replace("http://", "ws://")
            .replace("https://", "wss://"),
            require_version=require_version,
        )
    )

    return SmokeSummary(
        endpoint=endpoint,
        server_version=server_version,
        healthz=healthz,
        readyz=readyz,
        manifest={
            "resourceCount": manifest["server"]["resourceCount"],
            "toolCount": manifest["server"]["toolCount"],
            "publicBoundary": manifest["publicBoundary"],
        },
        resolve_exact={
            "status": resolve_exact["status"],
            "canonicalDtxsid": resolve_exact["canonicalDtxsid"],
            "preferredName": resolve_exact["preferredName"],
            "searchModeUsed": resolve_exact["searchModeUsed"],
        },
        resolve_ambiguous={
            "status": resolve_ambiguous["status"],
            "searchModeUsed": resolve_ambiguous["searchModeUsed"],
            "candidateCount": resolve_ambiguous["candidateCount"],
            "warnings": resolve_ambiguous["warnings"],
        },
        resolve_not_found={
            "status": resolve_not_found["status"],
            "warnings": resolve_not_found["warnings"],
        },
        prioritization={
            "chemicalRef": prioritization.get("chemicalRef"),
            "priorityBand": prioritization.get("prioritization", {}).get(
                "priorityBand"
            ),
            "knownDataGaps": prioritization.get("knownDataGaps"),
        },
        interop={
            "evidencePack": {
                "semanticCoverage": evidence_pack.get("semanticCoverage"),
                "knownDataGaps": evidence_pack.get("knownDataGaps"),
                "generatedFromTools": evidence_pack.get("generatedFromTools"),
            },
            "aopLinkageSummary": {
                "knownDataGaps": aop_summary.get("knownDataGaps"),
                "mappingCount": len(aop_summary.get("mappings", [])),
            },
            "pbpkContextBundle": {
                "knownDataGaps": pbpk_bundle.get("knownDataGaps"),
                "parameterCount": len(pbpk_bundle.get("parameters", [])),
            },
        },
        websocket=websocket_summary,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--endpoint",
        default="http://127.0.0.1:8000/mcp",
        help="HTTP MCP endpoint to validate (default: %(default)s)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON",
    )
    parser.add_argument(
        "--require-version",
        help="Assert that both HTTP and WebSocket initialize report this server version.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary = run_release_smoke(args.endpoint, require_version=args.require_version)
    except ReleaseSmokeError as exc:
        print(f"Release smoke failed: {exc}", file=sys.stderr)
        return 1

    payload = {
        "endpoint": summary.endpoint,
        "serverVersion": summary.server_version,
        "healthz": summary.healthz,
        "readyz": summary.readyz,
        "manifest": summary.manifest,
        "resolve_exact": summary.resolve_exact,
        "resolve_ambiguous": summary.resolve_ambiguous,
        "resolve_not_found": summary.resolve_not_found,
        "prioritization": summary.prioritization,
        "interop": summary.interop,
        "websocket": summary.websocket,
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print("Release smoke passed.")
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
