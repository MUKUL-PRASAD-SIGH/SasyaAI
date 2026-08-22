"""Public contracts for advisory and review operations."""

from datetime import datetime
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
    image_id: str | None = Field(default=None, min_length=8, max_length=120)


class LoginRequest(BaseModel):
    role: Literal["farmer", "extension_officer", "system_admin"]
    api_key: str | None = Field(default=None, min_length=24, max_length=512)
    email: str | None = Field(default=None, max_length=254)
    otp_code: str | None = Field(default=None, min_length=6, max_length=8)
    auth_method: Literal["api_key", "email_otp"] = "api_key"


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["api_key", "bearer"] = "bearer"
    subject: str
    roles: list[str]
    allowed_farmer_ids: list[str] | None = None
    allowed_regions: list[str] | None = None
    otp_demo_code: str | None = None
    message: str


class GoogleDemoLoginRequest(BaseModel):
    """Continue-with-Google payload. Only email is used; profile fields are ignored."""

    email: str = Field(min_length=5, max_length=254)
    name: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=80)
    district: str | None = Field(default=None, max_length=120)
    preferred_language: str | None = Field(default=None, max_length=8)
    season: str | None = Field(default=None, max_length=40)
    current_crop: str | None = Field(default=None, max_length=80)


class FarmerOnboardingRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=254)
    state: str = Field(min_length=2, max_length=80)
    district: str = Field(min_length=2, max_length=120)
    preferred_language: str = Field(default="en", min_length=2, max_length=8)
    season: str = Field(min_length=2, max_length=40)
    current_crop: str = Field(min_length=2, max_length=80)
    soil_fertility: str = Field(default="moderate", min_length=2, max_length=40)
    water_budget_mm: int = Field(default=250, ge=0, le=10_000)
    budget_inr: int = Field(default=50_000, ge=0, le=10_000_000)
    farm_size_hectares: float = Field(default=1.5, gt=0, le=10_000)
    soil_type: str = Field(default="locally recorded soil", min_length=2, max_length=120)
    irrigation_type: str = Field(default="rainfed", min_length=2, max_length=80)
    latitude: float | None = Field(default=None, ge=6, le=38)
    longitude: float | None = Field(default=None, ge=68, le=98)


class FarmerImageRecord(BaseModel):
    image_id: str
    farmer_id: str
    filename: str
    content_type: str
    uploaded_at: datetime
    analysis_summary: str
    suspected_issue: str | None = None
    confidence: float = Field(ge=0, le=1)


class FeedbackRequest(BaseModel):
    farmer_id: str = Field(min_length=3, max_length=64)
    request_id: str = Field(min_length=3, max_length=100)
    query: str = Field(min_length=3, max_length=1_000)
    recommendation: str = Field(min_length=3, max_length=2_000)
    helpful: bool
    note: str = Field(default="", max_length=1_000)


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


class AgentRun(BaseModel):
    """Safe execution telemetry; never contains hidden chain-of-thought."""

    agent_id: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=2, max_length=120)
    role: str = Field(min_length=2, max_length=160)
    status: Literal["completed", "failed", "skipped"]
    execution_mode: Literal["llm", "deterministic", "tool"]
    duration_ms: int = Field(ge=0, le=300_000)
    summary: str = Field(min_length=2, max_length=500)
    model: str | None = Field(default=None, max_length=120)
    input_sources: list[str] = Field(default_factory=list, max_length=20)
    output_confidence: float | None = Field(default=None, ge=0, le=1)


class AdvisoryResponse(BaseModel):
    request_id: str
    farmer_id: str
    safety_rule_set_version: str = Field(min_length=1, max_length=100)
    intent: Intent
    status: Literal["delivered", "requires_human_review"]
    confidence: float = Field(ge=0, le=1)
    recommendation: str
    explanation: str
    evidence: list[KnowledgeHit]
    reflection: ReflectionResult
    verification: list[VerificationCheck]
    trace: list[TraceEvent]
    agent_runs: list[AgentRun] = Field(default_factory=list)
    hitl_case_id: str | None = None


class MemorySearchRequest(BaseModel):
    farmer_id: str = Field(min_length=3, max_length=64)
    query: str = Field(min_length=1, max_length=500)


class KnowledgeIngestRequest(BaseModel):
    """A reviewed source document eligible for governed Qdrant ingestion."""

    document_id: str | None = Field(default=None, min_length=8, max_length=160)
    collection: Literal["crop_kb", "pest_kb", "scheme_kb"]
    title: str = Field(min_length=3, max_length=300)
    content: str = Field(min_length=20, max_length=20_000)
    state: str = Field(min_length=2, max_length=80)
    source_name: str = Field(min_length=2, max_length=160)
    source_url: str = Field(min_length=8, max_length=1_500)
    source_updated_at: datetime
    reviewed_by: str = Field(min_length=2, max_length=160)
    metadata: dict[str, str | int | float | bool | list[str]] = Field(default_factory=dict)


class AgentDescriptor(BaseModel):
    agent_id: str
    name: str
    role: str
    kind: Literal["manager", "reasoning", "tool", "safety"]
    production_model: str | None = None
    responsibilities: list[str]
    can_write_memory: bool = False


class KnowledgeStats(BaseModel):
    runtime_mode: Literal["demo", "production"]
    collections: dict[str, int]
    total_documents: int = Field(ge=0)
    regions: int = Field(ge=0)
    crops: int = Field(ge=0)


class DemoFarmerSummary(BaseModel):
    farmer_id: str
    name: str
    state: str
    district: str
    preferred_language: str
    current_crop: str
    season: str
    water_budget_mm: int
    farm_size_hectares: float
    soil_fertility: str = "moderate"
    budget_inr: int = 0
    soil_type: str = "locally recorded soil"
    irrigation_type: str = "rainfed"


class MemoryEpisode(BaseModel):
    """A validated local record of an advisory workflow outcome."""

    request_id: str = Field(min_length=1, max_length=100)
    farmer_id: str = Field(min_length=3, max_length=64)
    intent: Intent
    query: str = Field(min_length=3, max_length=1_000)
    outcome: Literal["delivered", "requires_human_review"]
    timestamp: datetime


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
    safety_rule_set_version: str | None = Field(default=None, min_length=1, max_length=100)
    intent: Intent | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    original_recommendation: str | None = None
    original_explanation: str | None = None
    evidence: list[KnowledgeHit] = Field(default_factory=list)
    verification: list[VerificationCheck] = Field(default_factory=list)
    trace: list[TraceEvent] = Field(default_factory=list)
    agent_runs: list[AgentRun] = Field(default_factory=list)
    created_at: str | None = None
    reviewer_note: str | None = None
    edited_recommendation: str | None = None
    decision_history: list[HITLDecisionAudit] = Field(default_factory=list)
