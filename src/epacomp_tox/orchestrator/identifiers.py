from __future__ import annotations

import re
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from ctxpy import CtxApiError
from epacomp_tox.resources.chemical import ChemicalResource

from .models import IdentifierResolution, MetadataTrace
from .utils import sanitize_metadata


class IdentifierResolutionError(RuntimeError):
    """Raised when chemical identifier normalization fails."""


class IdentifierResolver:
    """Resolve user-supplied identifiers into canonical DTXSID records."""

    _DTXSID_RE = re.compile(r"^DTXSID\d{7}$", re.IGNORECASE)
    _TYPE_ALIASES = {
        "dtxsid": "dtxsid",
        "sid": "dtxsid",
        "dsstox": "dtxsid",
        "cas": "casrn",
        "casrn": "casrn",
        "name": "name",
        "preferred_name": "name",
        "inchikey": "inchikey",
        "inchi": "inchikey",
        "smiles": "smiles",
    }
    _SEARCH_ORDER = {
        "casrn": ("equals",),
        "name": ("equals", "starts-with", "contains"),
        "smiles": ("equals", "contains"),
        "inchikey": ("equals", "contains"),
    }

    def __init__(
        self,
        *,
        chemical_resource: ChemicalResource,
        cache_ttl: int = 900,
        detail_subset: str = "identifiers",
        time_fn: Callable[[], float] = time.time,
    ) -> None:
        self.chemical_resource = chemical_resource
        self.cache_ttl = max(0, cache_ttl)
        self.detail_subset = detail_subset
        self._time_fn = time_fn
        self._cache: Dict[Tuple[str, str], Tuple[float, IdentifierResolution]] = {}

    def resolve(
        self,
        identifier: str,
        identifier_type: Optional[str] = None,
        *,
        allow_fallback: bool = False,
    ) -> IdentifierResolution:
        """Resolve an identifier to a canonical DTXSID."""
        normalized_value = (identifier or "").strip()
        if not normalized_value:
            raise IdentifierResolutionError("Identifier value is required.")

        normalized_type = self._normalize_type(identifier_type, normalized_value)
        cache_key = (
            normalized_value.lower(),
            normalized_type,
            "fallback" if allow_fallback else "exact",
        )
        cached = self._cache.get(cache_key)
        now = self._time_fn()
        if cached and (self.cache_ttl == 0 or now - cached[0] <= self.cache_ttl):
            return cached[1].model_copy(update={"cache_hit": True})

        trace: List[MetadataTrace] = []
        warnings: List[str] = []
        matched_record: Dict[str, Any]
        detail_record: Dict[str, Any]
        resolution_status = "exact"
        search_mode_used = "equals"
        candidate_count = 1

        if normalized_type == "dtxsid":
            detail_record = self._fetch_details(
                identifier=normalized_value,
                trace=trace,
                stage="chemical.details",
            )
            matched_record = detail_record
        else:
            (
                matched_record,
                resolution_status,
                search_mode_used,
                candidate_count,
            ) = self._search_for_match(
                identifier=normalized_value,
                identifier_type=normalized_type,
                trace=trace,
                warnings=warnings,
                allow_fallback=allow_fallback,
            )
            detail_record = self._fetch_details(
                identifier=self._extract_dtxsid(matched_record),
                trace=trace,
                stage="chemical.details",
            )

        resolution = self._build_resolution(
            input_value=normalized_value,
            input_type=normalized_type,
            matched_record=matched_record,
            detail_record=detail_record,
            warnings=warnings,
            trace=trace,
            resolution_status=resolution_status,
            search_mode_used=search_mode_used,
            candidate_count=candidate_count,
        )
        if self.cache_ttl:
            self._cache[cache_key] = (now, resolution)
        return resolution

    # Internal helpers -----------------------------------------------------

    def _normalize_type(self, identifier_type: Optional[str], value: str) -> str:
        if identifier_type:
            key = identifier_type.strip().lower()
            if key not in self._TYPE_ALIASES:
                raise IdentifierResolutionError(
                    f"Unsupported identifier type '{identifier_type}'."
                )
            return self._TYPE_ALIASES[key]
        if self._DTXSID_RE.match(value):
            return "dtxsid"
        if value.count("-") == 2 and len(value.replace("-", "")) in (5, 6, 7, 8, 9):
            return "casrn"
        return "name"

    def _metadata_trace(self, stage: str) -> MetadataTrace:
        metadata = sanitize_metadata(self.chemical_resource.get_last_metadata())
        return MetadataTrace(step=stage, metadata=metadata)

    def _search_for_match(
        self,
        *,
        identifier: str,
        identifier_type: str,
        trace: List[MetadataTrace],
        warnings: List[str],
        allow_fallback: bool,
    ) -> tuple[Dict[str, Any], str, str, int]:
        search_modes = self._SEARCH_ORDER.get(identifier_type)
        if not search_modes:
            raise IdentifierResolutionError(
                f"Identifier type '{identifier_type}' is not searchable."
            )
        if not allow_fallback:
            search_modes = ("equals",)

        last_error: Optional[Exception] = None
        for mode in search_modes:
            try:
                results = self.chemical_resource.search_chemical(
                    query=identifier, search_type=mode
                )
                trace.append(self._metadata_trace(f"chemical.search:{mode}"))
            except CtxApiError as exc:
                last_error = exc
                trace.append(self._metadata_trace(f"chemical.search:{mode}"))
                continue
            except Exception as exc:  # pragma: no cover - defensive
                last_error = exc
                trace.append(self._metadata_trace(f"chemical.search:{mode}"))
                continue

            candidates = [record for record in results if isinstance(record, dict)]
            if not candidates:
                continue
            if len(candidates) > 1:
                raise IdentifierResolutionError(
                    f"Multiple matches found for '{identifier}' using search mode '{mode}'."
                )
            if mode != "equals":
                warnings.append(
                    f"Identifier '{identifier}' resolved using fallback search mode '{mode}'."
                )
            status = "fallback" if mode != "equals" else "exact"
            return candidates[0], status, mode, len(candidates)

        if last_error:
            raise IdentifierResolutionError(
                f"Failed to search for identifier '{identifier}': {last_error}"
            ) from last_error
        raise IdentifierResolutionError(
            f"No CTX record found for identifier '{identifier}'."
        )

    def _fetch_details(
        self,
        *,
        identifier: str,
        trace: List[MetadataTrace],
        stage: str,
    ) -> Dict[str, Any]:
        try:
            details = self.chemical_resource.get_chemical_details(
                identifier=identifier,
                id_type="dtxsid",
                subset=self.detail_subset,
            )
            trace.append(self._metadata_trace(stage))
            if not isinstance(details, dict):
                raise IdentifierResolutionError(
                    f"Unexpected payload when fetching details for '{identifier}'."
                )
            return details
        except CtxApiError as exc:
            trace.append(self._metadata_trace(stage))
            raise IdentifierResolutionError(
                f"CTX API error retrieving details for '{identifier}': {exc}"
            ) from exc
        except Exception as exc:  # pragma: no cover - defensive
            trace.append(self._metadata_trace(stage))
            raise IdentifierResolutionError(
                f"Failed to retrieve details for '{identifier}': {exc}"
            ) from exc

    def _extract_dtxsid(self, record: Dict[str, Any]) -> str:
        for key in ("dtxsid", "DTXSID", "dtxSid", "sid"):
            value = record.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        raise IdentifierResolutionError("Search result did not include a DTXSID.")

    def _build_resolution(
        self,
        *,
        input_value: str,
        input_type: str,
        matched_record: Dict[str, Any],
        detail_record: Dict[str, Any],
        warnings: List[str],
        trace: List[MetadataTrace],
        resolution_status: str,
        search_mode_used: str,
        candidate_count: int,
    ) -> IdentifierResolution:
        dtxsid = self._extract_dtxsid(detail_record or matched_record)
        synonyms = self._extract_synonyms(detail_record)
        casrn = self._extract_field(
            ("casrn", "cas", "CASRN", "casNumber"), detail_record, matched_record
        )
        preferred_name = self._extract_field(
            ("preferredName", "preferred_name", "name"),
            detail_record,
            matched_record,
        )

        return IdentifierResolution(
            input_identifier=input_value,
            input_type=input_type,
            dtxsid=dtxsid,
            resolution_status=resolution_status,
            search_mode_used=search_mode_used,
            candidate_count=candidate_count,
            matched_record=matched_record,
            detail_record=detail_record,
            preferred_name=preferred_name,
            casrn=casrn,
            synonyms=synonyms,
            warnings=warnings,
            trace=trace,
        )

    def _extract_synonyms(self, detail: Dict[str, Any]) -> List[str]:
        raw = (
            detail.get("synonyms") or detail.get("synonym") or detail.get("synonymList")
        )
        values: Iterable[Any]
        if isinstance(raw, (list, tuple)):
            values = raw
        elif isinstance(raw, str):
            values = [raw]
        elif isinstance(raw, dict):
            values = raw.values()
        else:
            values = []
        result = []
        for item in values:
            if not item:
                continue
            if isinstance(item, str):
                trimmed = item.strip()
                if trimmed and trimmed not in result:
                    result.append(trimmed)
        return result

    def _extract_field(
        self,
        keys: Tuple[str, ...],
        detail: Dict[str, Any],
        fallback: Dict[str, Any],
    ) -> Optional[str]:
        for source in (detail, fallback):
            for key in keys:
                value = source.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None
