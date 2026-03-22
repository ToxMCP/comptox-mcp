#!/usr/bin/env python3
"""Live smoke runner for the public interop tools over MCP HTTP transport."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Iterable, Optional


DEFAULT_ENDPOINT = os.environ.get("EPA_MCP_HTTP_ENDPOINT", "http://127.0.0.1:8000/mcp")
DEFAULT_PROTOCOL_VERSION = "2025-06-18"
DEFAULT_DTXSID = "DTXSID2020006"
DEFAULT_CHEMICAL_LABEL = "Acetaminophen"
REQUIRED_TOOLS = (
    "assemble_comptox_evidence_pack",
    "build_aop_linkage_summary",
    "build_pbpk_context_bundle",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Validates the live public interop tools: "
            "build_aop_linkage_summary, "
            "build_pbpk_context_bundle, "
            "assemble_comptox_evidence_pack."
        ),
    )
    parser.add_argument(
        "--endpoint",
        default=DEFAULT_ENDPOINT,
        help="MCP HTTP endpoint to probe (default: %(default)s)",
    )
    parser.add_argument(
        "--bearer-token",
        default=os.environ.get("EPA_MCP_BEARER_TOKEN"),
        help="Optional bearer token for the MCP HTTP endpoint.",
    )
    parser.add_argument(
        "--protocol-version",
        default=DEFAULT_PROTOCOL_VERSION,
        help="Requested MCP protocol version for initialize (default: %(default)s)",
    )
    parser.add_argument(
        "--dtxsid",
        default=DEFAULT_DTXSID,
        help="DSSTox substance identifier used for interop smoke checks.",
    )
    parser.add_argument(
        "--chemical-label",
        default=DEFAULT_CHEMICAL_LABEL,
        help="Human-readable label used in the smoke summary output.",
    )
    parser.add_argument(
        "--max-assays",
        type=int,
        default=5,
        help="Max assays for AOP/evidence-pack smoke calls (default: %(default)s)",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=180,
        help="HTTP timeout for each MCP request (default: %(default)s)",
    )
    parser.add_argument(
        "--skip-health",
        action="store_true",
        help="Skip the /healthz probe and only exercise MCP JSON-RPC methods.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit only the final JSON summary on stdout.",
    )
    return parser.parse_args()


class SmokeError(RuntimeError):
    """Raised when the live smoke runner finds an invalid runtime condition."""


class HttpMcpClient:
    def __init__(
        self,
        *,
        endpoint: str,
        timeout_seconds: int,
        bearer_token: Optional[str] = None,
    ) -> None:
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self.bearer_token = bearer_token
        self.session_id = "interop-live-smoke"
        self._request_id = 0

    def call(
        self, method: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        self._request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params or {},
        }
        headers = {
            "Content-Type": "application/json",
            "Mcp-Session-Id": self.session_id,
        }
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"

        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self.timeout_seconds
            ) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise SmokeError(f"{method} returned HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise SmokeError(
                f"{method} failed to reach {self.endpoint}: {exc}"
            ) from exc

        if "error" in body:
            raise SmokeError(
                f"{method} returned JSON-RPC error: {json.dumps(body['error'])}"
            )
        return body["result"]

    def healthz(self) -> Dict[str, Any]:
        url = _derive_healthz_url(self.endpoint)
        request = urllib.request.Request(
            url, headers=_optional_auth_header(self.bearer_token)
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self.timeout_seconds
            ) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise SmokeError(f"/healthz returned HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise SmokeError(f"Failed to reach {url}: {exc}") from exc


def _derive_healthz_url(endpoint: str) -> str:
    parsed = urllib.parse.urlsplit(endpoint)
    if parsed.path.endswith("/mcp"):
        path = parsed.path[: -len("/mcp")] + "/healthz"
    else:
        path = parsed.path.rstrip("/") + "/healthz"
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _optional_auth_header(bearer_token: Optional[str]) -> Dict[str, str]:
    if not bearer_token:
        return {}
    return {"Authorization": f"Bearer {bearer_token}"}


def _assert_keys(
    label: str, payload: Dict[str, Any], required_keys: Iterable[str]
) -> None:
    missing = [key for key in required_keys if key not in payload]
    if missing:
        raise SmokeError(f"{label} missing required keys: {missing}")


def _extract_mmdb_status(pack: Dict[str, Any]) -> Dict[str, Any]:
    runtime_metadata = pack.get("mcpMetadata") or pack.get("metadata", {})
    step = (
        runtime_metadata.get("steps", {}).get("exposure:mmdb", {}).get("metadata", {})
    )
    return {
        "status": step.get("status"),
        "optional": step.get("optional"),
        "missing": step.get("missing"),
    }


def run_smoke(args: argparse.Namespace) -> Dict[str, Any]:
    client = HttpMcpClient(
        endpoint=args.endpoint,
        timeout_seconds=args.timeout_seconds,
        bearer_token=args.bearer_token,
    )

    summary: Dict[str, Any] = {
        "endpoint": args.endpoint,
        "chemical": {"label": args.chemical_label, "dtxsid": args.dtxsid},
    }

    if not args.skip_health:
        health = client.healthz()
        if health.get("status") != "ok":
            raise SmokeError(
                f"/healthz returned unexpected payload: {json.dumps(health)}"
            )
        summary["healthz"] = health

    initialize = client.call(
        "initialize",
        {
            "protocolVersion": args.protocol_version,
            "capabilities": {},
            "clientInfo": {"name": "epacomp-interop-smoke", "version": "0.1.0"},
        },
    )
    protocol_version = initialize.get("protocolVersion")
    if not protocol_version:
        raise SmokeError("initialize did not return a protocolVersion")
    summary["protocolVersion"] = protocol_version

    tools = client.call("tools/list").get("tools", [])
    tool_names = {tool.get("name") for tool in tools}
    missing_tools = sorted(set(REQUIRED_TOOLS) - tool_names)
    if missing_tools:
        raise SmokeError(
            f"Required interop tools missing from tools/list: {missing_tools}"
        )
    summary["toolCount"] = len(tools)

    resources = client.call("resources/list").get("resources", [])
    resource_names = {resource.get("name") for resource in resources}
    if "interop" not in resource_names:
        raise SmokeError("resources/list did not include the interop resource")
    summary["resourceCount"] = len(resources)

    aop = client.call(
        "tools/call",
        {
            "name": "build_aop_linkage_summary",
            "arguments": {"dtxsid": args.dtxsid, "max_assays": args.max_assays},
        },
    ).get("structuredContent", {})
    _assert_keys(
        "build_aop_linkage_summary",
        aop,
        ("chemicalRef", "lookupMode", "mappings", "confidence", "provenance"),
    )
    summary["aopLinkage"] = {
        "mappingCount": len(aop.get("mappings", [])),
        "lookupMode": aop.get("lookupMode"),
    }

    pbpk = client.call(
        "tools/call",
        {
            "name": "build_pbpk_context_bundle",
            "arguments": {"dtxsid": args.dtxsid},
        },
    ).get("structuredContent", {})
    _assert_keys(
        "build_pbpk_context_bundle",
        pbpk,
        (
            "chemicalIdentityRef",
            "httkSlice",
            "hazardAdmeIviveSlice",
            "modelCardRefs",
            "handoffTarget",
            "provenance",
        ),
    )
    if pbpk.get("handoffTarget") != "pbpk-mcp":
        raise SmokeError(
            f"build_pbpk_context_bundle returned unexpected handoffTarget: {pbpk.get('handoffTarget')}"
        )
    summary["pbpkContext"] = {
        "handoffTarget": pbpk.get("handoffTarget"),
        "httkRecordCount": pbpk.get("httkSlice", {}).get("recordCount"),
        "modelCardRefs": len(pbpk.get("modelCardRefs", [])),
    }

    pack = client.call(
        "tools/call",
        {
            "name": "assemble_comptox_evidence_pack",
            "arguments": {
                "dtxsid": args.dtxsid,
                "hazard_datasets": ["toxval", "adme_ivive"],
                "max_assays": args.max_assays,
            },
        },
    ).get("structuredContent", {})
    _assert_keys(
        "assemble_comptox_evidence_pack",
        pack,
        (
            "chemicalIdentity",
            "hazardEvidenceSummary",
            "exposureEvidenceSummary",
            "bioactivityEvidenceSummary",
            "aopLinkageSummary",
            "pbpkContextBundle",
            "metadata",
            "semanticCoverage",
        ),
    )
    mmdb_status = _extract_mmdb_status(pack)
    if mmdb_status["status"] == 404 and (
        mmdb_status["optional"] is not True or mmdb_status["missing"] is not True
    ):
        raise SmokeError(
            "assemble_comptox_evidence_pack recorded an MMDB 404 without optional/missing markers"
        )
    summary["evidencePack"] = {
        "semanticCoverage": pack.get("semanticCoverage"),
        "suiteRole": pack.get("metadata", {}).get("suiteRole"),
        "hasMcpMetadata": "mcpMetadata" in pack,
        "mmdbRecordCount": pack.get("exposureEvidenceSummary", {})
        .get("mmdb", {})
        .get("recordCount"),
        "mmdbStatus": mmdb_status,
    }

    return summary


def main() -> int:
    args = parse_args()
    try:
        summary = run_smoke(args)
    except SmokeError as exc:
        print(f"Interop smoke failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(summary, indent=2))
        return 0

    print("Interop live smoke passed.")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
