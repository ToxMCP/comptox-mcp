"""
Lightweight ctx-python shim for direct CTX API access.

This is a reduced implementation that covers the subset of functionality
required by the MCP migration work (chemical search/details and a few helpers).
It performs HTTPS requests against the CTX API using the provided API key.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

DEFAULT_BASE_URL = "https://comptox.epa.gov/ctx-api"

_RATE_LIMIT_HEADERS = (
    "x-ratelimit-limit",
    "x-ratelimit-remaining",
    "x-ratelimit-reset",
)


@dataclass
class RateLimitInfo:
    limit: Optional[int]
    remaining: Optional[int]
    reset: Optional[int]


class CtxApiError(RuntimeError):
    """Raised when the CTX API responds with an error or cannot be reached."""

    def __init__(
        self,
        status: Optional[int],
        message: str,
        *,
        detail: Any = None,
        request_id: Optional[str] = None,
        rate_limit: Optional[RateLimitInfo] = None,
        retry_after: Optional[float] = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.detail = detail
        self.request_id = request_id
        self.rate_limit = rate_limit
        self.retry_after = retry_after

    @property
    def retryable(self) -> bool:
        if self.status is None:
            return True
        if self.status == 429:
            return True
        return 500 <= self.status < 600


class _BaseCtxClient:
    def __init__(self, x_api_key: str, base_url: Optional[str] = None, timeout: float = 30.0):
        if not x_api_key:
            raise ValueError("x_api_key is required")
        env_base = (
            base_url
            or os.environ.get("ctx_api_host")
            or os.environ.get("CTX_API_BASE_URL")
            or DEFAULT_BASE_URL
        )
        self.base_url = env_base.rstrip("/")
        self.api_key = x_api_key
        self._default_batch_size = 200
        self._default_timeout = timeout
        self.last_metadata: Dict[str, Any] = {}

    def _extract_metadata(
        self, headers: Optional[Dict[str, Any]], *, status: Optional[int] = None
    ) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {"status": status}
        if headers:
            request_id = headers.get("x-request-id") or headers.get("x-correlation-id")
            if request_id:
                metadata["request_id"] = request_id

            values: Dict[str, Optional[int]] = {}
            for key in _RATE_LIMIT_HEADERS:
                raw = headers.get(key)
                if raw is None:
                    values[key] = None
                else:
                    try:
                        values[key] = int(raw)
                    except ValueError:
                        values[key] = None
            metadata["rate_limit"] = RateLimitInfo(
                limit=values.get("x-ratelimit-limit"),
                remaining=values.get("x-ratelimit-remaining"),
                reset=values.get("x-ratelimit-reset"),
            )

            retry_after = headers.get("retry-after")
            if retry_after is not None:
                try:
                    metadata["retry_after"] = float(retry_after)
                except ValueError:
                    metadata["retry_after"] = None
        return metadata

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        data: Any = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        # Use provided timeout, or fall back to instance default
        effective_timeout = timeout if timeout is not None else self._default_timeout
        url = f"{self.base_url}/{path.lstrip('/')}"
        if params:
            encoded_params = urllib.parse.urlencode(
                {
                    key: json.dumps(value) if isinstance(value, (list, dict)) else value
                    for key, value in params.items()
                    if value is not None
                },
                doseq=True,
            )
            if encoded_params:
                url = f"{url}?{encoded_params}"

        request_headers = {
            "x-api-key": self.api_key,
            "Accept": "application/json",
        }
        if headers:
            request_headers.update(headers)

        body: Optional[bytes] = None
        if data is not None:
            if isinstance(data, (dict, list)):
                body = json.dumps(data).encode("utf-8")
                request_headers.setdefault("Content-Type", "application/json")
            elif isinstance(data, (str, bytes)):
                body = data.encode("utf-8") if isinstance(data, str) else data
            else:
                raise TypeError("Unsupported payload type for ctx request")

        req = urllib.request.Request(url, data=body, headers=request_headers, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=effective_timeout) as response:
                metadata = self._extract_metadata(response.headers, status=response.status)
                self.last_metadata = metadata
                content = response.read()
                if not content:
                    return None
                try:
                    return json.loads(content.decode("utf-8"))
                except json.JSONDecodeError as exc:
                    raise CtxApiError(
                        response.status,
                        f"Failed to decode JSON payload from {url}",
                        detail=str(exc),
                        request_id=metadata.get("request_id"),
                        rate_limit=metadata.get("rate_limit"),
                        retry_after=metadata.get("retry_after"),
                    ) from exc
        except urllib.error.HTTPError as exc:
            metadata = self._extract_metadata(exc.headers, status=exc.code)
            error_body = exc.read()
            detail: Any
            try:
                detail = json.loads(error_body.decode("utf-8"))
            except Exception:
                detail = error_body.decode("utf-8", errors="ignore")
            self.last_metadata = metadata
            raise CtxApiError(
                exc.code,
                f"CTX API request failed: {exc.code} {exc.reason}",
                detail=detail,
                request_id=metadata.get("request_id"),
                rate_limit=metadata.get("rate_limit"),
                retry_after=metadata.get("retry_after"),
            ) from exc
        except urllib.error.URLError as exc:
            metadata = self._extract_metadata(None, status=None)
            self.last_metadata = metadata
            raise CtxApiError(
                None,
                f"CTX API request failed: {exc.reason}",
                detail=str(exc),
            ) from exc

    def get(self, suffix: str, *, params: Optional[Dict[str, Any]] = None) -> Any:
        if not suffix:
            raise ValueError("suffix is required")
        return self._request("GET", suffix, params=params)

    def post(
        self,
        suffix: str,
        payload: Any,
        *,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        if not suffix:
            raise ValueError("suffix is required")
        return self._request("POST", suffix, params=params, data=payload, headers=headers)

    def batch(
        self,
        suffix: str,
        word: Iterable[str],
        batch_size: int,
        bracketed: bool = False,
    ) -> List[Any]:
        values: List[str] = []
        seen = set()
        for item in word:
            if item is None:
                continue
            encoded = urllib.parse.quote(str(item), safe="")
            if encoded not in seen:
                seen.add(encoded)
                values.append(encoded)

        if not values:
            return []

        size = max(1, batch_size or self._default_batch_size)
        results: List[Any] = []
        for idx in range(0, len(values), size):
            chunk = values[idx : idx + size]
            if bracketed:
                payload = json.dumps(chunk)
                headers = {"Content-Type": "application/json"}
            else:
                payload = "\n".join(chunk)
                headers = {"Content-Type": "text/plain"}
            response = self.post(suffix, payload, headers=headers)
            if isinstance(response, list):
                results.extend(response)
            elif response is not None:
                results.append(response)
        return results


class Chemical(_BaseCtxClient):
    def search(self, by: str, word: Any, *, projection: Optional[str] = None) -> Any:
        norm = (by or "").strip().lower().replace("_", "-")
        if norm == "batch":
            if not isinstance(word, Iterable) or isinstance(word, str):
                raise ValueError("word must be an iterable of identifiers for batch search")
            return self.batch(
                suffix="chemical/search/equal/",
                word=word,
                batch_size=self._default_batch_size,
                bracketed=False,
            )

        if norm in ("equal", "equals"):
            path = f"chemical/search/equal/{urllib.parse.quote(str(word))}"
        elif norm in ("start-with", "starts-with", "startswith"):
            path = f"chemical/search/start-with/{urllib.parse.quote(str(word))}"
        elif norm in ("contain", "contains"):
            path = f"chemical/search/contain/{urllib.parse.quote(str(word))}"
        elif norm in ("by-exact-formula", "exact-formula", "formula"):
            path = f"chemical/search/by-exact-formula/{urllib.parse.quote(str(word))}"
        elif norm in ("by-msready-formula", "msready-formula"):
            path = f"chemical/search/by-msready-formula/{urllib.parse.quote(str(word))}"
        else:
            raise ValueError(f"Unsupported chemical search mode '{by}'")

        params = {"projection": projection} if projection else None
        return self.get(path, params=params)

    def details(self, by: str, word: Any, subset: Optional[str] = "default") -> Any:
        norm = (by or "").strip().lower()
        subset_key = str(subset or "default").strip().lower()
        projection_map = {
            "default": None,
            "all": "chemicaldetailall",
            "details": "chemicaldetailstandard",
            "standard": "chemicaldetailstandard",
            "identifiers": "chemicalidentifier",
            "identifier": "chemicalidentifier",
            "structures": "chemicalstructure",
            "structure": "chemicalstructure",
            "nta": "ntatoolkit",
            "ntatoolkit": "ntatoolkit",
        }

        if norm == "batch":
            if not isinstance(word, Iterable) or isinstance(word, str):
                raise ValueError("word must be an iterable of identifiers for batch detail lookup")
            return self.batch(
                suffix="chemical/detail/search/by-dtxsid/",
                word=word,
                batch_size=self._default_batch_size,
                bracketed=True,
            )

        if norm in ("dtxsid", "sid"):
            path = f"chemical/detail/search/by-dtxsid/{urllib.parse.quote(str(word))}"
        elif norm in ("dtxcid", "cid"):
            path = f"chemical/detail/search/by-dtxcid/{urllib.parse.quote(str(word))}"
        else:
            raise ValueError(f"Unsupported chemical details lookup '{by}'")

        projection = projection_map.get(subset_key, projection_map["default"])
        params = {"projection": projection} if projection else None
        return self.get(path, params=params)

    def msready(
        self,
        by: str,
        word: Optional[str] = None,
        start: Optional[float] = None,
        end: Optional[float] = None,
    ) -> Any:
        norm = (by or "").strip().lower()
        if norm == "dtxcid":
            if not word:
                raise ValueError("word is required for msready search by dtxcid")
            path = f"chemical/msready/search/by-dtxcid/{urllib.parse.quote(str(word))}"
            return self.get(path)
        if norm in ("formula", "by-formula"):
            if not word:
                raise ValueError("word is required for msready search by formula")
            path = f"chemical/msready/search/by-formula/{urllib.parse.quote(str(word))}"
            return self.get(path)
        if norm in ("mass", "mass-range"):
            if start is None or end is None:
                raise ValueError("start and end are required for msready mass search")
            path = f"chemical/msready/search/by-mass/{start}/{end}"
            return self.get(path)
        raise ValueError(f"Unsupported msready search mode '{by}'")

    def batch(
        self,
        suffix: str,
        word: Iterable[str],
        batch_size: int,
        bracketed: bool = False,
    ) -> Any:
        return super().batch(suffix, word, batch_size, bracketed)

    def fate_summary(self, dtxsid: str, prop_name: Optional[str] = None) -> Any:
        quoted = urllib.parse.quote(str(dtxsid))
        path = f"chemical/fate/summary/search/by-dtxsid/{quoted}"
        params = {"propertyName": prop_name} if prop_name else None
        return self.get(path, params=params)

    def fate_details(self, dtxsid: str) -> Any:
        quoted = urllib.parse.quote(str(dtxsid))
        # Assuming 'chemical/fate/search/by-dtxsid/{dtxsid}' returns details
        return self.get(f"chemical/fate/search/by-dtxsid/{quoted}")

    def extra_data_batch(self, identifiers: Iterable[str]) -> List[Any]:
        return self.batch("chemical/extra-data/batch", identifiers, self._default_batch_size, bracketed=True)

    def ghs_check_batch(self, source: str, identifiers: Iterable[str]) -> Any:
        # Assuming source is part of the path, or a query param. Placing it in path.
        quoted_source = urllib.parse.quote(str(source))
        return self.batch(f"chemical/ghs-check/batch/{quoted_source}", identifiers, self._default_batch_size, bracketed=True)

    def opsin_convert(self, name: str, output: str) -> Any:
        params = {"name": name, "output": output}
        return self.get("cheminformatics/opsin-convert", params=params)

    def indigo_convert(self, molfile: str, output: str) -> Any:
        # Assuming POST for molfile and direct path for output
        headers = {"Content-Type": "text/plain"}
        return self.post(f"cheminformatics/indigo-convert/{output}", molfile, headers=headers)
        
    def structure_file(self, identifier_type: str, identifier: str, file_format: str, image_format: Optional[str] = None) -> Any:
        quoted_identifier = urllib.parse.quote(str(identifier))
        path = f"chemical/structure-file/{identifier_type}/{quoted_identifier}/{file_format}"
        params = {"imageFormat": image_format} if image_format else None
        return self.get(path, params=params)




class Bioactivity(_BaseCtxClient):
    _SEARCH_MAP = {
        "equal": "bioactivity/search/equal/",
        "equals": "bioactivity/search/equal/",
        "starts-with": "bioactivity/search/start-with/",
        "start-with": "bioactivity/search/start-with/",
        "startswith": "bioactivity/search/start-with/",
        "contain": "bioactivity/search/contain/",
        "contains": "bioactivity/search/contain/",
    }

    def _encode(self, value: Any) -> str:
        return urllib.parse.quote(str(value))

    def _json_batch(self, suffix: str, identifiers: Iterable[str]) -> List[Any]:
        return super().batch(suffix, identifiers, self._default_batch_size, bracketed=True)

    def search(self, search_type: str, value: str) -> Any:
        norm = (search_type or "").strip().lower()
        suffix = self._SEARCH_MAP.get(norm)
        if not suffix:
            raise ValueError(f"Unsupported bioactivity search type '{search_type}'")
        return self._request("GET", f"{suffix}{self._encode(value)}") or []

    def models_by_dtxsid_and_name(self, dtxsid: str, model: str) -> Any:
        params = {"dtxsid": dtxsid, "model": model}
        return self._request("GET", "bioactivity/models/search/", params=params) or []

    def models_by_dtxsid(self, dtxsid: str) -> Any:
        return self._request(
            "GET",
            f"bioactivity/models/search/by-dtxsid/{self._encode(dtxsid)}",
        ) or []

    def data_summary_by_dtxsid(self, dtxsid: str) -> Any:
        return self._request(
            "GET",
            f"bioactivity/data/summary/search/by-dtxsid/{self._encode(dtxsid)}",
        ) or []

    def data_summary_by_aeid(self, aeid: str) -> Any:
        return self._request(
            "GET",
            f"bioactivity/data/summary/search/by-aeid/{self._encode(aeid)}",
        ) or []

    def data_summary_by_tissue(self, dtxsid: str, tissue: str) -> Any:
        params = {"dtxsid": dtxsid, "tissue": tissue}
        return self._request("GET", "bioactivity/data/summary/search/by-tissue/", params=params) or []

    def data_by_spid(self, spid: str) -> Any:
        return self._request(
            "GET",
            f"bioactivity/data/search/by-spid/{self._encode(spid)}",
        ) or []

    def data_by_m4id(self, m4id: str) -> Any:
        return self._request(
            "GET",
            f"bioactivity/data/search/by-m4id/{self._encode(m4id)}",
        ) or []

    def data_by_dtxsid(self, dtxsid: str, *, projection: Optional[str] = None) -> Any:
        params = {"projection": projection} if projection else None
        return self._request(
            "GET",
            f"bioactivity/data/search/by-dtxsid/{self._encode(dtxsid)}",
            params=params,
        ) or []

    def data_by_aeid(self, aeid: str, *, projection: Optional[str] = None) -> Any:
        params = {"projection": projection} if projection else None
        return self._request(
            "GET",
            f"bioactivity/data/search/by-aeid/{self._encode(aeid)}",
            params=params,
        ) or []

    def data_batch(self, identifier_type: str, identifiers: Iterable[str]) -> Any:
        norm = (identifier_type or "").strip().lower()
        suffix_map = {
            "spid": "bioactivity/data/search/by-spid/",
            "m4id": "bioactivity/data/search/by-m4id/",
            "dtxsid": "bioactivity/data/search/by-dtxsid/",
            "aeid": "bioactivity/data/search/by-aeid/",
        }
        suffix = suffix_map.get(norm)
        if not suffix:
            raise ValueError(f"Unsupported bioactivity identifier type '{identifier_type}'")
        return self._json_batch(suffix, identifiers)

    def aed_by_dtxsid(self, dtxsid: str) -> Any:
        return self._request(
            "GET",
            f"bioactivity/data/aed/search/by-dtxsid/{self._encode(dtxsid)}",
        ) or []

    def aed_batch(self, dtxsids: Iterable[str]) -> Any:
        return self._json_batch("bioactivity/data/aed/search/by-dtxsid", dtxsids)

    def assays_all(self) -> Any:
        return self._request("GET", "bioactivity/assay/") or []

    def assay_by_aeid(self, aeid: str) -> Any:
        return self._request(
            "GET",
            f"bioactivity/assay/search/by-aeid/{self._encode(aeid)}",
        ) or []

    def assay_single_conc_by_aeid(self, aeid: str) -> Any:
        return self._request(
            "GET",
            f"bioactivity/assay/single-conc/search/by-aeid/{self._encode(aeid)}",
        ) or []

    def assay_by_gene(self, gene_symbol: str) -> Any:
        return self._request(
            "GET",
            f"bioactivity/assay/search/by-gene/{self._encode(gene_symbol)}",
        ) or []

    def assay_batch(self, aeids: Iterable[str]) -> Any:
        return self._json_batch("bioactivity/assay/search/by-aeid/", aeids)

    def assay_count(self) -> Any:
        return self._request("GET", "bioactivity/assay/count") or {}

    def assay_chemicals_by_aeid(self, aeid: str) -> Any:
        return self._request(
            "GET",
            f"bioactivity/assay/chemicals/search/by-aeid/{self._encode(aeid)}",
        ) or []

    def aop_by_toxcast_aeid(self, toxcast_aeid: str) -> Any:
        return self._request(
            "GET",
            f"bioactivity/aop/search/by-toxcast-aeid/{self._encode(toxcast_aeid)}",
        ) or []

    def aop_by_event_number(self, event_number: str) -> Any:
        return self._request(
            "GET",
            f"bioactivity/aop/search/by-event-number/{self._encode(event_number)}",
        ) or []

    def aop_by_entrez_gene(self, entrez_gene_id: str) -> Any:
        return self._request(
            "GET",
            f"bioactivity/aop/search/by-entrez-gene-id/{self._encode(entrez_gene_id)}",
        ) or []

    def analytical_qc_by_dtxsid(self, dtxsid: str) -> Any:
        return self._request(
            "GET",
            f"bioactivity/analyticalqc/search/by-dtxsid/{self._encode(dtxsid)}",
        ) or []


class Hazard(_BaseCtxClient):
    _HUMAN_TAGS = ("human", "human health")
    _ECO_TAGS = ("eco", "ecotoxicology")
    _TOXREF_SEGMENTS = {
        "summary": "summary",
        "data": "data",
        "effects": "effects",
        "observations": "observations",
    }
    _TOXREF_LOOKUPS = {
        "dtxsid": "by-dtxsid",
        "study-id": "by-study-id",
        "study-type": "by-study-type",
    }

    def _encode(self, value: Any) -> str:
        return urllib.parse.quote(str(value))

    def _json_batch(self, suffix: str, identifiers: Iterable[str]) -> List[Any]:
        return super().batch(suffix, identifiers, self._default_batch_size, bracketed=True)

    def toxval(self, dtxsid: str) -> List[Any]:
        return self._request("GET", f"hazard/toxval/search/by-dtxsid/{self._encode(dtxsid)}") or []

    def toxval_batch(self, dtxsids: Iterable[str]) -> List[Any]:
        return self._json_batch("hazard/toxval/search/by-dtxsid/", dtxsids)

    def skin_eye(self, dtxsid: str) -> List[Any]:
        return self._request("GET", f"hazard/skin-eye/search/by-dtxsid/{self._encode(dtxsid)}") or []

    def skin_eye_batch(self, dtxsids: Iterable[str]) -> List[Any]:
        return self._json_batch("hazard/skin-eye/search/by-dtxsid/", dtxsids)

    def cancer_summary(self, dtxsid: str) -> List[Any]:
        return self._request(
            "GET",
            f"hazard/cancer-summary/search/by-dtxsid/{self._encode(dtxsid)}",
        ) or []

    def cancer_summary_batch(self, dtxsids: Iterable[str]) -> List[Any]:
        return self._json_batch("hazard/cancer-summary/search/by-dtxsid/", dtxsids)

    def genetox_summary(self, dtxsid: str) -> List[Any]:
        return self._request(
            "GET",
            f"hazard/genetox/summary/search/by-dtxsid/{self._encode(dtxsid)}",
        ) or []

    def genetox_summary_batch(self, dtxsids: Iterable[str]) -> List[Any]:
        return self._json_batch("hazard/genetox/summary/search/by-dtxsid/", dtxsids)

    def genetox_details(self, dtxsid: str) -> List[Any]:
        return self._request(
            "GET",
            f"hazard/genetox/details/search/by-dtxsid/{self._encode(dtxsid)}",
        ) or []

    def genetox_details_batch(self, dtxsids: Iterable[str]) -> List[Any]:
        return self._json_batch("hazard/genetox/details/search/by-dtxsid/", dtxsids)

    def adme_ivive(self, dtxsid: str) -> List[Any]:
        return self._request(
            "GET",
            f"hazard/adme-ivive/search/by-dtxsid/{self._encode(dtxsid)}",
        ) or []

    def pprtv(self, dtxsid: str) -> List[Any]:
        return self._request(
            "GET",
            f"hazard/pprtv/search/by-dtxsid/{self._encode(dtxsid)}",
        ) or []

    def iris(self, dtxsid: str) -> List[Any]:
        return self._request(
            "GET",
            f"hazard/iris/search/by-dtxsid/{self._encode(dtxsid)}",
        ) or []

    def hawc(self, dtxsid: str) -> List[Any]:
        return self._request(
            "GET",
            f"hazard/hawc/search/by-dtxsid/{self._encode(dtxsid)}",
        ) or []

    def toxref(self, *, dataset: str, lookup: str, value: str) -> List[Any]:
        dataset_key = self._TOXREF_SEGMENTS.get((dataset or "").strip().lower())
        if not dataset_key:
            raise ValueError(f"Unsupported toxref dataset '{dataset}'")
        lookup_key = self._TOXREF_LOOKUPS.get((lookup or "").strip().lower())
        if not lookup_key:
            raise ValueError(f"Unsupported toxref lookup '{lookup}'")
        if value is None or str(value).strip() == "":
            raise ValueError("value is required for toxref lookups")
        return self._request(
            "GET",
            f"hazard/toxref/{dataset_key}/search/{lookup_key}/{self._encode(value)}",
        ) or []

    def toxref_batch(self, dtxsids: Iterable[str]) -> List[Any]:
        return self._json_batch("hazard/toxref/search/by-dtxsid/", dtxsids)

    def search(self, by: str, dtxsid: str, summary: bool = True) -> Any:
        norm = (by or "all").strip().lower()
        normalized_sid = (dtxsid or "").strip()
        if not normalized_sid:
            raise ValueError("dtxsid is required for hazard searches")

        if norm in ("all", "toxval", "hazard"):
            return self.toxval(normalized_sid)

        if norm in ("human", "human health"):
            records = self.toxval(normalized_sid)
            filtered: List[Dict[str, Any]] = []
            for rec in records:
                category = str(rec.get("humanEco", "")).lower()
                if category.startswith(self._HUMAN_TAGS) or "human" in category:
                    filtered.append(rec)
            return filtered

        if norm in ("eco", "ecotoxicology"):
            records = self.toxval(normalized_sid)
            filtered: List[Dict[str, Any]] = []
            for rec in records:
                category = str(rec.get("humanEco", "")).lower()
                if any(tag in category for tag in self._ECO_TAGS):
                    filtered.append(rec)
            return filtered

        if norm == "skin-eye":
            return self.skin_eye(normalized_sid)

        if norm == "cancer":
            return self.cancer_summary(normalized_sid)

        if norm == "genetox":
            return (
                self.genetox_summary(normalized_sid)
                if summary
                else self.genetox_details(normalized_sid)
            )

        if norm == "adme":
            return self.adme_ivive(normalized_sid)

        if norm == "toxref":
            dataset = "summary" if summary else "data"
            return self.toxref(dataset=dataset, lookup="dtxsid", value=normalized_sid)

        if norm == "pprtv":
            return self.pprtv(normalized_sid)

        if norm == "iris":
            return self.iris(normalized_sid)

        if norm == "hawc":
            return self.hawc(normalized_sid)

        raise ValueError(f"Unsupported hazard data_type '{by}'")

    def batch_search(self, by: str, dtxsid: Iterable[str], summary: bool = True) -> Dict[str, Any]:
        results: Dict[str, Any] = {}
        for sid in dtxsid:
            if sid is None:
                continue
            normalized_sid = str(sid).strip()
            if not normalized_sid:
                continue
            results[normalized_sid] = self.search(by=by, dtxsid=normalized_sid, summary=summary)
        return results


class Exposure(_BaseCtxClient):
    def search_cpdat(self, vocab_name: str, dtxsid: str) -> Any:
        norm = (vocab_name or "").strip().lower()
        quoted = urllib.parse.quote(str(dtxsid))
        if norm == "fc":
            path = f"exposure/functional-use/search/by-dtxsid/{quoted}"
        elif norm == "puc":
            path = f"exposure/product-data/search/by-dtxsid/{quoted}"
        elif norm == "lpk":
            path = f"exposure/list-presence/search/by-dtxsid/{quoted}"
        else:
            raise ValueError(f"Unsupported CPDat vocabulary '{vocab_name}'")
        return self._request("GET", path) or []

    def search_httk(self, dtxsid: str) -> Any:
        quoted = urllib.parse.quote(str(dtxsid))
        return self._request("GET", f"exposure/httk/search/by-dtxsid/{quoted}") or []

    def get_cpdat_vocabulary(self, vocab_name: str) -> Any:
        norm = (vocab_name or "").strip().lower()
        if norm == "fc":
            path = "exposure/functional-use/category"
        elif norm == "puc":
            path = "exposure/product-data/puc"
        elif norm == "lpk":
            path = "exposure/list-presence/tags"
        else:
            raise ValueError(f"Unsupported CPDat vocabulary '{vocab_name}'")
        return self._request("GET", path) or []

    def search_qsurs(self, dtxsid: str) -> Any:
        quoted = urllib.parse.quote(str(dtxsid))
        return self._request("GET", f"exposure/functional-use/probability/search/by-dtxsid/{quoted}") or []

    def search_exposures(self, by: str, dtxsid: str) -> Any:
        norm = (by or "").strip().lower()
        quoted = urllib.parse.quote(str(dtxsid))

        if norm in ("pathways", "aggregate", "mmdb-aggregate"):
            return self._request("GET", f"exposure/mmdb/aggregate/by-dtxsid/{quoted}") or []
        if norm in ("mmdb-single", "single"):
            return self._request("GET", f"exposure/mmdb/single-sample/by-dtxsid/{quoted}") or []
        if norm in ("seem", "seem-general", "general"):
            return self._request("GET", f"exposure/seem/general/search/by-dtxsid/{quoted}") or []
        if norm in ("seem-demographic", "demographic"):
            return self._request("GET", f"exposure/seem/demographic/search/by-dtxsid/{quoted}") or []

        raise ValueError(f"Unsupported exposure data_type '{by}'")

    def product_data(self, dtxsid: str) -> Any:
        return self.search_cpdat("puc", dtxsid)

    def product_data_batch(self, dtxsids: Iterable[str]) -> List[Any]:
        return self._json_batch("exposure/product-data/search/by-dtxsid/", dtxsids)

    def product_data_puc(self) -> Any:
        return self.get_cpdat_vocabulary("puc")

    def list_presence(self, dtxsid: str) -> Any:
        return self.search_cpdat("lpk", dtxsid)

    def list_presence_batch(self, dtxsids: Iterable[str]) -> List[Any]:
        return self._json_batch("exposure/list-presence/search/by-dtxsid/", dtxsids)

    def list_presence_tags(self) -> Any:
        return self.get_cpdat_vocabulary("lpk")

    def httk(self, dtxsid: str) -> Any:
        return self.search_httk(dtxsid)

    def httk_batch(self, dtxsids: Iterable[str]) -> List[Any]:
        return self._json_batch("exposure/httk/search/by-dtxsid/", dtxsids)

    def functional_use(self, dtxsid: str) -> Any:
        return self.search_cpdat("fc", dtxsid)

    def functional_use_batch(self, dtxsids: Iterable[str]) -> List[Any]:
        return self._json_batch("exposure/functional-use/search/by-dtxsid/", dtxsids)

    def functional_use_probability(self, dtxsid: str) -> Any:
        return self.search_qsurs(dtxsid)

    def functional_use_categories(self) -> Any:
        return self.get_cpdat_vocabulary("fc")

    def seem_general(self, dtxsid: str) -> Any:
        quoted = urllib.parse.quote(str(dtxsid))
        return self.get(f"exposure/seem/general/search/by-dtxsid/{quoted}")

    def seem_general_batch(self, dtxsids: Iterable[str]) -> List[Any]:
        return self._json_batch("exposure/seem/general/search/by-dtxsid/", dtxsids)

    def seem_demographic(self, dtxsid: str) -> Any:
        quoted = urllib.parse.quote(str(dtxsid))
        return self.get(f"exposure/seem/demographic/search/by-dtxsid/{quoted}")

    def seem_demographic_batch(self, dtxsids: Iterable[str]) -> List[Any]:
        return self._json_batch("exposure/seem/demographic/search/by-dtxsid/", dtxsids)

    def ccd_puc(self, dtxsid: str) -> Any:
        quoted = urllib.parse.quote(str(dtxsid))
        return self.get(f"exposure/ccd/puc/search/by-dtxsid/{quoted}")

    def ccd_production_volume(self, dtxsid: str) -> Any:
        quoted = urllib.parse.quote(str(dtxsid))
        return self.get(f"exposure/ccd/production-volume/search/by-dtxsid/{quoted}")

    def ccd_monitoring_data(self, dtxsid: str) -> Any:
        quoted = urllib.parse.quote(str(dtxsid))
        return self.get(f"exposure/ccd/monitoring-data/search/by-dtxsid/{quoted}")

    def ccd_keywords(self, dtxsid: str) -> Any:
        quoted = urllib.parse.quote(str(dtxsid))
        return self.get(f"exposure/ccd/keywords/search/by-dtxsid/{quoted}")

    def ccd_functional_use(self, dtxsid: str) -> Any:
        quoted = urllib.parse.quote(str(dtxsid))
        return self.get(f"exposure/ccd/functional-use/search/by-dtxsid/{quoted}")

    def ccd_chem_weight_fractions(self, dtxsid: str) -> Any:
        quoted = urllib.parse.quote(str(dtxsid))
        return self.get(f"exposure/ccd/chemical-weight-fraction/search/by-dtxsid/{quoted}")

    def mmdb_single_sample_by_medium(self, medium: str) -> Any:
        quoted = urllib.parse.quote(str(medium))
        return self.get(f"exposure/mmdb/single-sample/search/by-medium/{quoted}")

    def mmdb_single_sample_by_dtxsid(self, dtxsid: str) -> Any:
        quoted = urllib.parse.quote(str(dtxsid))
        return self.get(f"exposure/mmdb/single-sample/search/by-dtxsid/{quoted}")

    def mmdb_mediums(self) -> Any:
        return self.get("exposure/mmdb/mediums")

    def mmdb_aggregate_by_medium(self, medium: str) -> Any:
        quoted = urllib.parse.quote(str(medium))
        return self.get(f"exposure/mmdb/aggregate/search/by-medium/{quoted}")

    def mmdb_aggregate_by_dtxsid(self, dtxsid: str) -> Any:
        quoted = urllib.parse.quote(str(dtxsid))
        return self.get(f"exposure/mmdb/aggregate/search/by-dtxsid/{quoted}")


class ChemicalList(_BaseCtxClient):
    def public_list_names(self) -> List[str]:
        lists = self._request("GET", "chemical/list/") or []
        return [
            item.get("listName")
            for item in lists
            if isinstance(item, dict) and item.get("visibility", "").upper() == "PUBLIC"
        ]

    def get_full_list(self, list_name: str) -> Any:
        quoted = urllib.parse.quote(str(list_name))
        return self._request("GET", f"chemical/list/chemicals/search/by-listname/{quoted}") or []


def search_toxprints(chemical: str) -> Any:
    client = _BaseCtxClient(os.environ.get("ctx_x_api_key") or os.environ.get("CTX_API_KEY"))
    try:
        return client._request("GET", "cheminformatics/search_toxprints", params={"chemical": chemical})
    except RuntimeError as exc:
        cause = exc.__cause__
        if isinstance(cause, urllib.error.HTTPError) and cause.code == 404:
            raise RuntimeError(
                "Cheminformatics ToxPrint endpoints are not available on the new CTX API. "
                "Consult EPA documentation for migration guidance."
            ) from exc
        raise
