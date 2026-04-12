from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence

from ctxpy import CtxApiError
from epacomp_tox.contracts import load_schema, schema_ref

from .base import BaseResource
from .bioactivity import BioactivityResource
from .chemical import ChemicalResource
from .exposure import ExposureResource
from .hazard import HazardResource
from .metadata import MetadataResource


class InteropResource(BaseResource):
    """Cross-suite evidence packaging and handoff tools."""

    DEFAULT_HAZARD_DATASETS = (
        "toxval",
        "toxref",
        "cancer",
        "genetox",
        "adme_ivive",
        "iris",
        "pprtv",
        "hawc",
    )

    def __init__(
        self,
        api_key: str,
        *,
        chemical_resource: Optional[ChemicalResource] = None,
        bioactivity_resource: Optional[BioactivityResource] = None,
        exposure_resource: Optional[ExposureResource] = None,
        hazard_resource: Optional[HazardResource] = None,
        metadata_resource: Optional[MetadataResource] = None,
    ) -> None:
        super().__init__(api_key)
        self.chemical_resource = chemical_resource or ChemicalResource(api_key)
        self.bioactivity_resource = bioactivity_resource or BioactivityResource(api_key)
        self.exposure_resource = exposure_resource or ExposureResource(api_key)
        self.hazard_resource = hazard_resource or HazardResource(api_key)
        self.metadata_resource = metadata_resource or MetadataResource(api_key)

    @property
    def name(self) -> str:
        return "interop"

    @property
    def description(self) -> str:
        return "Cross-suite evidence packaging and handoff builders for AOP and PBPK consumers"

    def get_tools(self) -> List[Dict[str, Any]]:
        tools = [
            {
                "name": "assemble_comptox_evidence_pack",
                "description": "Assemble a portable CompTox evidence pack combining identity, hazard, exposure, bioactivity, AOP linkage, and PBPK context slices.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "dtxsid": {
                            "type": "string",
                            "description": "DSSTox substance identifier to package.",
                        },
                        "identifier": {
                            "type": "string",
                            "description": "Optional non-DTXSID identifier to resolve before packaging.",
                        },
                        "identifier_type": {
                            "type": "string",
                            "enum": ["dtxsid", "casrn", "name", "smiles", "inchikey"],
                            "description": "Optional identifier category when `identifier` is supplied.",
                        },
                        "allow_fallback": {
                            "type": "boolean",
                            "default": False,
                        },
                        "max_candidates": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 25,
                            "default": 5,
                        },
                        "hazard_datasets": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": list(self.DEFAULT_HAZARD_DATASETS),
                            },
                            "description": "Hazard datasets to include in the portable hazard summary.",
                        },
                        "include_exposure": {
                            "type": "boolean",
                            "default": True,
                        },
                        "include_bioactivity": {
                            "type": "boolean",
                            "default": True,
                        },
                        "include_aop": {
                            "type": "boolean",
                            "default": True,
                        },
                        "include_pbpk_context": {
                            "type": "boolean",
                            "default": True,
                        },
                        "model_name": {
                            "type": "string",
                            "description": "Optional model-card name filter when collecting PBPK context references.",
                        },
                        "max_assays": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 25,
                            "default": 10,
                        },
                    },
                    "anyOf": [{"required": ["dtxsid"]}, {"required": ["identifier"]}],
                },
                "responseSchemaRef": schema_ref(
                    "workflow", "comptox_evidence_pack.response.schema"
                ),
            },
            {
                "name": "build_aop_linkage_summary",
                "description": "Build a CompTox-side AOP linkage summary from bioactivity assay and AOP crosswalk data.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "dtxsid": {
                            "type": "string",
                            "description": "DSSTox substance identifier to summarize.",
                        },
                        "identifier": {
                            "type": "string",
                            "description": "Optional non-DTXSID identifier to resolve before building the summary.",
                        },
                        "identifier_type": {
                            "type": "string",
                            "enum": ["dtxsid", "casrn", "name", "smiles", "inchikey"],
                            "description": "Optional identifier category when `identifier` is supplied.",
                        },
                        "allow_fallback": {
                            "type": "boolean",
                            "default": False,
                        },
                        "max_candidates": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 25,
                            "default": 5,
                        },
                        "aeids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional assay endpoint identifiers to prioritize for AOP mapping.",
                        },
                        "max_assays": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 25,
                            "default": 10,
                        },
                    },
                    "anyOf": [{"required": ["dtxsid"]}, {"required": ["identifier"]}],
                },
                "responseSchemaRef": schema_ref(
                    "workflow", "aop_linkage_summary.response.schema"
                ),
            },
            {
                "name": "build_pbpk_context_bundle",
                "description": "Build a CompTox-side PBPK context bundle from HTTK, ADME/IVIVE, exposure hints, and model-card references.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "dtxsid": {
                            "type": "string",
                            "description": "DSSTox substance identifier to summarize.",
                        },
                        "identifier": {
                            "type": "string",
                            "description": "Optional non-DTXSID identifier to resolve before building the bundle.",
                        },
                        "identifier_type": {
                            "type": "string",
                            "enum": ["dtxsid", "casrn", "name", "smiles", "inchikey"],
                            "description": "Optional identifier category when `identifier` is supplied.",
                        },
                        "allow_fallback": {
                            "type": "boolean",
                            "default": False,
                        },
                        "max_candidates": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 25,
                            "default": 5,
                        },
                        "model_name": {
                            "type": "string",
                            "description": "Optional model-card name filter.",
                        },
                    },
                    "anyOf": [{"required": ["dtxsid"]}, {"required": ["identifier"]}],
                },
                "responseSchemaRef": schema_ref(
                    "workflow", "pbpk_context_bundle.response.schema"
                ),
            },
        ]

        for tool in tools:
            ref = tool["responseSchemaRef"]
            tool["outputSchema"] = load_schema(ref["namespace"], ref["name"])

        return tools

    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        step_metadata: Dict[str, Dict[str, Any]] = {}
        if tool_name == "assemble_comptox_evidence_pack":
            result = self.assemble_comptox_evidence_pack(
                dtxsid=parameters.get("dtxsid"),
                identifier=parameters.get("identifier"),
                identifier_type=parameters.get("identifier_type"),
                allow_fallback=parameters.get("allow_fallback", False),
                max_candidates=parameters.get("max_candidates", 5),
                hazard_datasets=parameters.get("hazard_datasets"),
                include_exposure=parameters.get("include_exposure", True),
                include_bioactivity=parameters.get("include_bioactivity", True),
                include_aop=parameters.get("include_aop", True),
                include_pbpk_context=parameters.get("include_pbpk_context", True),
                model_name=parameters.get("model_name"),
                max_assays=parameters.get("max_assays", 10),
                step_metadata=step_metadata,
            )
        elif tool_name == "build_aop_linkage_summary":
            result = self.build_aop_linkage_summary(
                dtxsid=parameters.get("dtxsid"),
                identifier=parameters.get("identifier"),
                identifier_type=parameters.get("identifier_type"),
                allow_fallback=parameters.get("allow_fallback", False),
                max_candidates=parameters.get("max_candidates", 5),
                aeids=parameters.get("aeids"),
                max_assays=parameters.get("max_assays", 10),
                step_metadata=step_metadata,
            )
        elif tool_name == "build_pbpk_context_bundle":
            result = self.build_pbpk_context_bundle(
                dtxsid=parameters.get("dtxsid"),
                identifier=parameters.get("identifier"),
                identifier_type=parameters.get("identifier_type"),
                allow_fallback=parameters.get("allow_fallback", False),
                max_candidates=parameters.get("max_candidates", 5),
                model_name=parameters.get("model_name"),
                step_metadata=step_metadata,
            )
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

        self._last_metadata = {
            "steps": step_metadata,
            "resource": self.name,
        }
        return result

    def assemble_comptox_evidence_pack(
        self,
        *,
        dtxsid: Optional[str] = None,
        identifier: Optional[str] = None,
        identifier_type: Optional[str] = None,
        allow_fallback: bool = False,
        max_candidates: int = 5,
        hazard_datasets: Optional[Sequence[str]] = None,
        include_exposure: bool = True,
        include_bioactivity: bool = True,
        include_aop: bool = True,
        include_pbpk_context: bool = True,
        model_name: Optional[str] = None,
        max_assays: int = 10,
        step_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        steps = step_metadata if step_metadata is not None else {}
        timestamp = self._timestamp()
        identity, identity_resolution = self._resolve_requested_identity(
            dtxsid=dtxsid,
            identifier=identifier,
            identifier_type=identifier_type,
            allow_fallback=allow_fallback,
            max_candidates=max_candidates,
            step_metadata=steps,
        )

        hazard_summary = self._build_hazard_evidence_summary(
            identity=identity,
            datasets=hazard_datasets or self.DEFAULT_HAZARD_DATASETS,
            step_metadata=steps,
        )
        exposure_summary = (
            self._build_exposure_evidence_summary(
                identity=identity, step_metadata=steps
            )
            if include_exposure
            else None
        )
        bioactivity_summary = (
            self._build_bioactivity_evidence_summary(
                identity=identity,
                max_assays=max_assays,
                step_metadata=steps,
            )
            if include_bioactivity
            else None
        )
        aop_summary = (
            self._build_aop_linkage_summary(
                dtxsid=dtxsid,
                identity=identity,
                summary_records=(
                    bioactivity_summary["rawSummaryRecords"]
                    if bioactivity_summary
                    and "rawSummaryRecords" in bioactivity_summary
                    else None
                ),
                max_assays=max_assays,
                step_metadata=steps,
            )
            if include_aop
            else None
        )
        pbpk_bundle = (
            self._build_pbpk_context_bundle(
                dtxsid=dtxsid,
                identity=identity,
                model_name=model_name,
                step_metadata=steps,
            )
            if include_pbpk_context
            else None
        )

        if bioactivity_summary and "rawSummaryRecords" in bioactivity_summary:
            bioactivity_summary = dict(bioactivity_summary)
            bioactivity_summary.pop("rawSummaryRecords", None)

        source_tools = sorted(
            {
                info.get("tool")
                for info in steps.values()
                if isinstance(info, dict) and info.get("tool")
            }
        )
        model_card_refs = pbpk_bundle["modelCardRefs"] if pbpk_bundle else []

        payload = {
            "chemicalIdentity": identity,
            "hazardEvidenceSummary": hazard_summary,
            "exposureEvidenceSummary": exposure_summary,
            "bioactivityEvidenceSummary": bioactivity_summary,
            "aopLinkageSummary": aop_summary,
            "pbpkContextBundle": pbpk_bundle,
            "metadata": {
                "packId": f"comptox-pack-{identity['dtxsid']}-{timestamp}",
                "sourceMcp": "epacomp-tox-mcp",
                "createdAt": timestamp,
                "suiteRole": "evidence-federation",
                "downstreamConsumers": ["aop-mcp", "pbpk-mcp"],
                "modelCardRefs": model_card_refs,
            },
            "audit": {
                "generatedAt": timestamp,
                "generatedBy": "assemble_comptox_evidence_pack",
                "requestId": f"interop-{identity['dtxsid']}-{timestamp}",
                "sourceTools": source_tools,
                "notes": [
                    "CompTox evidence pack for downstream MCP consumers.",
                ],
            },
            "semanticCoverage": {
                "identity": "detailed",
                "hazard": "summary" if hazard_summary else "none",
                "exposure": "summary" if exposure_summary else "none",
                "bioactivity": "summary" if bioactivity_summary else "none",
                "aopLinkage": self._coverage_for_linkage(aop_summary),
                "pbpkContext": "summary" if pbpk_bundle else "none",
            },
        }
        return self._annotate_public_payload(
            payload,
            identity_resolution=identity_resolution,
            source_tools=source_tools,
            known_data_gaps=self._known_data_gaps_for_pack(
                hazard_summary=hazard_summary,
                exposure_summary=exposure_summary,
                bioactivity_summary=bioactivity_summary,
                aop_summary=aop_summary,
                pbpk_bundle=pbpk_bundle,
            ),
        )

    def build_aop_linkage_summary(
        self,
        *,
        dtxsid: Optional[str] = None,
        identifier: Optional[str] = None,
        identifier_type: Optional[str] = None,
        allow_fallback: bool = False,
        max_candidates: int = 5,
        aeids: Optional[Sequence[str]] = None,
        max_assays: int = 10,
        step_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        steps = step_metadata if step_metadata is not None else {}
        identity, identity_resolution = self._resolve_requested_identity(
            dtxsid=dtxsid,
            identifier=identifier,
            identifier_type=identifier_type,
            allow_fallback=allow_fallback,
            max_candidates=max_candidates,
            step_metadata=steps,
        )
        payload = self._build_aop_linkage_summary(
            dtxsid=identity["dtxsid"],
            identity=identity,
            provided_aeids=aeids,
            max_assays=max_assays,
            step_metadata=steps,
        )
        return self._annotate_public_payload(
            payload,
            identity_resolution=identity_resolution,
            source_tools=self._source_tools_from_steps(steps),
            known_data_gaps=self._known_data_gaps_for_aop(payload),
        )

    def build_pbpk_context_bundle(
        self,
        *,
        dtxsid: Optional[str] = None,
        identifier: Optional[str] = None,
        identifier_type: Optional[str] = None,
        allow_fallback: bool = False,
        max_candidates: int = 5,
        model_name: Optional[str] = None,
        step_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        steps = step_metadata if step_metadata is not None else {}
        identity, identity_resolution = self._resolve_requested_identity(
            dtxsid=dtxsid,
            identifier=identifier,
            identifier_type=identifier_type,
            allow_fallback=allow_fallback,
            max_candidates=max_candidates,
            step_metadata=steps,
        )
        payload = self._build_pbpk_context_bundle(
            dtxsid=identity["dtxsid"],
            identity=identity,
            model_name=model_name,
            step_metadata=steps,
        )
        return self._annotate_public_payload(
            payload,
            identity_resolution=identity_resolution,
            source_tools=self._source_tools_from_steps(steps),
            known_data_gaps=self._known_data_gaps_for_pbpk(payload),
        )

    def _resolve_identity_record(
        self, dtxsid: str, step_metadata: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        normalized_sid = (dtxsid or "").strip().upper()
        if not normalized_sid:
            raise ValueError("dtxsid is required.")

        matches = self.chemical_resource.search_chemical(
            query=normalized_sid,
            search_type="equals",
        )
        self._record_step(
            step_metadata,
            step_name="chemical:search",
            resource=self.chemical_resource,
            tool_name="search_chemical",
        )

        candidate = None
        for item in matches:
            if str(item.get("dtxsid", "")).upper() == normalized_sid:
                candidate = item
                break
        if candidate is None:
            candidate = matches[0] if matches else {}

        preferred_name = candidate.get("preferredName") or normalized_sid
        return {
            "dtxsid": candidate.get("dtxsid") or normalized_sid,
            "preferredName": preferred_name,
            "casrn": candidate.get("casrn"),
            "inchikey": candidate.get("inchikey") or candidate.get("inchiKey"),
            "smiles": candidate.get("smiles"),
            "synonyms": self._ensure_string_list(candidate.get("synonyms")),
            "provenance": self._build_provenance(
                generated_by="resolve_identity_record",
                step_metadata=step_metadata,
                notes=[
                    "Identity resolved through the CompTox chemical search surface."
                ],
            ),
        }

    def _resolve_requested_identity(
        self,
        *,
        dtxsid: Optional[str],
        identifier: Optional[str],
        identifier_type: Optional[str],
        allow_fallback: bool,
        max_candidates: int,
        step_metadata: Dict[str, Dict[str, Any]],
    ) -> tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        normalized_sid = (dtxsid or "").strip().upper() or None
        normalized_identifier = (identifier or "").strip() or None
        if normalized_identifier:
            resolution = self.chemical_resource.resolve_chemical_identifier(
                identifier=normalized_identifier,
                identifier_type=identifier_type,
                allow_fallback=allow_fallback,
                max_candidates=max_candidates,
            )
            self._record_step(
                step_metadata,
                step_name="chemical:resolve",
                resource=self.chemical_resource,
                tool_name="resolve_chemical_identifier",
            )
            if resolution["status"] != "resolved" or not resolution.get(
                "canonicalDtxsid"
            ):
                raise ValueError(
                    f"Unable to resolve identifier '{normalized_identifier}': {resolution['status']}"
                )
            canonical_sid = str(resolution["canonicalDtxsid"]).upper()
            if normalized_sid and normalized_sid != canonical_sid:
                raise ValueError(
                    "Provided dtxsid does not match the resolved canonical identifier."
                )
            return self._resolve_identity_record(canonical_sid, step_metadata), (
                resolution
                if str(resolution.get("inputType", "")).lower() != "dtxsid"
                else None
            )

        if not normalized_sid:
            raise ValueError("dtxsid or identifier is required.")
        return self._resolve_identity_record(normalized_sid, step_metadata), None

    def _build_hazard_evidence_summary(
        self,
        *,
        identity: Dict[str, Any],
        datasets: Sequence[str],
        step_metadata: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        fetchers = {
            "toxval": (
                "get_hazard_toxval",
                lambda sid: self.hazard_resource.get_hazard_toxval(sid),
                "summary",
            ),
            "toxref": (
                "get_hazard_toxref",
                lambda sid: self.hazard_resource.get_hazard_toxref(
                    dataset="summary",
                    lookup_type="dtxsid",
                    value=sid,
                ),
                "summary",
            ),
            "cancer": (
                "get_hazard_cancer_summary",
                lambda sid: self.hazard_resource.get_hazard_cancer_summary(sid),
                "summary",
            ),
            "genetox": (
                "get_hazard_genetox_summary",
                lambda sid: self.hazard_resource.get_hazard_genetox_summary(sid),
                "summary",
            ),
            "adme_ivive": (
                "get_hazard_adme_ivive",
                lambda sid: self.hazard_resource.get_hazard_adme_ivive(sid),
                "summary",
            ),
            "iris": (
                "get_hazard_iris",
                lambda sid: self.hazard_resource.get_hazard_iris(sid),
                "summary",
            ),
            "pprtv": (
                "get_hazard_pprtv",
                lambda sid: self.hazard_resource.get_hazard_pprtv(sid),
                "summary",
            ),
            "hawc": (
                "get_hazard_hawc",
                lambda sid: self.hazard_resource.get_hazard_hawc(sid),
                "summary",
            ),
        }

        slices: List[Dict[str, Any]] = []
        findings: List[Dict[str, Any]] = []
        references: List[Dict[str, Any]] = []
        requested_tools: List[str] = []

        for dataset in datasets:
            if dataset not in fetchers:
                raise ValueError(f"Unsupported hazard dataset '{dataset}'.")
            tool_name, fetcher, summary_level = fetchers[dataset]
            records = fetcher(identity["dtxsid"])
            self._record_step(
                step_metadata,
                step_name=f"hazard:{dataset}",
                resource=self.hazard_resource,
                tool_name=tool_name,
            )
            requested_tools.append(tool_name)
            slices.append(
                {
                    "dataset": dataset,
                    "summaryLevel": summary_level,
                    "recordCount": len(records),
                    "records": records,
                    "sourceTool": tool_name,
                    "retrievedAt": self._timestamp(),
                }
            )
            if records:
                findings.append(
                    self._drop_nones(
                        {
                            "statement": f"Retrieved {len(records)} {dataset} record(s) for {identity['preferredName']}.",
                            "sourceDataset": dataset,
                            "endpoint": self._pick_string(
                                records[0], "effect", "endpoint", "source", "assay"
                            ),
                            "value": self._pick_value(
                                records[0], "value", "ac50", "potency", "score"
                            ),
                            "unit": self._pick_string(records[0], "unit"),
                        }
                    )
                )
            references.append(
                {
                    "citation": f"EPA CompTox hazard dataset: {dataset}.",
                    "url": "https://comptox.epa.gov/ctx-api/v1/hazard",
                }
            )

        return {
            "chemicalRef": self._chemical_ref(identity),
            "datasets": slices,
            "keyFindings": findings,
            "references": references,
            "provenance": self._build_provenance(
                generated_by="assemble_comptox_evidence_pack",
                step_metadata=step_metadata,
                notes=[
                    "Hazard evidence compiled from selected CompTox hazard datasets."
                ],
            ),
            "requestMetadata": {
                "sourceTools": requested_tools,
                "requestedAt": self._timestamp(),
                "summaryOnly": True,
                "requestId": f"hazard-{identity['dtxsid']}",
            },
        }

    def _build_exposure_evidence_summary(
        self,
        *,
        identity: Dict[str, Any],
        step_metadata: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        cpdat = self.exposure_resource.search_cpdat("puc", [identity["dtxsid"]])
        self._record_step(
            step_metadata,
            step_name="exposure:cpdat",
            resource=self.exposure_resource,
            tool_name="search_cpdat",
        )
        seem = self.exposure_resource.get_seem_general(identity["dtxsid"])
        self._record_step(
            step_metadata,
            step_name="exposure:seem",
            resource=self.exposure_resource,
            tool_name="get_seem_general",
        )
        httk = self.exposure_resource.get_exposure_httk(identity["dtxsid"])
        self._record_step(
            step_metadata,
            step_name="exposure:httk",
            resource=self.exposure_resource,
            tool_name="get_exposure_httk",
        )
        mmdb = self._optional_records(
            fetcher=lambda: self.exposure_resource.get_exposure_mmdb_aggregate_by_dtxsid(
                identity["dtxsid"]
            ),
            step_metadata=step_metadata,
            step_name="exposure:mmdb",
            resource=self.exposure_resource,
            tool_name="get_exposure_mmdb_aggregate_by_dtxsid",
        )
        qsurs = self.exposure_resource.search_qsurs([identity["dtxsid"]])
        self._record_step(
            step_metadata,
            step_name="exposure:qsurs",
            resource=self.exposure_resource,
            tool_name="search_qsurs",
        )

        return {
            "chemicalRef": self._chemical_ref(identity),
            "cpdat": self._evidence_slice(cpdat, "search_cpdat"),
            "seem": self._evidence_slice(seem, "get_seem_general"),
            "httk": self._evidence_slice(httk, "get_exposure_httk"),
            "mmdb": self._evidence_slice(mmdb, "get_exposure_mmdb_aggregate_by_dtxsid"),
            "qsurs": self._evidence_slice(qsurs, "search_qsurs"),
            "provenance": self._build_provenance(
                generated_by="assemble_comptox_evidence_pack",
                step_metadata=step_metadata,
                notes=[
                    "Exposure evidence compiled from CPDat, SEEM, HTTK, MMDB, and QSUR outputs."
                ],
            ),
        }

    def _optional_records(
        self,
        *,
        fetcher,
        step_metadata: Dict[str, Dict[str, Any]],
        step_name: str,
        resource: BaseResource,
        tool_name: str,
        allow_statuses: Sequence[int] = (404,),
    ) -> List[Dict[str, Any]]:
        try:
            records = fetcher()
        except CtxApiError as exc:
            if exc.status not in allow_statuses:
                raise
            step_metadata[step_name] = {
                "resource": resource.name,
                "tool": tool_name,
                "metadata": self._drop_nones(
                    {
                        "status": exc.status,
                        "request_id": exc.request_id,
                        "rate_limit": exc.rate_limit,
                        "retry_after": exc.retry_after,
                        "optional": True,
                        "missing": True,
                        "error": str(exc),
                        "detail": exc.detail,
                    }
                ),
                "capturedAt": self._timestamp(),
            }
            return []

        self._record_step(
            step_metadata,
            step_name=step_name,
            resource=resource,
            tool_name=tool_name,
        )
        return records

    def _build_bioactivity_evidence_summary(
        self,
        *,
        identity: Dict[str, Any],
        max_assays: int,
        step_metadata: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        summary_records = self.bioactivity_resource.get_bioactivity_summary_by_dtxsid(
            identity["dtxsid"]
        )
        self._record_step(
            step_metadata,
            step_name="bioactivity:summary",
            resource=self.bioactivity_resource,
            tool_name="get_bioactivity_summary_by_dtxsid",
        )

        assays = self._bioactivity_assays_from_summary(summary_records, max_assays)
        _, aeids = self._assay_refs_from_summary(summary_records, max_assays)
        targets = self._target_refs_from_summary(summary_records)
        aop_summary = self._build_aop_linkage_summary(
            dtxsid=identity["dtxsid"],
            identity=identity,
            provided_aeids=aeids,
            summary_records=summary_records,
            max_assays=max_assays,
            step_metadata=step_metadata,
        )

        active_assay_count = 0
        for record in summary_records:
            hit_call = self._pick_value(record, "hitcall", "hitCall")
            if isinstance(hit_call, bool) and hit_call:
                active_assay_count += 1
            elif isinstance(hit_call, (int, float)) and hit_call:
                active_assay_count += 1

        return {
            "chemicalRef": self._chemical_ref(identity),
            "summary": {
                "assayCount": len(summary_records),
                "activeAssayCount": active_assay_count,
                "targetCount": len(targets),
                "referenceAssaySet": "toxcast-tox21-summary",
            },
            "assays": assays,
            "targets": targets,
            "aopMappings": self._bioactivity_aop_mappings(aop_summary["mappings"]),
            "provenance": self._build_provenance(
                generated_by="assemble_comptox_evidence_pack",
                step_metadata=step_metadata,
                notes=[
                    "Bioactivity summary built from CompTox summary and AOP crosswalk endpoints."
                ],
            ),
            "rawSummaryRecords": summary_records,
        }

    def _build_aop_linkage_summary(
        self,
        *,
        dtxsid: str,
        identity: Dict[str, Any],
        provided_aeids: Optional[Sequence[str]] = None,
        summary_records: Optional[List[Dict[str, Any]]] = None,
        max_assays: int,
        step_metadata: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        records = (
            summary_records
            if summary_records is not None
            else self.bioactivity_resource.get_bioactivity_summary_by_dtxsid(dtxsid)
        )
        if summary_records is None:
            self._record_step(
                step_metadata,
                step_name="bioactivity:summary",
                resource=self.bioactivity_resource,
                tool_name="get_bioactivity_summary_by_dtxsid",
            )

        assay_refs, derived_aeids = self._assay_refs_from_summary(records, max_assays)
        aeids = [str(value) for value in provided_aeids or [] if value]
        aeids.extend(aeid for aeid in derived_aeids if aeid not in aeids)

        mappings: List[Dict[str, Any]] = []
        seen_keys = set()
        for aeid in aeids[:max_assays]:
            rows = self.bioactivity_resource.get_bioactivity_aop("toxcast-aeid", aeid)
            self._record_step(
                step_metadata,
                step_name=f"bioactivity:aop:{aeid}",
                resource=self.bioactivity_resource,
                tool_name="get_bioactivity_aop",
            )
            for row in rows:
                mapping = self._drop_nones(
                    {
                        "aopId": self._pick_string(
                            row, "aopId", "aop_id", "aop", "aopNumber"
                        )
                        or "unknown",
                        "aopTitle": self._pick_string(
                            row, "aopTitle", "aop_name", "title", "aop"
                        ),
                        "keyEventId": self._pick_string(
                            row, "keyEventId", "key_event_id", "eventNumber"
                        ),
                        "eventType": self._pick_string(
                            row, "eventType", "event_type", "type"
                        )
                        or "unknown",
                        "eventLabel": self._pick_string(
                            row, "eventLabel", "event_name", "event", "title"
                        )
                        or f"AOP mapping for {aeid}",
                        "relationship": self._pick_string(
                            row, "relationship", "mappingType"
                        )
                        or "linked_via_toxcast_aeid",
                        "evidenceDirection": self._pick_string(
                            row, "evidenceDirection", "direction"
                        )
                        or "supports",
                        "confidence": self._pick_number(
                            row, "confidence", "score", "mappingScore"
                        ),
                    }
                )
                key = (
                    mapping["aopId"],
                    mapping["eventType"],
                    mapping["eventLabel"],
                )
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                mappings.append(mapping)

        if not assay_refs and aeids:
            assay_refs = [
                self._drop_nones(
                    {"aeid": aeid, "assayName": f"AEID {aeid}", "targetName": None}
                )
                for aeid in aeids[:max_assays]
            ]

        score = 0.0
        if assay_refs:
            score += 0.2
        if mappings:
            score += min(0.7, 0.1 * len(mappings))
        score = min(score, 0.95)

        return {
            "chemicalRef": self._chemical_ref(identity),
            "lookupMode": "dtxsid",
            "mappings": mappings,
            "supportingAssays": assay_refs,
            "confidence": {
                "score": score,
                "band": self._confidence_band(score),
                "basis": "Derived from available assay endpoint links and CompTox AOP crosswalk coverage.",
            },
            "provenance": self._build_provenance(
                generated_by="build_aop_linkage_summary",
                step_metadata=step_metadata,
                notes=[
                    "CompTox-side linkage only; downstream mechanistic normalization belongs in aop-mcp."
                ],
            ),
        }

    def _build_pbpk_context_bundle(
        self,
        *,
        dtxsid: str,
        identity: Dict[str, Any],
        model_name: Optional[str],
        step_metadata: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        httk = self.exposure_resource.get_exposure_httk(dtxsid)
        self._record_step(
            step_metadata,
            step_name="exposure:httk",
            resource=self.exposure_resource,
            tool_name="get_exposure_httk",
        )
        adme_ivive = self.hazard_resource.get_hazard_adme_ivive(dtxsid)
        self._record_step(
            step_metadata,
            step_name="hazard:adme_ivive",
            resource=self.hazard_resource,
            tool_name="get_hazard_adme_ivive",
        )
        seem = self.exposure_resource.get_seem_general(dtxsid)
        self._record_step(
            step_metadata,
            step_name="exposure:seem",
            resource=self.exposure_resource,
            tool_name="get_seem_general",
        )
        cpdat = self.exposure_resource.search_cpdat("puc", [dtxsid])
        self._record_step(
            step_metadata,
            step_name="exposure:cpdat",
            resource=self.exposure_resource,
            tool_name="search_cpdat",
        )
        qsurs = self.exposure_resource.search_qsurs([dtxsid])
        self._record_step(
            step_metadata,
            step_name="exposure:qsurs",
            resource=self.exposure_resource,
            tool_name="search_qsurs",
        )

        model_cards = self._collect_model_card_refs(model_name, step_metadata)

        return {
            "chemicalIdentityRef": identity,
            "httkSlice": self._evidence_slice(
                httk,
                "get_exposure_httk",
                selected_metrics=self._select_metrics(
                    httk[0] if httk else {},
                    "fractionUnboundPlasma",
                    "intrinsicClearance",
                    "value",
                    "unit",
                    "parameter",
                ),
            ),
            "hazardAdmeIviveSlice": self._evidence_slice(
                adme_ivive,
                "get_hazard_adme_ivive",
                selected_metrics=self._select_metrics(
                    adme_ivive[0] if adme_ivive else {},
                    "intrinsicClearance",
                    "value",
                    "unit",
                    "parameter",
                    "assay",
                ),
            ),
            "exposureHints": self._build_exposure_hints(seem, cpdat, qsurs),
            "modelCardRefs": model_cards,
            "provenance": self._build_provenance(
                generated_by="build_pbpk_context_bundle",
                step_metadata=step_metadata,
                notes=[
                    "CompTox provides PBPK context only; execution and internal exposure outputs belong in pbpk-mcp."
                ],
            ),
            "handoffTarget": "pbpk-mcp",
        }

    def _collect_model_card_refs(
        self,
        model_name: Optional[str],
        step_metadata: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"limit": 25}
        if model_name:
            params["model_name"] = model_name

        payload = self.metadata_resource.execute_tool("metadata_get_model_card", params)
        self._record_step(
            step_metadata,
            step_name="metadata:model_cards",
            resource=self.metadata_resource,
            tool_name="metadata_get_model_card",
        )

        refs: List[Dict[str, Any]] = []
        for entry in payload.get("modelCards", []):
            card = entry.get("card", {})
            model_details = card.get("modelDetails", {})
            endpoint = (
                card.get("oecdValidationPrinciples", {})
                .get("definedEndpoint", {})
                .get("description")
            )
            model_type = str(model_details.get("modelType", "")).lower()
            text = " ".join(
                value
                for value in [model_details.get("name"), endpoint]
                if isinstance(value, str)
            ).lower()
            if not model_name and not any(
                token in text or token in model_type
                for token in ("pbpk", "pbtk", "httk", "kinetic", "toxicokinetic")
            ):
                continue
            refs.append(
                self._drop_nones(
                    {
                        "modelName": model_details.get("name", "Unknown model"),
                        "modelVersion": model_details.get("version", "unknown"),
                        "endpoint": endpoint,
                        "limitations": card.get("intendedUse", {}).get(
                            "limitations", []
                        ),
                        "warnings": card.get("intendedUse", {}).get("warnings", []),
                    }
                )
            )
        return refs

    def _build_exposure_hints(
        self,
        seem_records: Sequence[Dict[str, Any]],
        cpdat_records: Sequence[Dict[str, Any]],
        qsurs_records: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        hints: List[Dict[str, Any]] = []
        if seem_records:
            first = seem_records[0]
            value = self._pick_value(
                first, "medianExposure", "meanExposure", "exposure", "value"
            )
            if value is not None:
                hints.append(
                    self._drop_nones(
                        {
                            "hintType": "population_exposure",
                            "value": value,
                            "unit": self._pick_string(first, "unit"),
                            "source": "SEEM",
                            "context": "Screening exposure estimate from CompTox exposure resources.",
                        }
                    )
                )
        if cpdat_records:
            first = cpdat_records[0]
            label = self._pick_string(
                first,
                "productUseCategory",
                "puc",
                "functionalUse",
                "listPresence",
                "name",
            )
            if label:
                hints.append(
                    {
                        "hintType": "product_use_signal",
                        "value": label,
                        "source": "CPDat",
                    }
                )
        if qsurs_records:
            first = qsurs_records[0]
            label = self._pick_string(
                first, "useDescriptor", "functionalUse", "category", "name"
            )
            probability = self._pick_value(first, "probability", "prob", "value")
            if label:
                hints.append(
                    self._drop_nones(
                        {
                            "hintType": "functional_use_prediction",
                            "value": label,
                            "source": "QSURS",
                            "context": (
                                f"probability={probability}"
                                if probability is not None
                                else None
                            ),
                        }
                    )
                )
        return hints

    def _bioactivity_assays_from_summary(
        self, records: Sequence[Dict[str, Any]], max_assays: int
    ) -> List[Dict[str, Any]]:
        assays: List[Dict[str, Any]] = []
        seen = set()
        for row in records:
            aeid = self._pick_string(row, "aeid", "AEID")
            if not aeid or aeid in seen:
                continue
            assays.append(
                self._drop_nones(
                    {
                        "aeid": aeid,
                        "assayName": self._pick_string(
                            row, "assayName", "assay_name", "assay"
                        )
                        or f"AEID {aeid}",
                        "assayComponent": self._pick_string(
                            row, "assayComponent", "component", "assayComponentName"
                        ),
                        "activityDirection": self._pick_string(
                            row, "activityDirection", "direction", "responseDirection"
                        ),
                        "activityValue": self._pick_value(
                            row, "ac50", "activityValue", "value", "potency"
                        ),
                        "unit": self._pick_string(row, "unit"),
                        "hitCall": self._coerce_hit_call(
                            self._pick_value(row, "hitcall", "hitCall")
                        ),
                    }
                )
            )
            seen.add(aeid)
            if len(assays) >= max_assays:
                break
        return assays

    def _assay_refs_from_summary(
        self, records: Sequence[Dict[str, Any]], max_assays: int
    ) -> tuple[List[Dict[str, Any]], List[str]]:
        refs: List[Dict[str, Any]] = []
        aeids: List[str] = []
        seen = set()
        for row in records:
            aeid = self._pick_string(row, "aeid", "AEID")
            if not aeid or aeid in seen:
                continue
            refs.append(
                self._drop_nones(
                    {
                        "aeid": aeid,
                        "assayName": self._pick_string(
                            row, "assayName", "assay_name", "assay"
                        )
                        or f"AEID {aeid}",
                        "targetName": self._pick_string(
                            row, "targetName", "geneSymbol", "target"
                        ),
                    }
                )
            )
            aeids.append(aeid)
            seen.add(aeid)
            if len(refs) >= max_assays:
                break
        return refs, aeids

    def _target_refs_from_summary(
        self, records: Sequence[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        targets: Dict[str, Dict[str, Any]] = {}
        for row in records:
            target_name = self._pick_string(
                row, "targetName", "geneSymbol", "target", "gene"
            )
            if not target_name:
                continue
            gene_symbol = self._pick_string(row, "geneSymbol", "gene")
            key = gene_symbol or target_name
            if key not in targets:
                targets[key] = self._drop_nones(
                    {
                        "targetName": target_name,
                        "geneSymbol": gene_symbol,
                        "targetFamily": self._pick_string(
                            row, "targetFamily", "family"
                        ),
                        "assayCount": 0,
                    }
                )
            targets[key]["assayCount"] += 1
        return list(targets.values())

    def _bioactivity_aop_mappings(
        self, mappings: Sequence[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        return [
            self._drop_nones(
                {
                    "aopId": mapping["aopId"],
                    "aopTitle": mapping.get("aopTitle"),
                    "eventType": mapping["eventType"],
                    "eventLabel": mapping["eventLabel"],
                    "confidence": mapping.get("confidence"),
                }
            )
            for mapping in mappings
        ]

    def _chemical_ref(self, identity: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "dtxsid": identity["dtxsid"],
            "preferredName": identity["preferredName"],
            "casrn": identity.get("casrn"),
        }

    def _evidence_slice(
        self,
        records: Sequence[Dict[str, Any]],
        source_tool: str,
        *,
        selected_metrics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "recordCount": len(records),
            "records": list(records),
            "sourceTool": source_tool,
            "retrievedAt": self._timestamp(),
        }
        if selected_metrics:
            payload["selectedMetrics"] = selected_metrics
        return payload

    def _build_provenance(
        self,
        *,
        generated_by: str,
        step_metadata: Dict[str, Dict[str, Any]],
        notes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        sources = []
        for step_name, info in step_metadata.items():
            sources.append(
                {
                    "name": f"{info.get('resource', step_name)} via {info.get('tool', step_name)}",
                    "toolName": info.get("tool"),
                    "url": self._source_url_for_resource(info.get("resource")),
                    "retrievedAt": info.get("capturedAt", self._timestamp()),
                    "citation": f"CompTox MCP resource {info.get('resource', step_name)}",
                }
            )
        return {
            "sourceMcp": "epacomp-tox-mcp",
            "generatedAt": self._timestamp(),
            "generatedBy": generated_by,
            "traceId": f"{generated_by}-{self._timestamp()}",
            "sources": sources or [self._default_source_record()],
            "notes": notes or [],
        }

    def _annotate_public_payload(
        self,
        payload: Dict[str, Any],
        *,
        identity_resolution: Optional[Dict[str, Any]],
        source_tools: Sequence[str],
        known_data_gaps: Sequence[str],
    ) -> Dict[str, Any]:
        annotated = dict(payload)
        limitations = self._limitations_for_payload(
            identity_resolution=identity_resolution,
            known_data_gaps=known_data_gaps,
            payload=annotated,
        )
        annotated["knownDataGaps"] = list(known_data_gaps)
        annotated["limitations"] = limitations
        annotated["generatedFromTools"] = list(source_tools)
        annotated["provenanceSummary"] = self._provenance_summary_for_payload(
            payload=annotated,
            source_tools=source_tools,
        )
        if identity_resolution:
            annotated["identityResolution"] = identity_resolution
        return annotated

    def _source_tools_from_steps(
        self, step_metadata: Dict[str, Dict[str, Any]]
    ) -> List[str]:
        return sorted(
            {
                info.get("tool")
                for info in step_metadata.values()
                if isinstance(info, dict) and info.get("tool")
            }
        )

    def _known_data_gaps_for_pack(
        self,
        *,
        hazard_summary: Optional[Dict[str, Any]],
        exposure_summary: Optional[Dict[str, Any]],
        bioactivity_summary: Optional[Dict[str, Any]],
        aop_summary: Optional[Dict[str, Any]],
        pbpk_bundle: Optional[Dict[str, Any]],
    ) -> List[str]:
        gaps: List[str] = []
        if hazard_summary:
            for dataset in hazard_summary.get("datasets", []):
                if dataset.get("recordCount", 0) == 0:
                    gaps.append(f"hazard:{dataset.get('dataset', 'unknown')}")
        if exposure_summary:
            for key in ("cpdat", "seem", "httk", "mmdb", "qsurs"):
                if exposure_summary.get(key, {}).get("recordCount", 0) == 0:
                    gaps.append(f"exposure:{key}")
        if (
            bioactivity_summary
            and bioactivity_summary.get("summary", {}).get("assayCount", 0) == 0
        ):
            gaps.append("bioactivity:summary")
        gaps.extend(self._known_data_gaps_for_aop(aop_summary))
        gaps.extend(self._known_data_gaps_for_pbpk(pbpk_bundle))
        return sorted(dict.fromkeys(gaps))

    def _known_data_gaps_for_aop(self, payload: Optional[Dict[str, Any]]) -> List[str]:
        if not payload:
            return []
        gaps: List[str] = []
        if not payload.get("supportingAssays"):
            gaps.append("bioactivity:assays")
        if not payload.get("mappings"):
            gaps.append("bioactivity:aop")
        return gaps

    def _known_data_gaps_for_pbpk(self, payload: Optional[Dict[str, Any]]) -> List[str]:
        if not payload:
            return []
        gaps: List[str] = []
        if payload.get("httkSlice", {}).get("recordCount", 0) == 0:
            gaps.append("exposure:httk")
        if payload.get("hazardAdmeIviveSlice", {}).get("recordCount", 0) == 0:
            gaps.append("hazard:adme_ivive")
        if not payload.get("modelCardRefs"):
            gaps.append("metadata:model_cards")
        if not payload.get("exposureHints"):
            gaps.append("exposure:hints")
        return gaps

    def _limitations_for_payload(
        self,
        *,
        identity_resolution: Optional[Dict[str, Any]],
        known_data_gaps: Sequence[str],
        payload: Dict[str, Any],
    ) -> List[str]:
        limitations: List[str] = []
        if identity_resolution and identity_resolution.get("searchModeUsed") not in (
            None,
            "equals",
        ):
            limitations.append(
                "Identity resolution required a fallback search mode; confirm manually before downstream use."
            )
        for gap in known_data_gaps:
            limitations.append(f"Missing or empty evidence slice: {gap}.")

        for model_ref in payload.get("modelCardRefs", []):
            for field_name in ("limitations", "warnings"):
                for entry in model_ref.get(field_name, []):
                    if isinstance(entry, str):
                        limitations.append(
                            f"{model_ref.get('modelName', 'Model card')}: {entry}"
                        )

        provenance = payload.get("provenance") or payload.get("audit") or {}
        for note in provenance.get("notes", []):
            if isinstance(note, str) and note not in limitations:
                limitations.append(note)
        return limitations

    def _provenance_summary_for_payload(
        self,
        *,
        payload: Dict[str, Any],
        source_tools: Sequence[str],
    ) -> Dict[str, Any]:
        provenance = payload.get("provenance") or payload.get("audit") or {}
        sources = provenance.get("sources", [])
        return {
            "generatedBy": provenance.get("generatedBy")
            or payload.get("audit", {}).get("generatedBy"),
            "generatedAt": provenance.get("generatedAt")
            or payload.get("audit", {}).get("generatedAt"),
            "sourceCount": len(sources) if isinstance(sources, list) else 0,
            "sourceTools": list(source_tools),
            "noteCount": (
                len(provenance.get("notes", []))
                if isinstance(provenance.get("notes"), list)
                else 0
            ),
        }

    def _record_step(
        self,
        step_metadata: Dict[str, Dict[str, Any]],
        *,
        step_name: str,
        resource: BaseResource,
        tool_name: str,
    ) -> None:
        metadata = {}
        if hasattr(resource, "get_last_metadata"):
            metadata = resource.get_last_metadata() or {}
        step_metadata[step_name] = {
            "resource": resource.name,
            "tool": tool_name,
            "metadata": metadata,
            "capturedAt": self._timestamp(),
        }

    @staticmethod
    def _ensure_string_list(value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str)]

    @staticmethod
    def _pick_value(payload: Dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in payload and payload[key] is not None:
                return payload[key]
        return None

    @classmethod
    def _pick_string(cls, payload: Dict[str, Any], *keys: str) -> Optional[str]:
        value = cls._pick_value(payload, *keys)
        if value is None:
            return None
        return str(value)

    @classmethod
    def _pick_number(cls, payload: Dict[str, Any], *keys: str) -> Optional[float]:
        value = cls._pick_value(payload, *keys)
        if isinstance(value, (int, float)):
            return float(value)
        return None

    @staticmethod
    def _coerce_hit_call(value: Any) -> Optional[bool]:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "y"}:
                return True
            if normalized in {"false", "0", "no", "n"}:
                return False
        return None

    @staticmethod
    def _confidence_band(score: float) -> str:
        if score >= 0.75:
            return "high"
        if score >= 0.4:
            return "moderate"
        if score > 0:
            return "low"
        return "none"

    @staticmethod
    def _coverage_for_linkage(summary: Optional[Dict[str, Any]]) -> str:
        if not summary:
            return "none"
        if summary.get("mappings"):
            return "linked"
        if summary.get("supportingAssays"):
            return "summary"
        return "none"

    @staticmethod
    def _select_metrics(payload: Dict[str, Any], *keys: str) -> Dict[str, Any]:
        return {
            key: payload[key]
            for key in keys
            if key in payload and payload[key] is not None
        }

    @staticmethod
    def _drop_nones(payload: Dict[str, Any]) -> Dict[str, Any]:
        return {key: value for key, value in payload.items() if value is not None}

    @staticmethod
    def _source_url_for_resource(resource_name: Optional[str]) -> str:
        if resource_name == "metadata":
            return "https://github.com/ToxMCP/comptox-mcp/tree/main/metadata"
        return "https://comptox.epa.gov/ctx-api"

    @classmethod
    def _default_source_record(cls) -> Dict[str, Any]:
        return {
            "name": "EPA CompTox MCP",
            "toolName": "interop",
            "url": "https://github.com/ToxMCP/comptox-mcp",
            "retrievedAt": cls._timestamp(),
            "citation": "CompTox MCP interop resource",
        }

    @staticmethod
    def _timestamp() -> str:
        return (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
