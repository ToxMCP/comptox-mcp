from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from ctxpy import CtxApiError
from epacomp_tox.contracts import schema_ref

from .base import BaseResource
from .bioactivity import BioactivityResource
from .chemical import ChemicalResource
from .exposure import ExposureResource


class PrioritizationResource(BaseResource):
    """Screening-style risk prioritization built from CompTox evidence slices."""

    def __init__(
        self,
        api_key: str,
        *,
        chemical_resource: Optional[ChemicalResource] = None,
        bioactivity_resource: Optional[BioactivityResource] = None,
        exposure_resource: Optional[ExposureResource] = None,
    ) -> None:
        super().__init__(api_key)
        self.chemical_resource = chemical_resource or ChemicalResource(api_key)
        self.bioactivity_resource = bioactivity_resource or BioactivityResource(api_key)
        self.exposure_resource = exposure_resource or ExposureResource(api_key)

    @property
    def name(self) -> str:
        return "prioritization"

    @property
    def description(self) -> str:
        return "Screening-style risk prioritization summaries combining AED, exposure, and use signals"

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "prioritize_risk_signals",
                "description": "Build a caveated screening-priority summary from bioactivity AED, SEEM exposure, HTTK context, MMDB, and CPDat use signals",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "dtxsid": {
                            "type": "string",
                            "description": "DSSTox substance identifier to prioritize.",
                        },
                        "identifier": {
                            "type": "string",
                            "description": "Optional non-DTXSID identifier to resolve before prioritization.",
                        },
                        "identifier_type": {
                            "type": "string",
                            "enum": ["dtxsid", "casrn", "name", "smiles", "inchikey"],
                            "description": "Optional identifier category when `identifier` is supplied.",
                        },
                        "allow_fallback": {
                            "type": "boolean",
                            "default": False,
                            "description": "Whether non-exact identifier fallback may be used after an exact search fails.",
                        },
                        "max_candidates": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 25,
                            "default": 5,
                            "description": "Maximum number of candidate records to return when identifier resolution is ambiguous.",
                        },
                    },
                    "anyOf": [
                        {"required": ["dtxsid"]},
                        {"required": ["identifier"]},
                    ],
                },
                "responseSchemaRef": schema_ref(
                    "risk", "prioritize_risk_signals.response.schema"
                ),
            }
        ]

    def execute_tool(
        self, tool_name: str, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        if tool_name != "prioritize_risk_signals":
            raise ValueError(f"Unknown tool: {tool_name}")
        return self.prioritize_risk_signals(
            dtxsid=parameters.get("dtxsid"),
            identifier=parameters.get("identifier"),
            identifier_type=parameters.get("identifier_type"),
            allow_fallback=bool(parameters.get("allow_fallback", False)),
            max_candidates=int(parameters.get("max_candidates", 5)),
        )

    def prioritize_risk_signals(
        self,
        *,
        dtxsid: Optional[str] = None,
        identifier: Optional[str] = None,
        identifier_type: Optional[str] = None,
        allow_fallback: bool = False,
        max_candidates: int = 5,
    ) -> Dict[str, Any]:
        step_metadata: Dict[str, Dict[str, Any]] = {}
        identity, resolution = self._resolve_requested_identity(
            dtxsid=dtxsid,
            identifier=identifier,
            identifier_type=identifier_type,
            allow_fallback=allow_fallback,
            max_candidates=max_candidates,
            step_metadata=step_metadata,
        )

        sid = identity["dtxsid"]
        aed_records = self._optional_records(
            fetcher=lambda: self.bioactivity_resource.get_bioactivity_aed(sid),
            step_metadata=step_metadata,
            step_name="bioactivity:aed",
            resource=self.bioactivity_resource,
            tool_name="get_bioactivity_aed",
        )
        seem_records = self._optional_records(
            fetcher=lambda: self.exposure_resource.get_seem_general(sid),
            step_metadata=step_metadata,
            step_name="exposure:seem",
            resource=self.exposure_resource,
            tool_name="get_seem_general",
        )
        httk_records = self._optional_records(
            fetcher=lambda: self.exposure_resource.get_exposure_httk(sid),
            step_metadata=step_metadata,
            step_name="exposure:httk",
            resource=self.exposure_resource,
            tool_name="get_exposure_httk",
        )
        mmdb_records = self._optional_records(
            fetcher=lambda: self.exposure_resource.get_exposure_mmdb_aggregate_by_dtxsid(
                sid
            ),
            step_metadata=step_metadata,
            step_name="exposure:mmdb",
            resource=self.exposure_resource,
            tool_name="get_exposure_mmdb_aggregate_by_dtxsid",
        )
        cpdat_records = self._optional_records(
            fetcher=lambda: self.exposure_resource.search_cpdat("puc", [sid]),
            step_metadata=step_metadata,
            step_name="exposure:cpdat",
            resource=self.exposure_resource,
            tool_name="search_cpdat",
        )

        selected_aed = self._select_aed_metric(aed_records)
        selected_exposure = self._select_exposure_metric(seem_records)
        prioritization = self._build_prioritization(
            selected_aed=selected_aed,
            selected_exposure=selected_exposure,
            cpdat_records=cpdat_records,
            mmdb_records=mmdb_records,
        )

        result = self._drop_nones(
            {
                "chemicalRef": self._chemical_ref(identity),
                "identityResolution": resolution,
                "hazardSignal": {
                    "recordCount": len(aed_records),
                    "sourceTool": "get_bioactivity_aed",
                    "selectedMetric": selected_aed,
                },
                "exposureSignal": {
                    "seem": self._evidence_slice(
                        seem_records,
                        "get_seem_general",
                        (
                            "medianExposure",
                            "meanExposure",
                            "exposure",
                            "value",
                            "unit",
                        ),
                    ),
                    "httk": self._evidence_slice(
                        httk_records,
                        "get_exposure_httk",
                        (
                            "fractionUnboundPlasma",
                            "intrinsicClearance",
                            "parameter",
                            "unit",
                        ),
                    ),
                    "mmdb": self._evidence_slice(
                        mmdb_records,
                        "get_exposure_mmdb_aggregate_by_dtxsid",
                        ("studyCount", "endpoint", "medium", "unit"),
                    ),
                    "cpdat": self._evidence_slice(
                        cpdat_records,
                        "search_cpdat",
                        (
                            "productUseCategory",
                            "name",
                            "kindName",
                            "functionalUse",
                            "useDescriptor",
                        ),
                    ),
                },
                "prioritization": prioritization,
                "knownDataGaps": self._known_data_gaps(
                    aed_records=aed_records,
                    seem_records=seem_records,
                    httk_records=httk_records,
                    mmdb_records=mmdb_records,
                    cpdat_records=cpdat_records,
                ),
                "limitations": self._limitations(prioritization),
                "generatedFromTools": self._generated_from_tools(step_metadata),
                "provenanceSummary": self._provenance_summary(
                    step_metadata=step_metadata,
                    resolution=resolution,
                ),
            }
        )

        timestamp = self._timestamp()
        self._last_metadata = {
            "steps": step_metadata,
            "generatedAt": timestamp,
            "requestId": f"prioritization-{sid}-{timestamp}",
        }
        return result

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
            if resolution.get("status") != "resolved" or not resolution.get(
                "canonicalDtxsid"
            ):
                raise ValueError(
                    f"Unable to resolve identifier '{normalized_identifier}': {resolution.get('status')}"
                )
            canonical_sid = str(resolution["canonicalDtxsid"]).upper()
            if normalized_sid and canonical_sid != normalized_sid:
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

    def _resolve_identity_record(
        self, dtxsid: str, step_metadata: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        record = self.chemical_resource.get_chemical_details(
            identifier=dtxsid,
            id_type="dtxsid",
            subset="default",
        )
        self._record_step(
            step_metadata,
            step_name="chemical:details",
            resource=self.chemical_resource,
            tool_name="get_chemical_details",
        )
        normalized = {
            "dtxsid": record.get("dtxsid", dtxsid),
            "preferredName": record.get("preferredName")
            or record.get("preferred_name")
            or record.get("name")
            or dtxsid,
            "casrn": record.get("casrn"),
        }
        return normalized

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

    def _select_aed_metric(
        self, records: Sequence[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        best_record: Optional[Dict[str, Any]] = None
        best_value: Optional[float] = None
        for record in records:
            value = self._coerce_number(
                self._pick_value(
                    record,
                    "aedVal",
                    "aed_value",
                    "administeredEquivalentDose",
                    "value",
                )
            )
            if value is None or value <= 0:
                continue
            if best_value is None or value < best_value:
                best_record = record
                best_value = value
        if best_record is None or best_value is None:
            return None
        return self._drop_nones(
            {
                "aeid": self._pick_value(best_record, "aeid"),
                "aedVal": best_value,
                "aedType": self._pick_value(best_record, "aedType", "type"),
                "aedValUnit": self._pick_value(
                    best_record, "aedValUnit", "unit", "valueUnit"
                ),
                "httkModel": self._pick_value(best_record, "httkModel"),
                "httkVersion": self._pick_value(best_record, "httkVersion"),
            }
        )

    def _select_exposure_metric(
        self, records: Sequence[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        best_record: Optional[Dict[str, Any]] = None
        best_value: Optional[float] = None
        for record in records:
            value = self._coerce_number(
                self._pick_value(
                    record, "medianExposure", "meanExposure", "exposure", "value"
                )
            )
            if value is None or value <= 0:
                continue
            if best_value is None or value > best_value:
                best_record = record
                best_value = value
        if best_record is None or best_value is None:
            return None
        return self._drop_nones(
            {
                "medianExposure": best_value,
                "unit": self._pick_value(best_record, "unit", "valueUnit"),
                "population": self._pick_value(best_record, "population"),
                "lifeStage": self._pick_value(best_record, "lifeStage"),
            }
        )

    def _build_prioritization(
        self,
        *,
        selected_aed: Optional[Dict[str, Any]],
        selected_exposure: Optional[Dict[str, Any]],
        cpdat_records: Sequence[Dict[str, Any]],
        mmdb_records: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        caveats: List[str] = [
            "Screening only; this output is not a regulatory risk determination."
        ]
        aed_value = self._coerce_number(
            self._pick_value(selected_aed or {}, "aedVal", "value")
        )
        exposure_value = self._coerce_number(
            self._pick_value(selected_exposure or {}, "medianExposure", "value")
        )
        hazard_unit = self._pick_value(selected_aed or {}, "aedValUnit", "unit")
        exposure_unit = self._pick_value(selected_exposure or {}, "unit", "valueUnit")

        margin_of_exposure: Optional[float] = None
        priority_band = "inconclusive"
        basis = (
            "Could not calculate a screening margin because either AED or exposure "
            "signals were missing or unit-incompatible."
        )

        if aed_value is None:
            caveats.append(
                "No usable AED value was available from the bioactivity resource."
            )
        if exposure_value is None:
            caveats.append("No usable general exposure value was available from SEEM.")

        units_compatible = (
            aed_value is not None
            and exposure_value is not None
            and self._normalize_unit(hazard_unit) == self._normalize_unit(exposure_unit)
        )

        if (
            aed_value is not None
            and exposure_value is not None
            and not units_compatible
        ):
            caveats.append(
                "AED and exposure units were not directly compatible, so the screening margin was not computed."
            )

        if units_compatible and exposure_value and exposure_value > 0:
            margin_of_exposure = round(aed_value / exposure_value, 3)
            basis = (
                "Calculated as the minimum available AED divided by the maximum "
                "available SEEM general exposure estimate when units matched."
            )
            if margin_of_exposure < 100:
                priority_band = "higher"
            elif margin_of_exposure < 1000:
                priority_band = "moderate"
            else:
                priority_band = "lower"

        supporting_signals: List[str] = []
        if cpdat_records:
            supporting_signals.append("CPDat product-use records were present.")
        if mmdb_records:
            supporting_signals.append(
                "MMDB aggregate biomonitoring records were present."
            )
        if not supporting_signals:
            supporting_signals.append(
                "No additional CPDat or MMDB signals were available to contextualize the screening margin."
            )

        return {
            "priorityBand": priority_band,
            "marginOfExposure": margin_of_exposure,
            "hazardPointOfDeparture": aed_value,
            "hazardUnit": hazard_unit,
            "exposureEstimate": exposure_value,
            "exposureUnit": exposure_unit,
            "signalDirection": "smaller_margin_means_higher_priority",
            "priorityHeuristic": {
                "higher": "margin < 100",
                "moderate": "100 <= margin < 1000",
                "lower": "margin >= 1000",
                "inconclusive": "core inputs missing or incompatible",
            },
            "basis": basis,
            "supportingSignals": supporting_signals,
            "caveats": caveats,
        }

    def _known_data_gaps(
        self,
        *,
        aed_records: Sequence[Dict[str, Any]],
        seem_records: Sequence[Dict[str, Any]],
        httk_records: Sequence[Dict[str, Any]],
        mmdb_records: Sequence[Dict[str, Any]],
        cpdat_records: Sequence[Dict[str, Any]],
    ) -> List[str]:
        gaps: List[str] = []
        if not aed_records:
            gaps.append("bioactivity:aed")
        if not seem_records:
            gaps.append("exposure:seem")
        if not httk_records:
            gaps.append("exposure:httk")
        if not mmdb_records:
            gaps.append("exposure:mmdb")
        if not cpdat_records:
            gaps.append("exposure:cpdat")
        return gaps

    def _limitations(self, prioritization: Dict[str, Any]) -> List[str]:
        limitations = [
            "This tool is intended for screening prioritization, not final risk characterization.",
            "The screening margin uses only the minimum available AED and the maximum available SEEM general exposure estimate.",
            "HTTK, MMDB, and CPDat slices are supporting context and are not folded directly into the margin calculation.",
        ]
        if prioritization.get("priorityBand") == "inconclusive":
            limitations.append(
                "When core quantitative inputs are missing or incompatible, the result remains intentionally inconclusive."
            )
        return limitations

    def _generated_from_tools(
        self, step_metadata: Dict[str, Dict[str, Any]]
    ) -> List[str]:
        return list(
            dict.fromkeys(
                info.get("tool")
                for info in step_metadata.values()
                if isinstance(info, dict) and info.get("tool")
            )
        )

    def _provenance_summary(
        self,
        *,
        step_metadata: Dict[str, Dict[str, Any]],
        resolution: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return {
            "generatedBy": "prioritize_risk_signals",
            "generatedAt": self._timestamp(),
            "sourceCount": len(step_metadata),
            "sourceTools": self._generated_from_tools(step_metadata),
            "identityMode": "resolved_identifier" if resolution else "dtxsid",
        }

    def _evidence_slice(
        self,
        records: Sequence[Dict[str, Any]],
        source_tool: str,
        selected_keys: Sequence[str],
    ) -> Dict[str, Any]:
        selected_metrics: Dict[str, Any] = {}
        if records:
            first = records[0]
            selected_metrics = self._drop_nones(
                {key: self._pick_value(first, key) for key in selected_keys}
            )
        return {
            "recordCount": len(records),
            "sourceTool": source_tool,
            "selectedMetrics": selected_metrics or None,
        }

    def _chemical_ref(self, identity: Dict[str, Any]) -> Dict[str, Any]:
        return self._drop_nones(
            {
                "dtxsid": identity.get("dtxsid"),
                "preferredName": identity.get("preferredName"),
                "casrn": identity.get("casrn"),
            }
        )

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
    def _pick_value(payload: Dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in payload and payload[key] is not None:
                return payload[key]
        return None

    @staticmethod
    def _coerce_number(value: Any) -> Optional[float]:
        if isinstance(value, (int, float)):
            return float(value)
        return None

    @staticmethod
    def _normalize_unit(value: Any) -> str:
        if not isinstance(value, str):
            return ""
        return value.strip().lower().replace(" ", "")

    @staticmethod
    def _drop_nones(payload: Dict[str, Any]) -> Dict[str, Any]:
        return {key: value for key, value in payload.items() if value is not None}

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()
