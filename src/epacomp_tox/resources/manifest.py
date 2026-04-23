from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from epacomp_tox.assets import data_file, iter_data_files
from epacomp_tox.contracts import schema_ref

from .base import BaseResource

if TYPE_CHECKING:
    from epacomp_tox.server import MCPServer


class ContractManifestResource(BaseResource):
    """Machine-readable inventory of the live public MCP contract surface."""

    def __init__(
        self,
        api_key: str = "",
        *,
        server_getter: Optional[Callable[[], "MCPServer"]] = None,
        repo_root: Optional[Path] = None,
    ) -> None:
        super().__init__(api_key)
        self._server_getter = server_getter
        self._repo_root = Path(repo_root) if repo_root is not None else None

    @property
    def name(self) -> str:
        return "manifest"

    @property
    def description(self) -> str:
        return "Machine-readable public contract manifest for resources, tools, schemas, and boundary notes"

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "get_contract_manifest",
                "description": "Return a machine-readable inventory of the live public resources, tools, MCP response schemas, portable schemas, and suite boundary notes",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
                "responseSchemaRef": schema_ref(
                    "manifest", "get_contract_manifest.response.schema"
                ),
            }
        ]

    def execute_tool(
        self, tool_name: str, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        if tool_name != "get_contract_manifest":
            raise ValueError(f"Unknown tool: {tool_name}")
        return self.get_contract_manifest()

    def get_contract_manifest(self) -> Dict[str, Any]:
        server = self._require_server()
        resources = server.get_resources()
        tool_defs = server.get_tools()
        registration_map = {
            registration.name: registration for registration in server.tool_registry
        }

        manifest = {
            "server": {
                **server.get_server_info(),
                "resourceCount": len(resources),
                "toolCount": len(tool_defs),
                "transportEndpoints": ["/mcp", "/mcp/ws"],
            },
            "publicBoundary": {
                "primaryRole": "evidence-federation",
                "screeningRole": "screening-prioritization",
                "experimentalModules": ["predictive", "orchestrator"],
                "notOwnedByCompToxMcp": [
                    "suite orchestrator",
                    "OECD AOP semantics",
                    "PBPK execution and qualification",
                    "final NGRA decision logic",
                ],
            },
            "resources": self._resource_entries(resources, tool_defs),
            "tools": self._tool_entries(server),
            "portableObjectSchemas": self._portable_schema_entries(),
            "responseSchemas": self._response_schema_entries(),
            "publicContractReferences": {
                "interop": [
                    self._contract_reference(
                        tool_name="assemble_comptox_evidence_pack",
                        response_schema_ref=self._response_schema_ref(
                            registration_map["assemble_comptox_evidence_pack"]
                        ),
                        portable_schema="comptoxEvidencePack.v1.json",
                        example_file="schemas/examples/comptoxEvidencePack.example.json",
                    ),
                    self._contract_reference(
                        tool_name="build_aop_linkage_summary",
                        response_schema_ref=self._response_schema_ref(
                            registration_map["build_aop_linkage_summary"]
                        ),
                        portable_schema="aopLinkageSummary.v1.json",
                        example_file="schemas/examples/aopLinkageSummary.example.json",
                    ),
                    self._contract_reference(
                        tool_name="build_pbpk_context_bundle",
                        response_schema_ref=self._response_schema_ref(
                            registration_map["build_pbpk_context_bundle"]
                        ),
                        portable_schema="pbpkContextBundle.v1.json",
                        example_file="schemas/examples/pbpkContextBundle.example.json",
                    ),
                ],
                "screeningPrioritization": [
                    self._contract_reference(
                        tool_name="prioritize_risk_signals",
                        response_schema_ref=self._response_schema_ref(
                            registration_map["prioritize_risk_signals"]
                        ),
                        portable_schema=None,
                        example_file=None,
                    )
                ],
            },
        }
        self._last_metadata = {
            "resource": self.name,
            "resourceCount": manifest["server"]["resourceCount"],
            "toolCount": manifest["server"]["toolCount"],
        }
        return manifest

    def _resource_entries(
        self, resources: List[Dict[str, Any]], tool_defs: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        for resource in resources:
            name = resource["name"]
            entries.append(
                {
                    "name": name,
                    "description": resource["description"],
                    "url": resource["url"],
                    "toolNames": sorted(
                        tool["name"]
                        for tool in tool_defs
                        if tool.get("annotations", {}).get("resource") == name
                    ),
                }
            )
        return entries

    def _tool_entries(self, server: "MCPServer") -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        for registration in server.tool_registry:
            entries.append(
                {
                    "name": registration.name,
                    "resource": registration.annotations.get("resource"),
                    "hasOutputSchema": registration.output_schema is not None,
                    "responseSchemaRef": self._response_schema_ref(registration),
                }
            )
        return sorted(entries, key=lambda item: item["name"])

    def _portable_schema_entries(self) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        paths = (
            sorted((self._repo_root / "schemas").glob("*.json"))
            if self._repo_root is not None
            else list(iter_data_files("schemas", suffix=".json"))
        )
        for path in paths:
            if path.name.startswith("."):
                continue
            data = self._load_json(path)
            example_file = self._portable_example_for(path.name)
            entries.append(
                self._drop_nones(
                    {
                        "file": f"schemas/{path.name}",
                        "title": data.get("title"),
                        "schemaId": data.get("$id"),
                        "exampleFile": example_file,
                    }
                )
            )
        return entries

    def _response_schema_entries(self) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        paths = (
            sorted(
                (self._repo_root / "docs" / "contracts" / "schemas").glob("*/*.json")
            )
            if self._repo_root is not None
            else list(
                iter_data_files("contracts", "schemas", suffix=".json", recursive=True)
            )
        )
        for path in paths:
            relative_path = (
                str(path.relative_to(self._repo_root))
                if self._repo_root is not None
                else f"docs/contracts/schemas/{path.parent.name}/{path.name}"
            )
            entries.append(
                {
                    "namespace": path.parent.name,
                    "file": path.name,
                    "path": relative_path,
                }
            )
        return entries

    @staticmethod
    def _contract_reference(
        *,
        tool_name: str,
        response_schema_ref: Dict[str, Any],
        portable_schema: Optional[str],
        example_file: Optional[str],
    ) -> Dict[str, Any]:
        payload = {
            "toolName": tool_name,
            "responseSchemaRef": response_schema_ref,
            "portableSchema": portable_schema,
            "exampleFile": example_file,
        }
        return {key: value for key, value in payload.items() if value is not None}

    def _portable_example_for(self, schema_file: str) -> Optional[str]:
        stem = schema_file.replace(".v1.json", "")
        if self._repo_root is not None:
            candidate = (
                self._repo_root / "schemas" / "examples" / f"{stem}.example.json"
            )
            if candidate.exists():
                return str(candidate.relative_to(self._repo_root))
            return None
        candidate = data_file("schemas", "examples", f"{stem}.example.json")
        if candidate.is_file():
            return f"schemas/examples/{stem}.example.json"
        return None

    @staticmethod
    def _response_schema_ref(registration: Any) -> Optional[Dict[str, str]]:
        if not getattr(registration, "response_schema_ref", None):
            return None
        namespace, name = registration.response_schema_ref
        return {"namespace": namespace, "name": name}

    def _require_server(self) -> "MCPServer":
        if self._server_getter is None:
            raise ValueError("ContractManifestResource requires a server_getter.")
        return self._server_getter()

    @staticmethod
    def _load_json(path: Path) -> Dict[str, Any]:
        import json

        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _drop_nones(payload: Dict[str, Any]) -> Dict[str, Any]:
        return {key: value for key, value in payload.items() if value is not None}
