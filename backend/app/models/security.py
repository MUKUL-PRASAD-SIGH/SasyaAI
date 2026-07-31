"""Typed contracts for local security, audit, and data-lifecycle boundaries."""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Role(str, Enum):
    FARMER = "farmer"
    EXTENSION_OFFICER = "extension_officer"
    SYSTEM_ADMIN = "system_admin"


class Principal(BaseModel):
    """Authenticated caller context; credentials are never included in audit output."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    subject: str = Field(min_length=1, max_length=120)
    roles: frozenset[Role] = Field(min_length=1)
    allowed_farmer_ids: frozenset[str] | None = None
    allowed_regions: frozenset[str] | None = None
    authentication_method: Literal["api_key", "session_token", "otp", "development_bypass"]


class ApiKeyCredential(BaseModel):
    """Environment-only API-key record for the local production-readiness gate."""

    model_config = ConfigDict(extra="forbid")

    api_key: str = Field(min_length=24, max_length=512)
    subject: str = Field(min_length=1, max_length=120)
    roles: frozenset[Role] = Field(min_length=1)
    allowed_farmer_ids: frozenset[str] | None = None
    allowed_regions: frozenset[str] | None = None
    email: str | None = Field(default=None, max_length=254)


class AuditEvent(BaseModel):
    """Data-minimised append-only record of a protected API action."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1, max_length=100)
    timestamp: datetime
    actor_subject: str = Field(min_length=1, max_length=120)
    actor_roles: list[Role] = Field(default_factory=list)
    authentication_method: str = Field(min_length=1, max_length=40)
    action: str = Field(min_length=1, max_length=160)
    resource: str = Field(min_length=1, max_length=160)
    outcome: Literal["success", "denied", "error"]
    status_code: int = Field(ge=100, le=599)


class DeletionRequest(BaseModel):
    """A governed request that purges local runtime data and records external follow-up."""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1, max_length=100)
    farmer_id: str = Field(min_length=3, max_length=64)
    requested_by: str = Field(min_length=1, max_length=120)
    requested_at: datetime
    status: Literal["pending_external_cleanup"]
    locally_purged_scopes: list[Literal["advisory_memory", "hitl_cases"]]
    human_action_required: str = Field(min_length=1, max_length=500)
