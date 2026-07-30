"""Public contracts for advisory and review operations."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Intent(str, Enum):
    CROP_PLAN = "crop_plan_request"
    DIAGNOSE = "diagnose"
    SCHEME = "scheme_query"


class QueryRequest(BaseModel):
    farmer_id: str = Field(min_length=3, max_length=64)
    query: str = Field(min_length=3, max_length=1_000)
    intent: Intent | None = None
    language: str = Field(default="en", min_length=2, max_length=8)
    requested_dose_ml_per_l: float | None = Field(default=None, ge=0, le=100)


class KnowledgeHit(BaseModel):
    source: str
    title: str
    score: float = Field(ge=0, le=1)
    metadata: dict[str, str | int | float | bool | list[str]] = Field(default_factory=dict)


class VerificationCheck(BaseModel):
    name: str
    status: Literal["pass", "fail", "not_applicable"]
    message: str


class ReflectionResult(BaseModel):
    status: Literal["pass", "revise"]
    notes: list[str]


class TraceEvent(BaseModel):
    stage: str
    status: Literal["completed", "skipped", "queued"]
    detail: str


class AdvisoryResponse(BaseModel):
    request_id: str
    farmer_id: str
    intent: Intent
    status: Literal["delivered", "requires_human_review"]
    confidence: float = Field(ge=0, le=1)
    recommendation: str
    explanation: str
    evidence: list[KnowledgeHit]
    reflection: ReflectionResult
    verification: list[VerificationCheck]
    trace: list[TraceEvent]
    hitl_case_id: str | None = None


class MemorySearchRequest(BaseModel):
    farmer_id: str = Field(min_length=3, max_length=64)
    query: str = Field(min_length=1, max_length=500)


class HITLDecisionRequest(BaseModel):
    decision: Literal["approve", "edit_and_approve", "reject"]
    reviewer_note: str = Field(min_length=1, max_length=1_000)
    reviewer_name: str = Field(default="Demo extension officer", min_length=1, max_length=120)
    edited_recommendation: str | None = Field(default=None, max_length=2_000)

    @model_validator(mode="after")
    def require_edited_recommendation(self) -> "HITLDecisionRequest":
        if self.decision == "edit_and_approve" and not self.edited_recommendation:
            raise ValueError("edited_recommendation is required when editing and approving a case.")
        return self


class HITLDecisionAudit(BaseModel):
    """An append-only demo audit event for a human review decision."""

    decision: Literal["approve", "edit_and_approve", "reject"]
    reviewer_name: str
    reviewer_note: str
    edited_recommendation: str | None = None
    decided_at: str


class HITLCase(BaseModel):
    case_id: str
    farmer_id: str
    status: Literal["pending", "approved", "rejected"]
    reason: str
    request_id: str | None = None
    intent: Intent | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    original_recommendation: str | None = None
    original_explanation: str | None = None
    evidence: list[KnowledgeHit] = Field(default_factory=list)
    verification: list[VerificationCheck] = Field(default_factory=list)
    trace: list[TraceEvent] = Field(default_factory=list)
    created_at: str | None = None
    reviewer_note: str | None = None
    edited_recommendation: str | None = None
    decision_history: list[HITLDecisionAudit] = Field(default_factory=list)
