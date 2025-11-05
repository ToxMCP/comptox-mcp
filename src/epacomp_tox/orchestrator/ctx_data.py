from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from ctxpy import CtxApiError

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
        },
    }

    def __init__(
        self,
        *,
        hazard_resource: HazardResource,
        exposure_resource: ExposureResource,
        cheminformatics_resource: Optional[CheminformaticsResource] = None,
        hazard_data_types: Sequence[str] = ("all",),
        exposure_datasets: Sequence[str] = ("httk",),
        cpdat_vocabularies: Sequence[str] = ("fc",),
        include_toxprints: bool = False,
        cache_ttl: int = 900,
        time_fn: Callable[[], float] = time.time,
    ) -> None:
        self.hazard_resource = hazard_resource
        self.exposure_resource = exposure_resource
        self.cheminformatics_resource = cheminformatics_resource
        self.hazard_data_types = tuple(dict.fromkeys(hazard_data_types))
        self.exposure_datasets = tuple(dict.fromkeys(exposure_datasets))
        self.cpdat_vocabularies = tuple(dict.fromkeys(cpdat_vocabularies))
        self.include_toxprints = include_toxprints
        self.cache_ttl = max(0, cache_ttl)
        self._time_fn = time_fn
        self._cache: Dict[
            Tuple[str, Tuple[str, ...], Tuple[str, ...], Tuple[str, ...], bool],
            Tuple[float, CtxDataBundle],
        ] = {}

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
            self.include_toxprints if include_cheminformatics is None else include_cheminformatics
        )

        for scenario in scenario_list:
            overrides = self.SCENARIO_OVERRIDES.get(scenario)
            if not overrides:
                continue
            hazard_types.update(overrides.get("hazard", []))
            exposure_types.update(overrides.get("exposure", []))
            cpdat_vocab.update(overrides.get("cpdat", []))
            if overrides.get("cheminformatics"):
                include_toxprints = True

        # Stable cache key covering config and request
        cache_key = (
            normalized_sid,
            tuple(sorted(hazard_types)),
            tuple(sorted(exposure_types)),
            tuple(sorted(cpdat_vocab)),
            bool(include_toxprints),
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

        # Hazard datasets ---------------------------------------------------
        for hazard_type in sorted(hazard_types):
            try:
                payload = self.hazard_resource.search_hazard(
                    data_type=hazard_type,
                    dtxsid=normalized_sid,
                    summary=hazard_summary,
                )
            except CtxApiError as exc:
                trace.append(self._metadata_trace(self.hazard_resource, f"hazard:{hazard_type}"))
                raise CtxDataAssemblyError(
                    f"Failed to fetch hazard dataset '{hazard_type}' for {normalized_sid}: {exc}"
                ) from exc
            hazard_data[hazard_type] = payload
            if not payload:
                data_gaps.append(f"hazard:{hazard_type}")
            trace.append(self._metadata_trace(self.hazard_resource, f"hazard:{hazard_type}"))

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
                    trace.append(self._metadata_trace(self.cheminformatics_resource, step_name))
                    raise CtxDataAssemblyError(
                        f"Failed to fetch toxprints for {normalized_sid}: {exc}"
                    ) from exc
                cheminformatics_data["toxprints"] = payload
                if not payload:
                    data_gaps.append(step_name)
                trace.append(self._metadata_trace(self.cheminformatics_resource, step_name))

        bundle = CtxDataBundle(
            dtxsid=normalized_sid,
            scenarios=scenario_list,
            hazard=hazard_data,
            exposure=exposure_data,
            cheminformatics=cheminformatics_data,
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

    def _fetch_exposure_dataset(self, dataset: str, dtxsid: str) -> List[Dict[str, Any]]:
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
