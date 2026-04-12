from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

from epacomp_tox.contracts import validate_payload

from .base import ADCheckResult, PredictiveRequest
from .descriptor_providers import (
    DescriptorProvider,
    DescriptorProviderError,
    build_descriptor_provider_from_env,
)
from .rule_providers import (
    ExpertRuleProvider,
    ExpertRuleProviderError,
    build_rule_provider_from_env,
)

AD_RESPONSE_SCHEMA = ("predictive", "ad_check.response.schema")
SUPPORTED_CRITERION_TYPES = {
    "similarity",
    "coverage",
    "descriptor_range",
    "expert_rule",
}


class ADEvaluationRequest(BaseModel):
    request: PredictiveRequest
    applicability_domain: Optional[Dict[str, Any]] = Field(
        default=None,
        alias="applicabilityDomain",
    )

    model_config = {
        "populate_by_name": True,
    }


def evaluate_reference_ad(
    request: PredictiveRequest,
    definition: Optional[Dict[str, Any]],
    *,
    descriptor_provider: Optional[DescriptorProvider] = None,
    rule_provider: Optional[ExpertRuleProvider] = None,
) -> ADCheckResult:
    details: Dict[str, Any] = {
        "adEvaluator": "external-chemistry-service",
        "adEnforcementLocation": "local-engine",
        "evaluationMode": "reference-sidecar",
        "supportedCriterionTypes": sorted(SUPPORTED_CRITERION_TYPES),
    }
    if descriptor_provider is not None:
        details["descriptorProvider"] = descriptor_provider.name
    if rule_provider is not None:
        details["ruleProvider"] = rule_provider.name
    if not definition:
        details["reason"] = "missing_applicability_domain_definition"
        return ADCheckResult(in_domain=False, confidence=0.0, details=details)

    criteria = list(definition.get("criteria") or [])
    criterion_results: List[Dict[str, Any]] = []
    supported_count = 0
    aggregate_confidence = 0.0

    for index, criterion in enumerate(criteria):
        criterion_type = str(criterion.get("type") or "").strip().lower()
        if criterion_type == "similarity":
            result = _evaluate_similarity_criterion(request, criterion)
        elif criterion_type == "coverage":
            result = _evaluate_coverage_criterion(request, criterion)
        elif criterion_type == "descriptor_range":
            result = _evaluate_descriptor_range_criterion(
                request,
                criterion,
                definition,
                descriptor_provider=descriptor_provider,
            )
        elif criterion_type == "expert_rule":
            result = _evaluate_expert_rule_criterion(
                request,
                criterion,
                definition,
                rule_provider=rule_provider,
            )
        else:
            result = {
                "type": criterion_type or "unknown",
                "supported": False,
                "passed": False,
                "reason": "unsupported_criterion_type",
            }
        result["index"] = index
        criterion_results.append(result)

        if result.get("supported"):
            supported_count += 1
            aggregate_confidence += float(result.get("confidence", 0.0))

    unsupported = [
        result["type"] for result in criterion_results if not result.get("supported")
    ]
    failures = [
        result
        for result in criterion_results
        if result.get("supported") and not result.get("passed")
    ]

    if supported_count == 0:
        confidence = 0.0
        in_domain = False
        details["reason"] = "no_supported_criteria_in_definition"
    else:
        support_fraction = supported_count / max(len(criteria), 1)
        mean_confidence = aggregate_confidence / supported_count
        confidence = round(mean_confidence * support_fraction, 4)
        in_domain = not failures

    details.update(
        {
            "criterionResults": criterion_results,
            "supportedCriteria": supported_count,
            "unsupportedCriteria": unsupported,
            "criteriaCoverage": round(
                supported_count / max(len(criteria), 1),
                4,
            )
            if criteria
            else 0.0,
            "definitionModel": definition.get("model"),
            "definitionVersion": definition.get("version"),
        }
    )
    return ADCheckResult(in_domain=in_domain, confidence=confidence, details=details)


def build_reference_ad_sidecar_app(
    *,
    descriptor_provider: Optional[DescriptorProvider] = None,
    rule_provider: Optional[ExpertRuleProvider] = None,
) -> FastAPI:
    active_descriptor_provider = descriptor_provider or build_descriptor_provider_from_env()
    active_rule_provider = rule_provider or build_rule_provider_from_env()
    app = FastAPI(
        title="CompTox Reference AD Sidecar",
        version="0.1.0",
    )

    @app.get("/healthz")
    async def healthz() -> Dict[str, Any]:
        return {
            "status": "ok",
            "service": "CompTox Reference AD Sidecar",
            "descriptorProvider": (
                active_descriptor_provider.name
                if active_descriptor_provider is not None
                else None
            ),
            "ruleProvider": (
                active_rule_provider.name if active_rule_provider is not None else None
            ),
        }

    @app.post(
        "/evaluate",
        response_model=ADCheckResult,
        summary="Evaluate supported applicability-domain criteria",
    )
    async def evaluate_endpoint(body: ADEvaluationRequest) -> ADCheckResult:
        result = evaluate_reference_ad(
            body.request,
            body.applicability_domain,
            descriptor_provider=active_descriptor_provider,
            rule_provider=active_rule_provider,
        )
        validate_payload(
            result.model_dump(),
            namespace=AD_RESPONSE_SCHEMA[0],
            name=AD_RESPONSE_SCHEMA[1],
        )
        return result

    return app


def _evaluate_similarity_criterion(
    request: PredictiveRequest, criterion: Dict[str, Any]
) -> Dict[str, Any]:
    similarity_inputs = request.ad_inputs.get("similarity") or {}
    metric = str(criterion.get("metric") or "tanimoto")
    metric_inputs = similarity_inputs.get(metric)
    if isinstance(metric_inputs, dict):
        payload = metric_inputs
    else:
        payload = similarity_inputs

    score = payload.get("score")
    threshold = criterion.get("threshold")
    if score is None or threshold is None:
        return {
            "type": "similarity",
            "supported": True,
            "passed": False,
            "reason": "missing_similarity_inputs",
            "confidence": 0.0,
            "metric": metric,
        }

    neighbors_required = criterion.get("neighbors") or criterion.get("minAnalogues")
    neighbors_available = payload.get("neighbors") or payload.get("analogueCount")
    threshold_pass = float(score) >= float(threshold)
    neighbor_pass = True
    if neighbors_required is not None:
        neighbor_pass = (neighbors_available or 0) >= int(neighbors_required)

    passed = threshold_pass and neighbor_pass
    ratio = float(score) / float(threshold) if float(threshold) > 0 else 1.0
    confidence = max(0.0, min(ratio, 1.0))
    if neighbors_required is not None and neighbors_available is not None:
        neighbor_ratio = min(float(neighbors_available) / float(neighbors_required), 1.0)
        confidence = round((confidence + neighbor_ratio) / 2.0, 4)
    else:
        confidence = round(confidence, 4)

    return {
        "type": "similarity",
        "supported": True,
        "passed": passed,
        "confidence": confidence,
        "metric": metric,
        "score": score,
        "threshold": threshold,
        "neighborsRequired": neighbors_required,
        "neighborsAvailable": neighbors_available,
    }


def _evaluate_coverage_criterion(
    request: PredictiveRequest, criterion: Dict[str, Any]
) -> Dict[str, Any]:
    coverage_inputs = request.ad_inputs.get("coverage") or {}
    domains = coverage_inputs.get("domains") or coverage_inputs.get("availableDomains") or []
    if not isinstance(domains, list):
        domains = []
    normalized_domains = {str(domain).strip().lower() for domain in domains}

    requirements = [
        str(requirement).strip().lower()
        for requirement in (criterion.get("requirements") or [])
    ]
    minimum_domains = int(criterion.get("minimumDomains") or 0)
    missing_requirements = [
        requirement
        for requirement in requirements
        if requirement not in normalized_domains
    ]
    passed = len(normalized_domains) >= minimum_domains and not missing_requirements
    coverage_ratio = 0.0
    if minimum_domains > 0:
        coverage_ratio = min(len(normalized_domains) / minimum_domains, 1.0)
    requirement_ratio = 1.0
    if requirements:
        met_requirements = len(requirements) - len(missing_requirements)
        requirement_ratio = met_requirements / len(requirements)
    confidence = round((coverage_ratio + requirement_ratio) / 2.0, 4)

    return {
        "type": "coverage",
        "supported": True,
        "passed": passed,
        "confidence": confidence,
        "availableDomains": sorted(normalized_domains),
        "requiredDomains": requirements,
        "missingRequirements": missing_requirements,
        "minimumDomains": minimum_domains,
    }


def _evaluate_descriptor_range_criterion(
    request: PredictiveRequest,
    criterion: Dict[str, Any],
    definition: Optional[Dict[str, Any]],
    *,
    descriptor_provider: Optional[DescriptorProvider],
) -> Dict[str, Any]:
    descriptors = [
        str(descriptor).strip()
        for descriptor in (criterion.get("descriptors") or [])
        if str(descriptor).strip()
    ]
    if not descriptors:
        return {
            "type": "descriptor_range",
            "supported": True,
            "passed": False,
            "reason": "missing_descriptor_list",
            "confidence": 0.0,
        }

    inline_values = _coerce_numeric_mapping(
        request.ad_inputs.get("descriptor_values")
        or request.ad_inputs.get("descriptorValues")
        or {}
    )
    inline_bounds = _coerce_bounds_mapping(
        request.ad_inputs.get("descriptor_bounds")
        or request.ad_inputs.get("descriptorBounds")
        or {}
    )
    descriptor_context_source = "request.ad_inputs"
    provider_metadata: Dict[str, Any] = {}

    if descriptor_provider is not None:
        try:
            context = descriptor_provider.resolve(
                request=request,
                descriptors=descriptors,
                criterion=criterion,
                definition=definition,
            )
        except DescriptorProviderError as exc:
            return {
                "type": "descriptor_range",
                "supported": True,
                "passed": False,
                "reason": "descriptor_provider_error",
                "confidence": 0.0,
                "error": str(exc),
                "descriptorProvider": descriptor_provider.name,
            }
        inline_values.update(context.values)
        inline_bounds.update(context.bounds)
        descriptor_context_source = context.source
        provider_metadata = context.metadata
    elif not inline_values and not inline_bounds:
        return {
            "type": "descriptor_range",
            "supported": False,
            "passed": False,
            "reason": "descriptor_backend_not_configured",
        }

    missing_values = [
        descriptor for descriptor in descriptors if descriptor not in inline_values
    ]
    missing_bounds = [
        descriptor for descriptor in descriptors if descriptor not in inline_bounds
    ]
    if missing_values or missing_bounds:
        return {
            "type": "descriptor_range",
            "supported": True,
            "passed": False,
            "reason": "missing_descriptor_context",
            "confidence": 0.0,
            "missingValues": missing_values,
            "missingBounds": missing_bounds,
            "descriptorSource": descriptor_context_source,
        }

    descriptor_results: List[Dict[str, Any]] = []
    per_descriptor_confidence: List[float] = []
    all_pass = True
    for descriptor in descriptors:
        value = inline_values[descriptor]
        bounds = inline_bounds[descriptor]
        lower = bounds["lower"]
        upper = bounds["upper"]
        passed = lower <= value <= upper
        all_pass = all_pass and passed
        descriptor_confidence = _range_confidence(value, lower, upper, passed=passed)
        per_descriptor_confidence.append(descriptor_confidence)
        descriptor_results.append(
            {
                "descriptor": descriptor,
                "value": value,
                "lower": lower,
                "upper": upper,
                "passed": passed,
                "confidence": descriptor_confidence,
            }
        )

    confidence = round(
        sum(per_descriptor_confidence) / max(len(per_descriptor_confidence), 1), 4
    )
    return {
        "type": "descriptor_range",
        "supported": True,
        "passed": all_pass,
        "confidence": confidence,
        "descriptorSource": descriptor_context_source,
        "descriptorResults": descriptor_results,
        "rangeDefinition": criterion.get("range"),
        "providerMetadata": provider_metadata,
    }


def _evaluate_expert_rule_criterion(
    request: PredictiveRequest,
    criterion: Dict[str, Any],
    definition: Optional[Dict[str, Any]],
    *,
    rule_provider: Optional[ExpertRuleProvider],
) -> Dict[str, Any]:
    rule_name = str(criterion.get("rule") or "").strip()
    normalized_rule = _normalize_rule_name(rule_name)
    if normalized_rule != "mode_of_action_tags_align":
        return {
            "type": "expert_rule",
            "supported": False,
            "passed": False,
            "reason": "unsupported_expert_rule",
            "rule": rule_name,
        }

    inline_context = (
        request.ad_inputs.get("expert_rule")
        or request.ad_inputs.get("expertRule")
        or {}
    )
    context_source = "request.ad_inputs"
    provider_metadata: Dict[str, Any] = {}

    if rule_provider is not None:
        try:
            provider_context = rule_provider.resolve(
                request=request,
                criterion=criterion,
                definition=definition,
            )
        except ExpertRuleProviderError as exc:
            return {
                "type": "expert_rule",
                "supported": True,
                "passed": False,
                "reason": "expert_rule_provider_error",
                "confidence": 0.0,
                "error": str(exc),
                "ruleProvider": rule_provider.name,
                "rule": rule_name,
            }
        inline_context = _deep_merge_dicts(inline_context, provider_context.payload)
        context_source = provider_context.source
        provider_metadata = provider_context.metadata

    moa_context = (
        inline_context.get("mode_of_action_tags")
        or inline_context.get("modeOfActionTags")
        or inline_context
    )
    if not isinstance(moa_context, dict):
        moa_context = {}

    target_tags = _normalize_tags(
        moa_context.get("target_tags")
        or moa_context.get("targetTags")
        or moa_context.get("target")
    )
    analogues_raw = moa_context.get("analogues") or moa_context.get("analoguesRaw") or []
    analogue_contexts = _normalize_analogue_contexts(analogues_raw)
    derivation_source: Optional[str] = None
    if not target_tags or not analogue_contexts:
        derived_context, derivation_source = _derive_mode_of_action_context(inline_context)
        if not target_tags:
            target_tags = _normalize_tags(
                derived_context.get("target_tags") or derived_context.get("targetTags")
            )
        if not analogue_contexts:
            analogue_contexts = _normalize_analogue_contexts(
                derived_context.get("analogues") or []
            )
        if derivation_source:
            context_source = derivation_source
    if not target_tags or not analogue_contexts:
        return {
            "type": "expert_rule",
            "supported": True,
            "passed": False,
            "reason": "missing_expert_rule_context",
            "confidence": 0.0,
            "rule": rule_name,
            "ruleSource": context_source,
        }

    allowable_mismatch = int(criterion.get("allowableMismatch") or 0)
    analogue_results: List[Dict[str, Any]] = []
    similarity_scores: List[float] = []
    all_pass = True
    for analogue in analogue_contexts:
        analogue_tags = analogue["tags"]
        union = sorted(target_tags | analogue_tags)
        mismatch_count = len(target_tags.symmetric_difference(analogue_tags))
        passed = mismatch_count <= allowable_mismatch
        all_pass = all_pass and passed
        similarity = _tag_similarity(target_tags, analogue_tags)
        similarity_scores.append(similarity)
        analogue_results.append(
            {
                "id": analogue["id"],
                "tags": sorted(analogue_tags),
                "mismatchCount": mismatch_count,
                "allowableMismatch": allowable_mismatch,
                "passed": passed,
                "similarity": similarity,
                "unionTags": union,
            }
        )

    confidence = round(sum(similarity_scores) / max(len(similarity_scores), 1), 4)
    return {
        "type": "expert_rule",
        "supported": True,
        "passed": all_pass,
        "confidence": confidence,
        "rule": rule_name,
        "ruleKey": normalized_rule,
        "ruleSource": context_source,
        "targetTags": sorted(target_tags),
        "analogueResults": analogue_results,
        "providerMetadata": provider_metadata,
        "mechanisticDerivationUsed": bool(derivation_source),
    }


def _coerce_numeric_mapping(payload: Any) -> Dict[str, float]:
    if not isinstance(payload, dict):
        return {}
    result: Dict[str, float] = {}
    for key, value in payload.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            result[str(key)] = float(value)
    return result


def _coerce_bounds_mapping(payload: Any) -> Dict[str, Dict[str, float]]:
    if not isinstance(payload, dict):
        return {}
    result: Dict[str, Dict[str, float]] = {}
    for descriptor, bound_payload in payload.items():
        if not isinstance(bound_payload, dict):
            continue
        lower = (
            bound_payload.get("lower")
            if bound_payload.get("lower") is not None
            else bound_payload.get("min")
        )
        upper = (
            bound_payload.get("upper")
            if bound_payload.get("upper") is not None
            else bound_payload.get("max")
        )
        if isinstance(lower, (int, float)) and isinstance(upper, (int, float)):
            result[str(descriptor)] = {"lower": float(lower), "upper": float(upper)}
    return result


def _range_confidence(value: float, lower: float, upper: float, *, passed: bool) -> float:
    if upper <= lower:
        return 1.0 if passed else 0.0
    if not passed:
        return 0.0
    center = (lower + upper) / 2.0
    half_width = (upper - lower) / 2.0
    if half_width <= 0:
        return 1.0
    distance = abs(value - center) / half_width
    return round(max(0.0, min(1.0 - distance, 1.0)), 4)


def _normalize_rule_name(rule_name: str) -> str:
    normalized = " ".join(rule_name.lower().split())
    if normalized == "mode of action tags must align":
        return "mode_of_action_tags_align"
    return normalized.replace(" ", "_")


def _normalize_tags(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    tags = set()
    for item in value:
        token = str(item).strip().lower()
        if token:
            tags.add(token)
    return tags


def _normalize_analogue_contexts(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result: List[Dict[str, Any]] = []
    for index, item in enumerate(value):
        analogue_id = f"analogue-{index + 1}"
        tags_value: Any = item
        if isinstance(item, dict):
            analogue_id = str(item.get("id") or item.get("name") or analogue_id)
            tags_value = item.get("tags") or item.get("mode_of_action_tags") or item.get(
                "modeOfActionTags"
            )
        tags = _normalize_tags(tags_value)
        if tags:
            result.append({"id": analogue_id, "tags": tags})
    return result


def _tag_similarity(target_tags: set[str], analogue_tags: set[str]) -> float:
    union = target_tags | analogue_tags
    if not union:
        return 1.0
    intersection = target_tags & analogue_tags
    return round(len(intersection) / len(union), 4)


def _derive_mode_of_action_context(value: Any) -> tuple[Dict[str, Any], Optional[str]]:
    mechanistic_context = _pick_mapping(
        value,
        "mechanistic_context",
        "mechanisticContext",
        "bioactivity_context",
        "bioactivityContext",
    )
    if mechanistic_context is None:
        mechanistic_context = value if isinstance(value, dict) else None
    if mechanistic_context is None:
        return {}, None

    target_context = _pick_mapping(mechanistic_context, "target") or {}
    analogues_raw = mechanistic_context.get("analogues") or mechanistic_context.get(
        "analogueContext"
    )
    if not isinstance(analogues_raw, list):
        analogues_raw = []

    target_tags = _derive_tags_from_mechanistic_evidence(target_context)
    analogue_payloads: List[Dict[str, Any]] = []
    for index, analogue in enumerate(analogues_raw):
        if not isinstance(analogue, dict):
            continue
        analogue_id = str(analogue.get("id") or analogue.get("name") or f"analogue-{index + 1}")
        analogue_tags = _derive_tags_from_mechanistic_evidence(analogue)
        if not analogue_tags:
            continue
        analogue_payloads.append({"id": analogue_id, "tags": sorted(analogue_tags)})

    if not target_tags or not analogue_payloads:
        return {}, None
    return (
        {
            "target_tags": sorted(target_tags),
            "analogues": analogue_payloads,
        },
        "derived:mechanistic_context",
    )


def _derive_tags_from_mechanistic_evidence(value: Any) -> set[str]:
    if not isinstance(value, dict):
        return set()
    tags: set[str] = set()
    tags.update(
        _normalize_tags(
            value.get("tags")
            or value.get("mode_of_action_tags")
            or value.get("modeOfActionTags")
        )
    )

    bioactivity_rows = _collect_rows(
        value,
        "bioactivity",
        "bioactivity_summary",
        "bioactivitySummary",
        "supportingAssays",
        "assays",
    )
    for row in bioactivity_rows:
        if _row_is_explicitly_inactive(row):
            continue
        gene = _pick_string(row, "geneSymbol", "targetName", "target", "gene")
        direction = _pick_string(
            row,
            "activityDirection",
            "direction",
            "responseDirection",
            "evidenceDirection",
        )
        component = _pick_string(row, "assayComponent", "component")
        if gene:
            tags.add(gene.lower())
        if component:
            tags.add(component.lower())
        if gene and direction:
            tags.add(f"{gene.lower()} {direction.lower()}")
        elif component and direction:
            tags.add(f"{component.lower()} {direction.lower()}")

    aop_rows = _collect_rows(
        value,
        "aop",
        "aop_mappings",
        "aopMappings",
        "mappings",
    )
    for row in aop_rows:
        event_label = _pick_string(row, "eventLabel", "event", "keyEvent")
        if event_label:
            tags.add(event_label.lower())

    return tags


def _collect_rows(value: Dict[str, Any], *keys: str) -> List[Dict[str, Any]]:
    for key in keys:
        rows = value.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def _pick_mapping(value: Any, *keys: str) -> Optional[Dict[str, Any]]:
    if not isinstance(value, dict):
        return None
    for key in keys:
        candidate = value.get(key)
        if isinstance(candidate, dict):
            return candidate
    return None


def _pick_string(row: Dict[str, Any], *keys: str) -> Optional[str]:
    for key in keys:
        candidate = row.get(key)
        if candidate is None:
            continue
        text = str(candidate).strip()
        if text:
            return text
    return None


def _row_is_explicitly_inactive(row: Dict[str, Any]) -> bool:
    for key in ("hitcall", "hitCall"):
        if key not in row:
            continue
        value = row.get(key)
        if value in (0, False, "0", "false", "False"):
            return True
    return False


def _deep_merge_dicts(left: Any, right: Any) -> Dict[str, Any]:
    base = dict(left) if isinstance(left, dict) else {}
    incoming = dict(right) if isinstance(right, dict) else {}
    for key, value in incoming.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            base[key] = _deep_merge_dicts(base[key], value)
        else:
            base[key] = value
    return base


app = build_reference_ad_sidecar_app()


__all__ = [
    "ADEvaluationRequest",
    "SUPPORTED_CRITERION_TYPES",
    "app",
    "build_reference_ad_sidecar_app",
    "evaluate_reference_ad",
]
