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
    def __init__(self, x_api_key: str, base_url: Optional[str] = None):
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
        timeout: float = 30.0,
    ) -> Any:
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
            with urllib.request.urlopen(req, timeout=timeout) as response:
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


class Hazard(_BaseCtxClient):
    _HUMAN_TAGS = ("human", "human health")
    _ECO_TAGS = ("eco", "ecotoxicology")

    def search(self, by: str, dtxsid: str, summary: bool = True) -> Any:
        norm = (by or "all").strip().lower()
        quoted = urllib.parse.quote(str(dtxsid))

        if norm in ("all", "human", "eco"):
            records = self._request("GET", f"hazard/toxval/search/by-dtxsid/{quoted}") or []
            if norm == "human":
                filtered: List[Dict[str, Any]] = []
                for rec in records:
                    category = str(rec.get("humanEco", "")).lower()
                    if category.startswith(self._HUMAN_TAGS) or "human" in category:
                        filtered.append(rec)
                return filtered
            if norm == "eco":
                filtered = []
                for rec in records:
                    category = str(rec.get("humanEco", "")).lower()
                    if any(tag in category for tag in self._ECO_TAGS):
                        filtered.append(rec)
                return filtered
            return records

        if norm == "skin-eye":
            return self._request("GET", f"hazard/skin-eye/search/by-dtxsid/{quoted}") or []

        if norm == "cancer":
            return self._request("GET", f"hazard/cancer-summary/search/by-dtxsid/{quoted}") or []

        if norm == "genetox":
            path = "hazard/genetox/summary/search/by-dtxsid" if summary else "hazard/genetox/details/search/by-dtxsid"
            return self._request("GET", f"{path}/{quoted}") or []

        if norm == "adme":
            return self._request("GET", f"hazard/adme-ivive/search/by-dtxsid/{quoted}") or []

        if norm == "toxref":
            base = "hazard/toxref/summary/search/by-dtxsid" if summary else "hazard/toxref/data/search/by-dtxsid"
            return self._request("GET", f"{base}/{quoted}") or []

        raise ValueError(f"Unsupported hazard data_type '{by}'")

    def batch_search(self, by: str, dtxsid: Iterable[str], summary: bool = True) -> Dict[str, Any]:
        results: Dict[str, Any] = {}
        for sid in dtxsid:
            results[sid] = self.search(by=by, dtxsid=sid, summary=summary)
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
