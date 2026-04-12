from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from ctxpy import CtxApiError
from epacomp_tox.resources.bioactivity import BioactivityResource
from epacomp_tox.resources.cheminformatics import CheminformaticsResource
from epacomp_tox.resources.exposure import ExposureResource
from epacomp_tox.resources.hazard import HazardResource

from .models import CtxDataBundle, MetadataTrace
from .utils import sanitize_metadata


class CtxDataAssemblyError(RuntimeError):
    """Raised when CTX data retrieval fails."""


class CtxDataAssembler:
    """Fetch and cache CTX datasets required before GenRA predictive calls."""

    SCENARIO_OVERRIDES = {
        "acute_toxicity": {
            "hazard": ["all", "human", "eco"],
            "exposure": ["httk"],
        },
        "exposure_prioritization": {
            "hazard": ["all"],
            "exposure": ["pathways", "seem"],
            "cpdat": ["fc", "puc"],
        },
        "genra_read_across": {
            "hazard": ["all"],
            "exposure": ["httk", "qsurs"],
            "cpdat": ["fc"],
            "cheminformatics": True,
            "mechanistic_context": True,
        },
    }

    def __init__(
        self,
        *,
        hazard_resource: HazardResource,
        exposure_resource: ExposureResource,
        cheminformatics_resource: Optional[CheminformaticsResource] = None,
        bioactivity_resource: Optional[BioactivityResource] = None,
        hazard_data_types: Sequence[str] = ("all",),
        exposure_datasets: Sequence[str] = ("httk",),
        cpdat_vocabularies: Sequence[str] = ("fc",),
        include_toxprints: bool = False,
        include_mechanistic_context: bool = False,
        mechanistic_max_assays: int = 12,
        cache_ttl: int = 900,
        time_fn: Callable[[], float] = time.time,
    ) -> None:
        self.hazard_resource = hazard_resource
        self.exposure_resource = exposure_resource
        self.cheminformatics_resource = cheminformatics_resource
        self.bioactivity_resource = bioactivity_resource
        self.hazard_data_types = tuple(dict.fromkeys(hazard_data_types))
        self.exposure_datasets = tuple(dict.fromkeys(exposure_datasets))
        self.cpdat_vocabularies = tuple(dict.fromkeys(cpdat_vocabularies))
        self.include_toxprints = include_toxprints
        self.include_mechanistic_context = include_mechanistic_context
        self.mechanistic_max_assays = max(1, mechanistic_max_assays)
        self.cache_ttl = max(0, cache_ttl)
        self._time_fn = time_fn
        self._cache: Dict[
            Tuple[
                str,
                Tuple[str, ...],
                Tuple[str, ...],
                Tuple[str, ...],
                bool,
                bool,
                int,
            ],
            Tuple[float, CtxDataBundle],
        ] = {}
        self._mechanistic_cache: Dict[Tuple[str, int], Tuple[float, Dict[str, Any]]] = (
            {}
        )

    def assemble(
        self,
        dtxsid: str,
        *,
        scenarios: Optional[Sequence[str]] = None,
        include_cheminformatics: Optional[bool] = None,
        hazard_summary: bool = True,
    ) -> CtxDataBundle:
        """Gather hazard/exposure datasets (with caching) for the orchestrator workflow."""
        normalized_sid = (dtxsid or "").strip().upper()
        if not normalized_sid:
            raise CtxDataAssemblyError("DTXSID is required for CTX data assembly.")

        scenario_list = sorted(
            {
                scenario.strip().lower()
                for scenario in scenarios or []
                if isinstance(scenario, str) and scenario.strip()
            }
        )

        hazard_types = set(self.hazard_data_types)
        exposure_types = set(self.exposure_datasets)
        cpdat_vocab = set(self.cpdat_vocabularies)
        include_toxprints = (
            self.include_toxprints
            if include_cheminformatics is None
            else include_cheminformatics
        )
        include_mechanistic_context = self.include_mechanistic_context

        for scenario in scenario_list:
            overrides = self.SCENARIO_OVERRIDES.get(scenario)
            if not overrides:
                continue
            hazard_types.update(overrides.get("hazard", []))
            exposure_types.update(overrides.get("exposure", []))
            cpdat_vocab.update(overrides.get("cpdat", []))
            if overrides.get("cheminformatics"):
                include_toxprints = True
            if overrides.get("mechanistic_context"):
                include_mechanistic_context = True

        # Stable cache key covering config and request
        cache_key = (
            normalized_sid,
            tuple(sorted(hazard_types)),
            tuple(sorted(exposure_types)),
            tuple(sorted(cpdat_vocab)),
            bool(include_toxprints),
            bool(include_mechanistic_context),
            int(self.mechanistic_max_assays),
        )
        now = self._time_fn()
        cached = self._cache.get(cache_key)
        if cached and (self.cache_ttl == 0 or now - cached[0] <= self.cache_ttl):
            return cached[1].model_copy(update={"cache_hit": True})

        trace: List[MetadataTrace] = []
        data_gaps: List[str] = []
        hazard_data: Dict[str, List[Dict[str, Any]]] = {}
        exposure_data: Dict[str, List[Dict[str, Any]]] = {}
        cheminformatics_data: Dict[str, Any] = {}
        mechanistic_context: Dict[str, Any] = {}

        # Hazard datasets ---------------------------------------------------
        for hazard_type in sorted(hazard_types):
            try:
                payload = self.hazard_resource.search_hazard(
                    data_type=hazard_type,
                    dtxsid=normalized_sid,
                    summary=hazard_summary,
                )
            except CtxApiError as exc:
                trace.append(
                    self._metadata_trace(self.hazard_resource, f"hazard:{hazard_type}")
                )
                raise CtxDataAssemblyError(
                    f"Failed to fetch hazard dataset '{hazard_type}' for {normalized_sid}: {exc}"
                ) from exc
            hazard_data[hazard_type] = payload
            if not payload:
                data_gaps.append(f"hazard:{hazard_type}")
            trace.append(
                self._metadata_trace(self.hazard_resource, f"hazard:{hazard_type}")
            )

        # Exposure datasets -------------------------------------------------
        for exposure_type in sorted(exposure_types):
            step_name = f"exposure:{exposure_type}"
            try:
                payload = self._fetch_exposure_dataset(exposure_type, normalized_sid)
            except CtxApiError as exc:
                trace.append(self._metadata_trace(self.exposure_resource, step_name))
                raise CtxDataAssemblyError(
                    f"Failed to fetch exposure dataset '{exposure_type}' for {normalized_sid}: {exc}"
                ) from exc
            exposure_data[exposure_type] = payload
            if not payload:
                data_gaps.append(step_name)
            trace.append(self._metadata_trace(self.exposure_resource, step_name))

        for vocab in sorted(cpdat_vocab):
            step_name = f"exposure:cpdat:{vocab}"
            try:
                payload = self.exposure_resource.search_cpdat(
                    vocab_name=vocab,
                    dtxsids=[normalized_sid],
                )
            except CtxApiError as exc:
                trace.append(self._metadata_trace(self.exposure_resource, step_name))
                raise CtxDataAssemblyError(
                    f"Failed to fetch CPDat vocabulary '{vocab}' for {normalized_sid}: {exc}"
                ) from exc
            exposure_data[f"cpdat:{vocab}"] = payload
            if not payload:
                data_gaps.append(step_name)
            trace.append(self._metadata_trace(self.exposure_resource, step_name))

        # Cheminformatics ---------------------------------------------------
        if include_toxprints:
            if not self.cheminformatics_resource:
                data_gaps.append("cheminformatics:toxprints")
            else:
                step_name = "cheminformatics:toxprints"
                try:
                    payload = self.cheminformatics_resource.search_toxprints(
                        chemical=normalized_sid
                    )
                except CtxApiError as exc:
                    trace.append(
                        self._metadata_trace(self.cheminformatics_resource, step_name)
                    )
                    raise CtxDataAssemblyError(
                        f"Failed to fetch toxprints for {normalized_sid}: {exc}"
                    ) from exc
                cheminformatics_data["toxprints"] = payload
                if not payload:
                    data_gaps.append(step_name)
                trace.append(
                    self._metadata_trace(self.cheminformatics_resource, step_name)
                )

        # Mechanistic context ------------------------------------------------
        if include_mechanistic_context:
            target_context = self._get_mechanistic_context_slice(
                normalized_sid,
                trace=trace,
                data_gaps=data_gaps,
            )
            if target_context:
                mechanistic_context["target"] = target_context

        bundle = CtxDataBundle(
            dtxsid=normalized_sid,
            scenarios=scenario_list,
            hazard=hazard_data,
            exposure=exposure_data,
            cheminformatics=cheminformatics_data,
            mechanistic_context=mechanistic_context,
            data_gaps=data_gaps,
            trace=trace,
        )
        if self.cache_ttl:
            self._cache[cache_key] = (now, bundle)
        return bundle

    # Internal helpers -----------------------------------------------------

    def _metadata_trace(self, resource: Optional[object], step: str) -> MetadataTrace:
        metadata = {}
        if resource and hasattr(resource, "get_last_metadata"):
            metadata = sanitize_metadata(resource.get_last_metadata())
        return MetadataTrace(step=step, metadata=metadata)

    def _fetch_exposure_dataset(
        self, dataset: str, dtxsid: str
    ) -> List[Dict[str, Any]]:
        dataset = dataset.lower()
        if dataset == "httk":
            return self.exposure_resource.search_httk(dtxsids=[dtxsid])
        if dataset == "qsurs":
            return self.exposure_resource.search_qsurs(dtxsids=[dtxsid])
        if dataset in ("pathways", "mmdb-single", "seem", "seem-demographic"):
            return self.exposure_resource.search_exposures(
                data_type=dataset,
                dtxsids=[dtxsid],
            )
        raise CtxDataAssemblyError(f"Unsupported exposure dataset '{dataset}'.")

    def get_mechanistic_context_slice(self, dtxsid: str) -> Dict[str, Any]:
        """Return cached mechanistic context for a chemical when bioactivity is configured."""
        normalized_sid = (dtxsid or "").strip().upper()
        if not normalized_sid:
            return {}
        return self._get_mechanistic_context_slice(normalized_sid)

    def _get_mechanistic_context_slice(
        self,
        dtxsid: str,
        *,
        trace: Optional[List[MetadataTrace]] = None,
        data_gaps: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        if not self.bioactivity_resource:
            if data_gaps is not None:
                self._append_data_gap(data_gaps, "bioactivity:summary")
                self._append_data_gap(data_gaps, "bioactivity:aop")
            return {}

        cache_key = (dtxsid, self.mechanistic_max_assays)
        now = self._time_fn()
        cached = self._mechanistic_cache.get(cache_key)
        if cached and (self.cache_ttl == 0 or now - cached[0] <= self.cache_ttl):
            return dict(cached[1])

        summary_records = self._fetch_bioactivity_summary(
            dtxsid,
            trace=trace,
            data_gaps=data_gaps,
        )
        aop_mappings = self._fetch_bioactivity_aop_mappings(
            summary_records,
            trace=trace,
            data_gaps=data_gaps,
        )
        slice_payload = self._drop_nones(
            {
                "dtxsid": dtxsid,
                "bioactivity_summary": summary_records,
                "aop_mappings": aop_mappings,
            }
        )
        self._mechanistic_cache[cache_key] = (now, slice_payload)
        return dict(slice_payload)

    def _fetch_bioactivity_summary(
        self,
        dtxsid: str,
        *,
        trace: Optional[List[MetadataTrace]],
        data_gaps: Optional[List[str]],
    ) -> List[Dict[str, Any]]:
        if not self.bioactivity_resource:
            return []
        records = self.bioactivity_resource.get_bioactivity_summary_by_dtxsid(dtxsid)
        if trace is not None:
            trace.append(
                self._metadata_trace(self.bioactivity_resource, "bioactivity:summary")
            )
        normalized = self._normalize_bioactivity_summary(records)
        if not normalized and data_gaps is not None:
            self._append_data_gap(data_gaps, "bioactivity:summary")
        return normalized

    def _fetch_bioactivity_aop_mappings(
        self,
        summary_records: Sequence[Dict[str, Any]],
        *,
        trace: Optional[List[MetadataTrace]],
        data_gaps: Optional[List[str]],
    ) -> List[Dict[str, Any]]:
        if not self.bioactivity_resource:
            return []
        aeids = self._extract_aeids(summary_records)
        if not aeids:
            return []

        mappings: List[Dict[str, Any]] = []
        seen = set()
        for aeid in aeids:
            rows = self.bioactivity_resource.get_bioactivity_aop("toxcast-aeid", aeid)
            if trace is not None:
                trace.append(
                    self._metadata_trace(
                        self.bioactivity_resource, f"bioactivity:aop:{aeid}"
                    )
                )
            for row in rows:
                mapping = self._drop_nones(
                    {
                        "aopId": self._pick_string(
                            row, "aopId", "aop_id", "aop", "aopNumber"
                        ),
                        "aopTitle": self._pick_string(
                            row, "aopTitle", "aop_name", "title", "aop"
                        ),
                        "eventType": self._pick_string(
                            row, "eventType", "event_type", "type"
                        ),
                        "eventLabel": self._pick_string(
                            row, "eventLabel", "event_name", "event", "title"
                        ),
                        "evidenceDirection": self._pick_string(
                            row, "evidenceDirection", "direction"
                        ),
                        "confidence": self._pick_number(
                            row, "confidence", "score", "mappingScore"
                        ),
                    }
                )
                if not mapping:
                    continue
                key = (
                    mapping.get("aopId"),
                    mapping.get("eventType"),
                    mapping.get("eventLabel"),
                )
                if key in seen:
                    continue
                seen.add(key)
                mappings.append(mapping)
        if not mappings and data_gaps is not None:
            self._append_data_gap(data_gaps, "bioactivity:aop")
        return mappings

    def _normalize_bioactivity_summary(
        self, records: Sequence[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        seen = set()
        for row in records:
            if not isinstance(row, dict):
                continue
            aeid = self._pick_string(row, "aeid", "AEID")
            key = aeid or str(len(normalized))
            if key in seen:
                continue
            normalized.append(
                self._drop_nones(
                    {
                        "aeid": aeid,
                        "assayName": self._pick_string(
                            row, "assayName", "assay_name", "assay"
                        ),
                        "assayComponent": self._pick_string(
                            row, "assayComponent", "component", "assayComponentName"
                        ),
                        "targetName": self._pick_string(
                            row, "targetName", "target", "geneSymbol", "gene"
                        ),
                        "geneSymbol": self._pick_string(row, "geneSymbol", "gene"),
                        "targetFamily": self._pick_string(
                            row, "targetFamily", "family"
                        ),
                        "activityDirection": self._pick_string(
                            row,
                            "activityDirection",
                            "direction",
                            "responseDirection",
                        ),
                        "ac50": self._pick_number(
                            row, "ac50", "activityValue", "value", "potency"
                        ),
                        "unit": self._pick_string(row, "unit"),
                        "hitcall": self._pick_value(row, "hitcall", "hitCall"),
                    }
                )
            )
            seen.add(key)
            if len(normalized) >= self.mechanistic_max_assays:
                break
        return normalized

    def _extract_aeids(self, records: Sequence[Dict[str, Any]]) -> List[str]:
        aeids: List[str] = []
        seen = set()
        for row in records:
            if not isinstance(row, dict):
                continue
            aeid = self._pick_string(row, "aeid", "AEID")
            if not aeid or aeid in seen:
                continue
            aeids.append(aeid)
            seen.add(aeid)
            if len(aeids) >= self.mechanistic_max_assays:
                break
        return aeids

    def _append_data_gap(self, data_gaps: List[str], value: str) -> None:
        if value not in data_gaps:
            data_gaps.append(value)

    def _pick_string(self, row: Dict[str, Any], *keys: str) -> Optional[str]:
        for key in keys:
            candidate = row.get(key)
            if candidate is None:
                continue
            text = str(candidate).strip()
            if text:
                return text
        return None

    def _pick_number(self, row: Dict[str, Any], *keys: str) -> Optional[float]:
        for key in keys:
            candidate = row.get(key)
            if isinstance(candidate, bool):
                continue
            if isinstance(candidate, (int, float)):
                return float(candidate)
            try:
                if candidate is not None and str(candidate).strip():
                    return float(candidate)
            except (TypeError, ValueError):
                continue
        return None

    def _pick_value(self, row: Dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in row:
                return row.get(key)
        return None

    def _drop_nones(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {key: value for key, value in payload.items() if value is not None}
