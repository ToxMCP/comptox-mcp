from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional

from epacomp_tox.metadata.applicability import ApplicabilityDomainStore
from epacomp_tox.predictive.ad_evaluators import ApplicabilityDomainEvaluator
from epacomp_tox.predictive.base import (
    ADCheckResult,
    PredictiveRequest,
    PredictiveServiceBase,
)
from epacomp_tox.predictive.clients import PredictiveClient


class GenRAClient(PredictiveClient):
    """Wrapper interface for GenRA analogue search + prediction service."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def predict(self, request: PredictiveRequest) -> Dict[str, Any]:
        return self.client.predict(
            chemical=request.chemical_identifier,
            identifier_type=request.identifier_type,
        )

    def search_analogues(self, request: PredictiveRequest) -> Any:
        method = None
        for name in (
            "search_analogues",
            "search_analogs",
            "find_analogues",
            "find_analogs",
            "get_analogues",
            "get_analogs",
            "analogue_search",
            "analog_search",
        ):
            candidate = getattr(self.client, name, None)
            if callable(candidate):
                method = candidate
                break
        if method is None:
            return None
        try:
            return method(
                chemical=request.chemical_identifier,
                identifier_type=request.identifier_type,
            )
        except TypeError:
            return method(request.chemical_identifier, request.identifier_type)

    def check_applicability_domain(self, request: PredictiveRequest) -> ADCheckResult:
        result = self.client.check_applicability_domain(
            chemical=request.chemical_identifier,
            identifier_type=request.identifier_type,
        )
        return ADCheckResult(
            in_domain=result.get("in_domain", False),
            confidence=result.get("confidence", 0.0),
            details=result,
        )


class GenRAService(PredictiveServiceBase):
    """Predictive service wrapper for the GenRA read-across workflow."""

    def __init__(
        self,
        *,
        config: Dict[str, Any],
        client: Optional[PredictiveClient] = None,
        ad_store: Optional[ApplicabilityDomainStore] = None,
        ad_evaluator: Optional[ApplicabilityDomainEvaluator] = None,
    ) -> None:
        super().__init__(
            config=config,
            ad_store=ad_store,
            ad_evaluator=ad_evaluator,
        )
        self.client = client

    def _ensure_client(self) -> PredictiveClient:
        if self.client is None:
            raise RuntimeError("GenRA client not configured")
        return self.client

    def prepare_request(self, request: PredictiveRequest) -> PredictiveRequest:
        if self._extract_existing_analogue_ids(request.ad_inputs):
            return request
        client = self._ensure_client()
        payload = client.search_analogues(request)
        analogue_ids = self._extract_analogue_ids_from_payload(payload)
        if not analogue_ids:
            return request
        return self._apply_analogue_ids_to_request(
            request,
            analogue_ids,
            source="genra-analogue-search",
        )

    def backfill_request_from_outputs(
        self,
        request: PredictiveRequest,
        *,
        ad_result: Optional[ADCheckResult],
        prediction_payload: Optional[Dict[str, Any]],
    ) -> PredictiveRequest:
        if self._extract_existing_analogue_ids(request.ad_inputs):
            return request
        analogue_ids, source = self._resolve_analogue_provenance(
            request,
            ad_result=ad_result,
            prediction_payload=prediction_payload,
        )
        if not analogue_ids:
            return request
        return self._apply_analogue_ids_to_request(request, analogue_ids, source=source)

    def _predict_impl(self, request: PredictiveRequest) -> Dict[str, Any]:
        client = self._ensure_client()
        return client.predict(request)

    def _check_ad_impl(self, request: PredictiveRequest) -> ADCheckResult:
        client = self._ensure_client()
        return client.check_applicability_domain(request)

    def _build_metadata(
        self,
        request: PredictiveRequest,
        ad_result: ADCheckResult,
        prediction_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        metadata = super()._build_metadata(request, ad_result, prediction_payload)
        analogue_ids, source = self._resolve_analogue_provenance(
            request,
            ad_result=ad_result,
            prediction_payload=prediction_payload,
        )
        if analogue_ids:
            metadata["resolvedAnalogueIds"] = analogue_ids
            metadata["resolvedAnalogueCount"] = len(analogue_ids)
            metadata["analogueIdSource"] = source
        return metadata

    def _extract_existing_analogue_ids(self, ad_inputs: Dict[str, Any]) -> list[str]:
        candidates = [
            ad_inputs.get("expert_rule"),
            ad_inputs.get("expertRule"),
            ad_inputs.get("similarity"),
        ]
        found: list[str] = []
        seen = set()
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            for key in (
                "analogueIds",
                "analogue_ids",
                "analogIds",
                "neighborIds",
                "neighbor_ids",
            ):
                value = candidate.get(key)
                if not isinstance(value, list):
                    continue
                for item in value:
                    analogue_id = self._normalize_dtxsid(item)
                    if analogue_id and analogue_id not in seen:
                        seen.add(analogue_id)
                        found.append(analogue_id)
            analogues = candidate.get("analogues")
            if isinstance(analogues, list):
                for item in analogues:
                    analogue_id = self._extract_dtxsid_from_value(item)
                    if analogue_id and analogue_id not in seen:
                        seen.add(analogue_id)
                        found.append(analogue_id)
        return found

    def _resolve_analogue_provenance(
        self,
        request: PredictiveRequest,
        *,
        ad_result: Optional[ADCheckResult],
        prediction_payload: Optional[Dict[str, Any]],
    ) -> tuple[list[str], str]:
        prediction_ids = self._extract_analogue_ids_from_payload(prediction_payload)
        if prediction_ids:
            return prediction_ids, "genra-prediction-payload"

        ad_ids = self._extract_analogue_ids_from_payload(
            ad_result.details if ad_result else None
        )
        if ad_ids:
            return ad_ids, "genra-ad-details"

        request_ids = self._extract_existing_analogue_ids(request.ad_inputs)
        if request_ids:
            expert_rule = request.ad_inputs.get("expert_rule") or request.ad_inputs.get(
                "expertRule"
            )
            source = "request.ad_inputs"
            if isinstance(expert_rule, dict):
                source = str(expert_rule.get("analogueIdSource") or source)
            return request_ids, source
        return [], "unavailable"

    def _apply_analogue_ids_to_request(
        self, request: PredictiveRequest, analogue_ids: list[str], *, source: str
    ) -> PredictiveRequest:
        ad_inputs = deepcopy(request.ad_inputs)
        similarity = dict(ad_inputs.get("similarity") or {})
        similarity.setdefault("neighborIds", analogue_ids)
        similarity.setdefault("neighbors", len(analogue_ids))
        ad_inputs["similarity"] = similarity

        expert_rule = dict(ad_inputs.get("expert_rule") or ad_inputs.get("expertRule") or {})
        expert_rule.setdefault("analogueIds", analogue_ids)
        expert_rule.setdefault("analogueIdSource", source)
        ad_inputs["expert_rule"] = expert_rule
        return request.model_copy(update={"ad_inputs": ad_inputs})

    def _extract_analogue_ids_from_payload(self, payload: Any) -> list[str]:
        found: list[str] = []
        seen = set()

        def _visit(value: Any) -> None:
            if isinstance(value, list):
                for item in value:
                    _visit(item)
                return
            if isinstance(value, dict):
                analogue_id = self._extract_dtxsid_from_value(value)
                if analogue_id and analogue_id not in seen:
                    seen.add(analogue_id)
                    found.append(analogue_id)
                for key in (
                    "analogues",
                    "analogs",
                    "neighbors",
                    "neighbours",
                    "results",
                    "hits",
                    "candidates",
                    "readAcrossCandidates",
                    "read_across_candidates",
                ):
                    if key in value:
                        _visit(value.get(key))
                return
            analogue_id = self._normalize_dtxsid(value)
            if analogue_id and analogue_id not in seen:
                seen.add(analogue_id)
                found.append(analogue_id)

        _visit(payload)
        return found

    def _extract_dtxsid_from_value(self, value: Any) -> Optional[str]:
        if isinstance(value, dict):
            for key in (
                "dtxsid",
                "analogueDtxsid",
                "analogue_dtxsid",
                "analogDtxsid",
                "analog_dtxsid",
                "chemicalIdentifier",
                "chemical_identifier",
                "substanceId",
                "substance_id",
                "sid",
                "id",
            ):
                analogue_id = self._normalize_dtxsid(value.get(key))
                if analogue_id:
                    return analogue_id
            return None
        return self._normalize_dtxsid(value)

    def _normalize_dtxsid(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip().upper()
        if text.startswith("DTXSID"):
            return text
        return None
