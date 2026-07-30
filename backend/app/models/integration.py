"""Provider-neutral contracts for future consent-gated data adapters."""

from enum import Enum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class ConsentStatus(str, Enum):
    PENDING = "pending"
    GRANTED = "granted"
    DENIED = "denied"
    REVOKED = "revoked"
    EXPIRED = "expired"


class ConsentScope(str, Enum):
    FARMER_PROFILE = "farmer_profile"
    ADVISORY = "advisory"
    ADVISORY_MEMORY = "advisory_memory"


class SourceProvenance(BaseModel):
    """Minimal source and freshness context carried by an adapter result."""

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1, max_length=120)
    source_type: str = Field(min_length=1, max_length=40)
    source_record_id: str = Field(min_length=1, max_length=160)
    retrieved_at: AwareDatetime
    data_as_of: AwareDatetime | None = None
    freshness: str = Field(min_length=1, max_length=40)
    degraded: bool = False
    fallback_used: bool = False
    request_id: str | None = Field(default=None, max_length=100)


class ConsentRecord(BaseModel):
    """A data-minimised consent record returned by an adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    consent_id: str = Field(min_length=1, max_length=120)
    farmer_id: str = Field(min_length=3, max_length=64)
    status: ConsentStatus
    purpose: str = Field(min_length=1, max_length=120)
    scopes: frozenset[ConsentScope] = Field(default_factory=frozenset)
    granted_at: AwareDatetime | None = None
    expires_at: AwareDatetime | None = None
    revoked_at: AwareDatetime | None = None
    provenance: SourceProvenance


class ConsentPreflightResult(BaseModel):
    """A fail-closed decision made before any protected profile read."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    allowed: bool
    reason: str = Field(min_length=1, max_length=160)
    consent: ConsentRecord
    required_scopes: frozenset[ConsentScope] = Field(default_factory=frozenset)

    @model_validator(mode="after")
    def validate_granted_result(self) -> "ConsentPreflightResult":
        """Prevent a caller from constructing a contradictory granted result."""

        if not self.allowed:
            return self

        if self.consent.status is not ConsentStatus.GRANTED:
            raise ValueError("A granted preflight result requires granted consent status.")
        if self.consent.revoked_at is not None:
            raise ValueError("A granted preflight result cannot include a revocation timestamp.")
        if ConsentScope.ADVISORY not in self.consent.scopes:
            raise ValueError("A granted preflight result requires advisory scope.")
        if not self.required_scopes.issubset(self.consent.scopes):
            raise ValueError("A granted preflight result is missing a required scope.")
        if (
            self.consent.expires_at is not None
            and self.consent.expires_at <= self.consent.provenance.retrieved_at
        ):
            raise ValueError("A granted preflight result cannot use expired consent.")
        return self
