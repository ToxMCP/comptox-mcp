from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

from epacomp_tox.contracts import SchemaValidationError, validate_payload


DEFAULT_ENDPOINT = os.environ.get("EPA_MCP_HTTP_ENDPOINT", "http://127.0.0.1:8000/mcp")
DEFAULT_PROTOCOL_VERSION = "2025-06-18"
DEFAULT_DTXSID = "DTXSID2020006"
DEFAULT_CHEMICAL_LABEL = "Acetaminophen"
DEFAULT_CAPTURE_DIR = (
    Path(__file__).resolve().parents[2] / "tests" / "golden" / "interop_live"
)
REQUIRED_TOOLS = (
    "assemble_comptox_evidence_pack",
    "build_aop_linkage_summary",
    "build_pbpk_context_bundle",
)

_TOOL_CAPTURE_SPECS: Mapping[str, Dict[str, Any]] = {
    "assemble_comptox_evidence_pack": {
        "required_keys": (
            "chemicalIdentity",
            "hazardEvidenceSummary",
            "exposureEvidenceSummary",
            "bioactivityEvidenceSummary",
            "aopLinkageSummary",
            "pbpkContextBundle",
            "metadata",
            "semanticCoverage",
        ),
        "response_schema": ("workflow", "comptox_evidence_pack.response.schema"),
        "portable_schema_path": "schemas/comptoxEvidencePack.v1.json",
        "response_schema_path": (
            "docs/contracts/schemas/workflow/"
            "comptox_evidence_pack.response.schema.json"
        ),
    },
    "build_aop_linkage_summary": {
        "required_keys": (
            "chemicalRef",
            "lookupMode",
            "mappings",
            "confidence",
            "provenance",
        ),
        "response_schema": ("workflow", "aop_linkage_summary.response.schema"),
        "portable_schema_path": "schemas/aopLinkageSummary.v1.json",
        "response_schema_path": (
            "docs/contracts/schemas/workflow/"
            "aop_linkage_summary.response.schema.json"
        ),
    },
    "build_pbpk_context_bundle": {
        "required_keys": (
            "chemicalIdentityRef",
            "httkSlice",
            "hazardAdmeIviveSlice",
            "modelCardRefs",
            "handoffTarget",
            "provenance",
        ),
        "response_schema": ("workflow", "pbpk_context_bundle.response.schema"),
        "portable_schema_path": "schemas/pbpkContextBundle.v1.json",
        "response_schema_path": (
            "docs/contracts/schemas/workflow/"
            "pbpk_context_bundle.response.schema.json"
        ),
    },
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Live smoke runner for the public interop tools over MCP HTTP transport.",
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
        "--capture-dir",
        type=Path,
        help=(
            "Optional directory where validated live interop payload fixtures and "
            "capture_manifest.json should be written."
        ),
    )
    parser.add_argument(
        "--refresh-live-fixtures",
        action="store_true",
        help=(
            "Allow overwriting existing live interop fixture files in --capture-dir. "
            "Without this flag, capture aborts if fixture files already exist."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit only the final JSON summary on stdout.",
    )
    return parser


class SmokeError(RuntimeError):
    """Raised when the live smoke runner finds an invalid runtime condition."""


@dataclass(frozen=True)
class SmokeRunArtifacts:
    summary: Dict[str, Any]
    payloads: Dict[str, Dict[str, Any]]
    tool_arguments: Dict[str, Dict[str, Any]]


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


def _tool_arguments(args: argparse.Namespace) -> Dict[str, Dict[str, Any]]:
    return {
        "build_aop_linkage_summary": {
            "dtxsid": args.dtxsid,
            "max_assays": args.max_assays,
        },
        "build_pbpk_context_bundle": {"dtxsid": args.dtxsid},
        "assemble_comptox_evidence_pack": {
            "dtxsid": args.dtxsid,
            "hazard_datasets": ["toxval", "adme_ivive"],
            "max_assays": args.max_assays,
        },
    }


def run_live_interop_suite(args: argparse.Namespace) -> SmokeRunArtifacts:
    client = HttpMcpClient(
        endpoint=args.endpoint,
        timeout_seconds=args.timeout_seconds,
        bearer_token=args.bearer_token,
    )

    summary: Dict[str, Any] = {
        "endpoint": args.endpoint,
        "chemical": {"label": args.chemical_label, "dtxsid": args.dtxsid},
    }
    payloads: Dict[str, Dict[str, Any]] = {}
    tool_arguments = _tool_arguments(args)

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
            "arguments": tool_arguments["build_aop_linkage_summary"],
        },
    ).get("structuredContent", {})
    _assert_keys(
        "build_aop_linkage_summary",
        aop,
        _TOOL_CAPTURE_SPECS["build_aop_linkage_summary"]["required_keys"],
    )
    payloads["build_aop_linkage_summary"] = aop
    summary["aopLinkage"] = {
        "mappingCount": len(aop.get("mappings", [])),
        "lookupMode": aop.get("lookupMode"),
    }

    pbpk = client.call(
        "tools/call",
        {
            "name": "build_pbpk_context_bundle",
            "arguments": tool_arguments["build_pbpk_context_bundle"],
        },
    ).get("structuredContent", {})
    _assert_keys(
        "build_pbpk_context_bundle",
        pbpk,
        _TOOL_CAPTURE_SPECS["build_pbpk_context_bundle"]["required_keys"],
    )
    if pbpk.get("handoffTarget") != "pbpk-mcp":
        raise SmokeError(
            "build_pbpk_context_bundle returned unexpected handoffTarget: "
            f"{pbpk.get('handoffTarget')}"
        )
    payloads["build_pbpk_context_bundle"] = pbpk
    summary["pbpkContext"] = {
        "handoffTarget": pbpk.get("handoffTarget"),
        "httkRecordCount": pbpk.get("httkSlice", {}).get("recordCount"),
        "modelCardRefs": len(pbpk.get("modelCardRefs", [])),
    }

    pack = client.call(
        "tools/call",
        {
            "name": "assemble_comptox_evidence_pack",
            "arguments": tool_arguments["assemble_comptox_evidence_pack"],
        },
    ).get("structuredContent", {})
    _assert_keys(
        "assemble_comptox_evidence_pack",
        pack,
        _TOOL_CAPTURE_SPECS["assemble_comptox_evidence_pack"]["required_keys"],
    )
    mmdb_status = _extract_mmdb_status(pack)
    if mmdb_status["status"] == 404 and (
        mmdb_status["optional"] is not True or mmdb_status["missing"] is not True
    ):
        raise SmokeError(
            "assemble_comptox_evidence_pack recorded an MMDB 404 without "
            "optional/missing markers"
        )
    payloads["assemble_comptox_evidence_pack"] = pack
    summary["evidencePack"] = {
        "semanticCoverage": pack.get("semanticCoverage"),
        "suiteRole": pack.get("metadata", {}).get("suiteRole"),
        "hasMcpMetadata": "mcpMetadata" in pack,
        "mmdbRecordCount": pack.get("exposureEvidenceSummary", {})
        .get("mmdb", {})
        .get("recordCount"),
        "mmdbStatus": mmdb_status,
    }

    return SmokeRunArtifacts(
        summary=summary,
        payloads=payloads,
        tool_arguments=tool_arguments,
    )


def run_smoke(args: argparse.Namespace) -> Dict[str, Any]:
    return run_live_interop_suite(args).summary


def write_capture_bundle(
    artifacts: SmokeRunArtifacts,
    *,
    capture_dir: Path,
    refresh: bool = False,
) -> Dict[str, Any]:
    capture_dir = Path(capture_dir)
    target_paths = [
        capture_dir / f"{tool_name}.json" for tool_name in sorted(artifacts.payloads)
    ]
    manifest_path = capture_dir / "capture_manifest.json"
    if not refresh:
        existing = [
            path.name
            for path in (*target_paths, manifest_path)
            if path.exists()
        ]
        if existing:
            raise SmokeError(
                "Live interop fixture capture would overwrite existing files in "
                f"{capture_dir}. Re-run with --refresh-live-fixtures to update: "
                f"{sorted(existing)}"
            )

    fixture_payloads: Dict[str, str] = {}
    fixture_entries = []
    for tool_name in REQUIRED_TOOLS:
        payload = artifacts.payloads.get(tool_name)
        if payload is None:
            raise SmokeError(f"Missing captured payload for required tool {tool_name}")
        spec = _TOOL_CAPTURE_SPECS[tool_name]
        namespace, schema_name = spec["response_schema"]
        try:
            validate_payload(payload, namespace=namespace, name=schema_name)
        except SchemaValidationError as exc:
            raise SmokeError(
                f"{tool_name} payload failed schema validation during live capture: {exc}"
            ) from exc
        rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        fixture_payloads[tool_name] = rendered
        fixture_entries.append(
            {
                "tool": tool_name,
                "file": f"{tool_name}.json",
                "arguments": artifacts.tool_arguments[tool_name],
                "responseSchemaRef": {
                    "namespace": namespace,
                    "name": schema_name,
                },
                "responseSchemaPath": spec["response_schema_path"],
                "portableSchemaPath": spec["portable_schema_path"],
                "sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
                "sizeBytes": len(rendered.encode("utf-8")),
                "topLevelKeys": sorted(payload.keys()),
            }
        )

    capture_dir.mkdir(parents=True, exist_ok=True)
    for tool_name, rendered in fixture_payloads.items():
        (capture_dir / f"{tool_name}.json").write_text(rendered, encoding="utf-8")

    manifest = {
        "captureVersion": 1,
        "capturedAt": _utc_now(),
        "endpoint": artifacts.summary.get("endpoint"),
        "protocolVersion": artifacts.summary.get("protocolVersion"),
        "chemical": artifacts.summary.get("chemical"),
        "fixtures": fixture_entries,
        "smokeSummary": artifacts.summary,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


__all__ = [
    "DEFAULT_CAPTURE_DIR",
    "DEFAULT_CHEMICAL_LABEL",
    "DEFAULT_DTXSID",
    "DEFAULT_ENDPOINT",
    "DEFAULT_PROTOCOL_VERSION",
    "REQUIRED_TOOLS",
    "HttpMcpClient",
    "SmokeError",
    "SmokeRunArtifacts",
    "build_parser",
    "run_live_interop_suite",
    "run_smoke",
    "write_capture_bundle",
]
