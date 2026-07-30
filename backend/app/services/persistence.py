"""PostgreSQL persistence owned by the production Memory boundary.

No production endpoint writes directly to these tables. The advisory workflow
uses this adapter for farmer context, consent receipts, episodic memory, HITL,
and audit events so all state is durable and transactionally updated.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from app.services.memory import HITLDecisionOutcome


class PersistenceUnavailableError(RuntimeError):
    """Raised when durable state cannot be read or committed safely."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PostgresMemoryStore:
    """Synchronous SQLAlchemy Core store; instantiated only in production mode."""

    def __init__(self, database_url: str) -> None:
        if not database_url.startswith("postgresql"):
            raise ValueError("DATABASE_URL must use a PostgreSQL connection string in production mode.")
        try:
            import sqlalchemy as sa
        except ImportError as error:  # pragma: no cover - dependency guard for minimal demo installs
            raise PersistenceUnavailableError(
                "SQLAlchemy is required for the production persistence adapter."
            ) from error

        self.sa = sa
        self.engine = sa.create_engine(database_url, pool_pre_ping=True, future=True)
        self.metadata = sa.MetaData()
        self.farmers = sa.Table(
            "farmers",
            self.metadata,
            sa.Column("farmer_id", sa.String(64), primary_key=True),
            sa.Column("profile", sa.JSON, nullable=False),
            sa.Column("version", sa.Integer, nullable=False, server_default="1"),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        self.consents = sa.Table(
            "consent_receipts",
            self.metadata,
            sa.Column("farmer_id", sa.String(64), primary_key=True),
            sa.Column("receipt", sa.JSON, nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        self.episodes = sa.Table(
            "advisory_episodes",
            self.metadata,
            sa.Column("request_id", sa.String(100), primary_key=True),
            sa.Column("farmer_id", sa.String(64), nullable=False, index=True),
            sa.Column("episode", sa.JSON, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, index=True),
        )
        self.hitl_cases = sa.Table(
            "hitl_cases",
            self.metadata,
            sa.Column("case_id", sa.String(100), primary_key=True),
            sa.Column("farmer_id", sa.String(64), nullable=False, index=True),
            sa.Column("case_data", sa.JSON, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, index=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        self.audit_events = sa.Table(
            "audit_events",
            self.metadata,
            sa.Column("event_id", sa.String(100), primary_key=True),
            sa.Column("event", sa.JSON, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, index=True),
        )
        self.deletion_requests = sa.Table(
            "deletion_requests",
            self.metadata,
            sa.Column("request_id", sa.String(100), primary_key=True),
            sa.Column("farmer_id", sa.String(64), nullable=False, index=True),
            sa.Column("request", sa.JSON, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        try:
            self.metadata.create_all(self.engine)
        except Exception as error:
            raise PersistenceUnavailableError("PostgreSQL schema initialisation failed.") from error

    def _run(self, operation):
        try:
            return operation()
        except PersistenceUnavailableError:
            raise
        except Exception as error:
            raise PersistenceUnavailableError("PostgreSQL state is unavailable; no advisory was delivered.") from error

    def get_farmer(self, farmer_id: str) -> dict[str, Any] | None:
        def operation():
            with self.engine.connect() as connection:
                value = connection.execute(
                    self.sa.select(self.farmers.c.profile).where(self.farmers.c.farmer_id == farmer_id)
                ).scalar_one_or_none()
            return copy.deepcopy(value) if value is not None else None

        return self._run(operation)

    def has_farmer(self, farmer_id: str) -> bool:
        return self.get_farmer(farmer_id) is not None

    def get_consent(self, farmer_id: str) -> dict[str, Any] | None:
        def operation():
            with self.engine.connect() as connection:
                value = connection.execute(
                    self.sa.select(self.consents.c.receipt).where(self.consents.c.farmer_id == farmer_id)
                ).scalar_one_or_none()
            return copy.deepcopy(value) if value is not None else None

        return self._run(operation)

    def upsert_farmer(self, farmer_id: str, profile: dict[str, Any]) -> None:
        """Ingestion-only helper; callers must validate consent before invoking it."""

        def operation():
            now = _utc_now()
            with self.engine.begin() as connection:
                exists = connection.execute(
                    self.sa.select(self.farmers.c.farmer_id).where(self.farmers.c.farmer_id == farmer_id)
                ).scalar_one_or_none()
                if exists:
                    connection.execute(
                        self.sa.update(self.farmers)
                        .where(self.farmers.c.farmer_id == farmer_id)
                        .values(profile=profile, updated_at=now, version=self.farmers.c.version + 1)
                    )
                else:
                    connection.execute(
                        self.sa.insert(self.farmers).values(
                            farmer_id=farmer_id, profile=profile, updated_at=now
                        )
                    )

        self._run(operation)

    def upsert_consent(self, farmer_id: str, receipt: dict[str, Any]) -> None:
        def operation():
            now = _utc_now()
            with self.engine.begin() as connection:
                exists = connection.execute(
                    self.sa.select(self.consents.c.farmer_id).where(self.consents.c.farmer_id == farmer_id)
                ).scalar_one_or_none()
                statement = (
                    self.sa.update(self.consents)
                    .where(self.consents.c.farmer_id == farmer_id)
                    .values(receipt=receipt, updated_at=now)
                    if exists
                    else self.sa.insert(self.consents).values(
                        farmer_id=farmer_id, receipt=receipt, updated_at=now
                    )
                )
                connection.execute(statement)

        self._run(operation)

    def append_episode(self, episode: dict[str, Any]) -> None:
        def operation():
            with self.engine.begin() as connection:
                connection.execute(
                    self.sa.insert(self.episodes).values(
                        request_id=str(episode["request_id"]),
                        farmer_id=str(episode["farmer_id"]),
                        episode=episode,
                        created_at=_utc_now(),
                    )
                )

        self._run(operation)

    def search_episodes(self, farmer_id: str, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Scoped durable episode read. Semantic search lives in Qdrant; this is the audit view."""

        def operation():
            with self.engine.connect() as connection:
                records = connection.execute(
                    self.sa.select(self.episodes.c.episode)
                    .where(self.episodes.c.farmer_id == farmer_id)
                    .order_by(self.episodes.c.created_at.desc())
                    .limit(limit)
                ).scalars().all()
            terms = {term.lower() for term in query.split() if len(term) > 2}
            return [
                copy.deepcopy(record) | {"score": sum(term in str(record).lower() for term in terms)}
                for record in records
            ]

        return self._run(operation)

    def enqueue_hitl(self, case: dict[str, Any]) -> None:
        def operation():
            now = _utc_now()
            with self.engine.begin() as connection:
                connection.execute(
                    self.sa.insert(self.hitl_cases).values(
                        case_id=str(case["case_id"]),
                        farmer_id=str(case["farmer_id"]),
                        case_data=case,
                        created_at=now,
                        updated_at=now,
                    )
                )

        self._run(operation)

    def get_hitl(self, case_id: str) -> dict[str, Any] | None:
        def operation():
            with self.engine.connect() as connection:
                case = connection.execute(
                    self.sa.select(self.hitl_cases.c.case_data).where(self.hitl_cases.c.case_id == case_id)
                ).scalar_one_or_none()
            return copy.deepcopy(case) if case is not None else None

        return self._run(operation)

    def list_hitl(self) -> list[dict[str, Any]]:
        def operation():
            with self.engine.connect() as connection:
                records = connection.execute(
                    self.sa.select(self.hitl_cases.c.case_data).order_by(self.hitl_cases.c.created_at.desc())
                ).scalars().all()
            return [copy.deepcopy(record) for record in records]

        return self._run(operation)

    def decide_hitl(
        self,
        case_id: str,
        decision: str,
        note: str,
        reviewer_name: str,
        edited_recommendation: str | None,
    ) -> HITLDecisionOutcome:
        """Lock the case row so exactly one reviewer can transition it."""

        def operation():
            with self.engine.begin() as connection:
                case = connection.execute(
                    self.sa.select(self.hitl_cases.c.case_data)
                    .where(self.hitl_cases.c.case_id == case_id)
                    .with_for_update()
                ).scalar_one_or_none()
                if case is None:
                    return HITLDecisionOutcome(state="not_found")
                case = copy.deepcopy(case)
                if case.get("status") != "pending":
                    return HITLDecisionOutcome(state="not_pending")
                blocking = tuple(
                    str(check.get("name"))
                    for check in case.get("verification", [])
                    if check.get("status") == "fail"
                )
                if blocking and decision != "reject":
                    return HITLDecisionOutcome(state="safety_blocked", case=case, blocking_checks=blocking)
                history = list(case.get("decision_history", []))
                history.append(
                    {
                        "decision": decision,
                        "reviewer_name": reviewer_name,
                        "reviewer_note": note,
                        "edited_recommendation": edited_recommendation,
                        "decided_at": _utc_now().isoformat(),
                    }
                )
                updated = {
                    **case,
                    "status": "rejected" if decision == "reject" else "approved",
                    "reviewer_note": note,
                    "edited_recommendation": edited_recommendation,
                    "decision_history": history,
                }
                connection.execute(
                    self.sa.update(self.hitl_cases)
                    .where(self.hitl_cases.c.case_id == case_id)
                    .values(case_data=updated, updated_at=_utc_now())
                )
                return HITLDecisionOutcome(state="updated", case=updated)

        return self._run(operation)

    def append_audit_event(self, event: dict[str, Any]) -> None:
        def operation():
            with self.engine.begin() as connection:
                connection.execute(
                    self.sa.insert(self.audit_events).values(
                        event_id=str(event["event_id"]), event=event, created_at=_utc_now()
                    )
                )

        self._run(operation)

    def list_audit_events(self, limit: int = 100) -> list[dict[str, Any]]:
        def operation():
            with self.engine.connect() as connection:
                records = connection.execute(
                    self.sa.select(self.audit_events.c.event)
                    .order_by(self.audit_events.c.created_at.desc())
                    .limit(limit)
                ).scalars().all()
            return [copy.deepcopy(record) for record in records]

        return self._run(operation)

    def append_deletion_request(self, request: dict[str, Any]) -> None:
        def operation():
            with self.engine.begin() as connection:
                connection.execute(
                    self.sa.insert(self.deletion_requests).values(
                        request_id=str(request["request_id"]),
                        farmer_id=str(request["farmer_id"]),
                        request=request,
                        created_at=_utc_now(),
                    )
                )

        self._run(operation)

    def purge_farmer_runtime_data(self, farmer_id: str) -> dict[str, int]:
        """Delete derived advisory state, never the governed farmer source record."""

        def operation():
            with self.engine.begin() as connection:
                episodes_result = connection.execute(
                    self.sa.delete(self.episodes).where(self.episodes.c.farmer_id == farmer_id)
                )
                cases_result = connection.execute(
                    self.sa.delete(self.hitl_cases).where(self.hitl_cases.c.farmer_id == farmer_id)
                )
            return {
                "advisory_memory": int(episodes_result.rowcount or 0),
                "hitl_cases": int(cases_result.rowcount or 0),
            }

        return self._run(operation)


class PostgresAuditLog:
    """Compatibility adapter exposing the audit-log contract used by the API middleware."""

    def __init__(self, store: PostgresMemoryStore) -> None:
        self.store = store

    def append(self, event: dict[str, Any]) -> None:
        self.store.append_audit_event(event)

    def list(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.store.list_audit_events(limit)


class PostgresDeletionRequestStore:
    """Compatibility adapter for durable deletion-request receipts."""

    def __init__(self, store: PostgresMemoryStore) -> None:
        self.store = store

    def append(self, request: dict[str, Any]) -> None:
        self.store.append_deletion_request(request)
