"""Validated contracts for checked-in synthetic demonstrator data."""

from datetime import date
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.models.integration import ConsentScope, ConsentStatus


class SyntheticConsent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    advisory: bool
    consent_id: str = Field(min_length=1, max_length=120)
    status: ConsentStatus
    purpose: str = Field(min_length=1, max_length=120)
    scopes: frozenset[ConsentScope] = Field(min_length=1)
    granted_at: AwareDatetime | None = None
    expires_at: AwareDatetime | None = None
    revoked_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_lifecycle(self) -> "SyntheticConsent":
        if self.status is ConsentStatus.GRANTED and self.granted_at is None:
            raise ValueError("Granted synthetic consent must include granted_at.")
        if (
            self.granted_at is not None
            and self.expires_at is not None
            and self.expires_at <= self.granted_at
        ):
            raise ValueError("Synthetic consent expiry must follow its grant time.")
        return self


class DigitalTwinSeed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    season: str = Field(min_length=1, max_length=40)
    current_crop: str = Field(min_length=1, max_length=80)
    soil_fertility: str = Field(min_length=1, max_length=40)
    water_budget_mm: int = Field(ge=0, le=10_000)
    budget_inr: int = Field(ge=0, le=10_000_000)
    eligible_schemes: list[str] = Field(default_factory=list)
    weather_alert: bool = False
    farm_size_hectares: float = Field(default=1.5, gt=0, le=10_000)
    soil_type: str = Field(default="locally recorded soil", min_length=2, max_length=120)
    irrigation_type: str = Field(default="rainfed", min_length=2, max_length=80)
    risk_flags: list[str] = Field(default_factory=list)


class SyntheticLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(ge=6, le=38)
    longitude: float = Field(ge=68, le=98)


class FarmerSeed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    farmer_id: str = Field(pattern=r"^AGR_[A-Z]{2}_\d{6}$")
    name: str = Field(min_length=1, max_length=120)
    state: str = Field(min_length=1, max_length=80)
    district: str = Field(min_length=1, max_length=120)
    preferred_language: str = Field(min_length=2, max_length=8)
    synthetic_data: Literal[True]
    consent: SyntheticConsent
    digital_twin: DigitalTwinSeed
    location: SyntheticLocation | None = None


class KnowledgeSource(BaseModel):
    """Provenance metadata for a non-launch synthetic reference record."""

    source_name: str = Field(default="SasyaAI synthetic reference", min_length=2, max_length=160)
    source_url: str = Field(default="", max_length=1_500)
    source_updated_at: date | None = None
    review_status: Literal["synthetic_reference", "domain_reviewed"] = "synthetic_reference"
    tags: list[str] = Field(default_factory=list, max_length=20)


class CropKnowledgeSeed(KnowledgeSource):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=300)
    crop: str = Field(min_length=1, max_length=80)
    region: str = Field(min_length=1, max_length=80)
    soil_type: str = Field(min_length=1, max_length=120)
    water_need_mm: int = Field(ge=0, le=10_000)
    estimated_input_cost_inr: int = Field(ge=0, le=10_000_000)
    guidance: str = Field(min_length=1, max_length=2_000)


class PestKnowledgeSeed(KnowledgeSource):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=300)
    name: str = Field(min_length=1, max_length=120)
    crop: str = Field(min_length=1, max_length=80)
    region: str = Field(min_length=1, max_length=80)
    max_dose_ml_per_l: float | None = Field(default=None, ge=0, le=100)
    guidance: str = Field(min_length=1, max_length=2_000)


class SchemeKnowledgeSeed(KnowledgeSource):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=300)
    name: str = Field(min_length=1, max_length=120)
    state: str = Field(min_length=1, max_length=80)
    deadline: str = Field(min_length=1, max_length=300)
    guidance: str = Field(min_length=1, max_length=2_000)
