from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from epacomp_tox.predictive import ADCheckResult, PredictiveRequest, PredictiveResponse

IdentifierResolutionStatus = Literal["exact", "fallback", "ambiguous", "not_found"]


class MetadataTrace(BaseModel):
    """Structured record of transport metadata captured during orchestration."""

    step: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IdentifierResolution(BaseModel):
    """Canonicalized identity data for orchestrator workflows."""

    input_identifier: str
    input_type: str
    dtxsid: str
    resolution_status: IdentifierResolutionStatus = "exact"
    search_mode_used: str = "equals"
    candidate_count: int = 1
    matched_record: Dict[str, Any] = Field(default_factory=dict)
    detail_record: Dict[str, Any] = Field(default_factory=dict)
    preferred_name: Optional[str] = None
    casrn: Optional[str] = None
    synonyms: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    trace: List[MetadataTrace] = Field(default_factory=list)
    cache_hit: bool = False


class CtxDataBundle(BaseModel):
    """CTX data payload and provenance captured before predictive stages."""

    dtxsid: str
    scenarios: List[str] = Field(default_factory=list)
    hazard: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)
    exposure: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)
    cheminformatics: Dict[str, Any] = Field(default_factory=dict)
    mechanistic_context: Dict[str, Any] = Field(default_factory=dict)
    data_gaps: List[str] = Field(default_factory=list)
    trace: List[MetadataTrace] = Field(default_factory=list)
    cache_hit: bool = False


class PredictiveTask(BaseModel):
    """Definition of a predictive call executed during orchestration."""

    service: str
    request: PredictiveRequest
    scenario: Optional[str] = None
    label: Optional[str] = None


class GuardrailEvent(BaseModel):
    """Recorded guardrail outcome (denial, warning, or error)."""

    stage: str
    component: str
    status: str
    code: Optional[str]
    message: str
    confidence: Optional[float] = None
    timestamp: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PredictiveStepResult(BaseModel):
    """Outcome of an individual predictive service invocation."""

    service: str
    status: str
    scenario: Optional[str] = None
    label: Optional[str] = None
    request: PredictiveRequest
    ad: Optional[ADCheckResult] = None
    prediction: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class PredictiveRunResult(BaseModel):
    """Combined results for a predictive orchestration stage."""

    results: List[PredictiveStepResult] = Field(default_factory=list)
    guardrails: List[GuardrailEvent] = Field(default_factory=list)
    succeeded: bool = True


class EvidenceScore(BaseModel):
    """Weighted representation of evidence dimensions used in synthesis."""

    analogue_coverage: float
    evidence_quality: float
    predictive_agreement: float


class EvidenceSynthesis(BaseModel):
    """Structured result returned by the evidence grading engine."""

    confidence_band: str
    scores: Optional[EvidenceScore] = None
    assessment: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    narrative: str
    recommended_actions: List[str] = Field(default_factory=list)
    guardrail_events: List["GuardrailEvent"] = Field(default_factory=list)
