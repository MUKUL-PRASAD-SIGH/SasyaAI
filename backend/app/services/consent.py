"""Credential-free, fail-closed consent preflight for the local demonstrator."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Protocol

from pydantic import ValidationError

from app.models.integration import (
    ConsentPreflightResult,
    ConsentRecord,
    ConsentScope,
    ConsentStatus,
    SourceProvenance,
)
from app.services.memory import SeedRepository


class ConsentAdapterUnavailableError(RuntimeError):
    """Raised when consent cannot be checked safely and access must fail closed."""


class ConsentAdapter(Protocol):
    """Provider-neutral boundary for checking a consent receipt before data access."""

    def preflight(
        self,
        *,
        farmer_id: str,
        purpose: str,
        required_scopes: frozenset[ConsentScope],
        request_id: str | None = None,
    ) -> ConsentPreflightResult | None:
        """Return no result for an unknown farmer, otherwise a fail-closed decision."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SyntheticConsentAdapter:
    """Adapter over validated fixtures; it never makes a network or credentialed call."""

    provider_name = "synthetic_seed"

    def __init__(
        self,
        repository: SeedRepository,
        *,
        clock: Callable[[], datetime] = _utc_now,
        registered_consent_lookup: Callable[[str], dict[str, object] | None] | None = None,
    ) -> None:
        self.repository = repository
        self._clock = clock
        self.available = True
        self._registered_consent_lookup = registered_consent_lookup

    @staticmethod
    def _utc_timestamp(value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ConsentAdapterUnavailableError(
                "Synthetic consent fixture has an unsafe timezone-less timestamp."
            )
        return value.astimezone(timezone.utc)

    def _record_for(
        self, farmer_id: str, raw_consent: dict[str, object], request_id: str | None
    ) -> ConsentRecord:
        now = self._utc_timestamp(self._clock())
        try:
            return ConsentRecord(
                consent_id=str(raw_consent["consent_id"]),
                farmer_id=farmer_id,
                status=raw_consent["status"],
                purpose=str(raw_consent["purpose"]),
                scopes=raw_consent["scopes"],
                granted_at=raw_consent.get("granted_at"),
                expires_at=raw_consent.get("expires_at"),
                revoked_at=raw_consent.get("revoked_at"),
                provenance=SourceProvenance(
                    provider=self.provider_name,
                    source_type="synthetic_fixture",
                    source_record_id=str(raw_consent["consent_id"]),
                    retrieved_at=now,
                    data_as_of=raw_consent.get("granted_at"),
                    freshness="static_demo",
                    request_id=request_id,
                ),
            )
        except (KeyError, TypeError, ValidationError) as error:
            raise ConsentAdapterUnavailableError(
                "Synthetic consent fixture could not be interpreted safely."
            ) from error

    @staticmethod
    def _denied(
        record: ConsentRecord, reason: str, required_scopes: frozenset[ConsentScope]
    ) -> ConsentPreflightResult:
        return ConsentPreflightResult(
            allowed=False,
            reason=reason,
            consent=record,
            required_scopes=required_scopes,
        )

    def preflight(
        self,
        *,
        farmer_id: str,
        purpose: str,
        required_scopes: frozenset[ConsentScope],
        request_id: str | None = None,
    ) -> ConsentPreflightResult | None:
        if not self.available:
            raise ConsentAdapterUnavailableError("Synthetic consent adapter is unavailable.")

        raw_consent = self.repository.get_consent(farmer_id)
        if raw_consent is None and self._registered_consent_lookup is not None:
            raw_consent = self._registered_consent_lookup(farmer_id)
        if raw_consent is None:
            return None
        record = self._record_for(farmer_id, raw_consent, request_id)
        now = record.provenance.retrieved_at

        if raw_consent.get("advisory") is not True:
            return self._denied(record, "advisory_not_granted", required_scopes)
        if record.status is not ConsentStatus.GRANTED:
            return self._denied(record, f"status_{record.status.value}", required_scopes)
        if record.granted_at is None or record.granted_at > now:
            pending_record = record.model_copy(update={"status": ConsentStatus.PENDING})
            return self._denied(pending_record, "grant_not_yet_active", required_scopes)
        if record.revoked_at is not None:
            revoked_record = record.model_copy(update={"status": ConsentStatus.REVOKED})
            return self._denied(revoked_record, "revoked", required_scopes)
        if record.expires_at is not None and record.expires_at <= now:
            expired_record = record.model_copy(update={"status": ConsentStatus.EXPIRED})
            return self._denied(expired_record, "expired", required_scopes)
        if record.purpose != purpose:
            return self._denied(record, "purpose_mismatch", required_scopes)
        if not required_scopes.issubset(record.scopes):
            return self._denied(record, "missing_required_scope", required_scopes)

        return ConsentPreflightResult(
            allowed=True,
            reason="granted",
            consent=record,
            required_scopes=required_scopes,
        )
