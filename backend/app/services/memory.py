"""Validated seed access and safe local persistence behind the Memory boundary."""

from __future__ import annotations

import copy
import json
import os
import tempfile
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Literal

from filelock import FileLock, Timeout
from pydantic import BaseModel, ValidationError

from app.models.advisory import HITLCase, MemoryEpisode
from app.models.security import AuditEvent, DeletionRequest
from app.models.seed import (
    CropKnowledgeSeed,
    FarmerSeed,
    PestKnowledgeSeed,
    SchemeKnowledgeSeed,
)


class SeedDataError(RuntimeError):
    """Raised when checked-in demonstrator data is missing or invalid."""


class RuntimeStateError(RuntimeError):
    """Raised when local demo state cannot be safely read or persisted."""


def _parse_runtime_timestamp(value: object) -> datetime:
    """Parse persisted ISO timestamps consistently on Python 3.10+ runtimes."""

    timestamp = str(value)
    if timestamp.endswith("Z"):
        timestamp = f"{timestamp[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(timestamp)
    except ValueError as error:
        raise RuntimeStateError("Local runtime state has an invalid timestamp.") from error
    if parsed.tzinfo is None:
        raise RuntimeStateError("Local runtime state has a timezone-less timestamp.")
    return parsed.astimezone(timezone.utc)


class SeedRepository:
    """Read-only, validated adapter over checked-in synthetic seed data."""

    _knowledge_models: dict[str, type[BaseModel]] = {
        "crops": CropKnowledgeSeed,
        "pests": PestKnowledgeSeed,
        "schemes": SchemeKnowledgeSeed,
    }

    def __init__(self, seed_data_dir: Path) -> None:
        self.seed_data_dir = seed_data_dir
        self._farmers, self._consents = self._load_farmers()
        self._knowledge = {
            collection: self._load_knowledge(collection, model)
            for collection, model in self._knowledge_models.items()
        }

    def _load_json(self, relative_path: str) -> Any:
        path = self.seed_data_dir / relative_path
        try:
            with path.open(encoding="utf-8") as file:
                return json.load(file)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise SeedDataError(f"Could not load synthetic seed data from {relative_path}.") from error

    @staticmethod
    def _validate_record(
        model: type[BaseModel], record: Any, label: str
    ) -> dict[str, Any]:
        try:
            return model.model_validate(record).model_dump(mode="json")
        except ValidationError as error:
            raise SeedDataError(f"Invalid {label} seed record.") from error

    def _load_farmers(self) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
        farmers_dir = self.seed_data_dir / "farmers"
        if not farmers_dir.is_dir():
            raise SeedDataError("Synthetic farmer seed directory is missing.")

        farmer_paths = sorted(farmers_dir.glob("*.json"))
        if not farmer_paths:
            raise SeedDataError("No synthetic farmer seed records were found.")

        farmers: dict[str, dict[str, Any]] = {}
        consents: dict[str, dict[str, Any]] = {}
        for path in farmer_paths:
            relative_path = path.relative_to(self.seed_data_dir).as_posix()
            farmer = self._validate_record(
                FarmerSeed,
                self._load_json(relative_path),
                f"farmer ({path.name})",
            )
            farmer_id = str(farmer["farmer_id"])
            if farmer_id in farmers:
                raise SeedDataError(f"Duplicate synthetic farmer ID: {farmer_id}.")
            farmers[farmer_id] = farmer
            # Keep a data-minimised index so consent can be checked before profile access.
            consents[farmer_id] = copy.deepcopy(farmer["consent"])
        return farmers, consents

    def _load_knowledge(
        self, collection: str, model: type[BaseModel]
    ) -> list[dict[str, Any]]:
        relative_path = f"kb/{collection}.json"
        records = self._load_json(relative_path)
        if not isinstance(records, list) or not records:
            raise SeedDataError(f"Knowledge collection {collection} must contain at least one record.")
        return [
            self._validate_record(model, record, f"{collection} ({index})")
            for index, record in enumerate(records, start=1)
        ]

    def get_farmer(self, farmer_id: str) -> dict[str, Any] | None:
        farmer = self._farmers.get(farmer_id)
        return copy.deepcopy(farmer) if farmer is not None else None

    def has_farmer(self, farmer_id: str) -> bool:
        """Check fixture identity without reading a farmer profile."""

        return farmer_id in self._farmers

    def get_consent(self, farmer_id: str) -> dict[str, Any] | None:
        """Return only the validated synthetic consent fixture for a farmer."""

        consent = self._consents.get(farmer_id)
        return copy.deepcopy(consent) if consent is not None else None

    def list_farmer_summaries(self) -> list[dict[str, Any]]:
        """Return non-sensitive fields from synthetic fixtures for the demo UI."""

        summaries = []
        for farmer in self._farmers.values():
            twin = farmer["digital_twin"]
            summaries.append(
                {
                    "farmer_id": farmer["farmer_id"],
                    "name": farmer["name"],
                    "state": farmer["state"],
                    "district": farmer["district"],
                    "preferred_language": farmer["preferred_language"],
                    "current_crop": twin["current_crop"],
                    "season": twin["season"],
                    "water_budget_mm": twin["water_budget_mm"],
                    "farm_size_hectares": twin["farm_size_hectares"],
                }
            )
        return sorted(summaries, key=lambda item: (item["state"], item["district"]))

    def list_knowledge(self, collection: str) -> list[dict[str, Any]]:
        try:
            return copy.deepcopy(self._knowledge[collection])
        except KeyError as error:
            raise SeedDataError(f"Unknown seed knowledge collection: {collection}.") from error

    def search_knowledge(self, collection: str, query: str, limit: int = 3) -> list[dict[str, Any]]:
        records = self.list_knowledge(collection)
        query_terms = {term.lower() for term in query.split() if len(term) > 2}

        ranked: list[tuple[float, dict[str, Any]]] = []
        for record in records:
            searchable_text = " ".join(str(value) for value in record.values()).lower()
            overlap = sum(term in searchable_text for term in query_terms)
            score = round(min(0.95, 0.45 + (0.15 * overlap)), 2)
            ranked.append((score, record))

        return [
            record | {"_score": score}
            for score, record in sorted(ranked, reverse=True, key=lambda item: item[0])[:limit]
        ]

    def knowledge_stats(self) -> dict[str, object]:
        collection_names = {
            "crops": "crop_kb",
            "pests": "pest_kb",
            "schemes": "scheme_kb",
        }
        collections = {
            collection_names[name]: len(records) for name, records in self._knowledge.items()
        }
        regions = {
            str(record.get("region", record.get("state", "all")))
            for records in self._knowledge.values()
            for record in records
            if str(record.get("region", record.get("state", "all"))).lower() != "all"
        }
        crops = {
            str(record["crop"])
            for collection in ("crops", "pests")
            for record in self._knowledge[collection]
            if record.get("crop")
        }
        return {
            "collections": collections,
            "total_documents": sum(collections.values()),
            "regions": len(regions),
            "crops": len(crops),
        }


class _JsonListStore:
    """A same-process locked, atomic JSON-list store for local demo state."""

    def __init__(self, runtime_dir: Path, filename: str) -> None:
        self.runtime_dir = runtime_dir
        self.path = runtime_dir / filename
        self._lock = RLock()
        self._file_lock = FileLock(runtime_dir / f".{filename}.lock", timeout=3)

    @contextmanager
    def _locked_transaction(self):
        """Serialize local read/modify/write work across threads and processes."""

        with self._lock:
            try:
                self.runtime_dir.mkdir(parents=True, exist_ok=True)
                with self._file_lock:
                    yield
            except Timeout as error:
                raise RuntimeStateError("Local demo state is busy; retry shortly.") from error
            except OSError as error:
                raise RuntimeStateError("Local demo state cannot be accessed safely.") from error

    def _read_unlocked(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            with self.path.open(encoding="utf-8") as file:
                payload = json.load(file)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RuntimeStateError("Local demo state cannot be read safely.") from error

        if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
            raise RuntimeStateError("Local demo state has an invalid JSON structure.")
        return payload

    def _write_unlocked(self, records: list[dict[str, Any]]) -> None:
        temporary_path: Path | None = None
        try:
            self.runtime_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.runtime_dir,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                json.dump(records, temporary_file, ensure_ascii=False, indent=2)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_path, self.path)
            temporary_path = None
        except (OSError, TypeError, ValueError) as error:
            raise RuntimeStateError("Local demo state cannot be persisted safely.") from error
        finally:
            if temporary_path is not None:
                with suppress(OSError):
                    temporary_path.unlink(missing_ok=True)


class LocalMemoryStore(_JsonListStore):
    """Append-only runtime episode store accessed only through the Memory boundary."""

    def __init__(self, runtime_dir: Path) -> None:
        super().__init__(runtime_dir, "farmer_memory.json")

    @staticmethod
    def _validate_episode(episode: dict[str, Any]) -> dict[str, Any]:
        try:
            return MemoryEpisode.model_validate(episode).model_dump(mode="json")
        except ValidationError as error:
            raise RuntimeStateError("Local advisory memory has an invalid episode.") from error

    def _episodes_unlocked(self) -> list[dict[str, Any]]:
        return [self._validate_episode(episode) for episode in self._read_unlocked()]

    def append(self, episode: dict[str, Any]) -> None:
        validated_episode = self._validate_episode(episode)
        with self._locked_transaction():
            episodes = self._episodes_unlocked()
            episodes.append(validated_episode)
            self._write_unlocked(episodes)

    def search(self, farmer_id: str, query: str) -> list[dict[str, Any]]:
        query_terms = {term.lower() for term in query.split() if len(term) > 2}
        with self._locked_transaction():
            episodes = self._episodes_unlocked()

        matches = []
        for episode in episodes:
            if episode["farmer_id"] != farmer_id:
                continue
            text = " ".join(str(value) for value in episode.values()).lower()
            score = sum(term in text for term in query_terms)
            if score:
                matches.append(episode | {"score": score})
        return sorted(matches, key=lambda item: item["score"], reverse=True)[:5]

    def purge_farmer(self, farmer_id: str) -> int:
        """Remove only local runtime episodes for a governed deletion request."""

        with self._locked_transaction():
            episodes = self._episodes_unlocked()
            retained = [episode for episode in episodes if episode["farmer_id"] != farmer_id]
            removed = len(episodes) - len(retained)
            if removed:
                self._write_unlocked(retained)
            return removed

    def purge_before(self, cutoff: datetime) -> int:
        """Apply the configured local retention period to runtime episodes."""

        with self._locked_transaction():
            episodes = self._episodes_unlocked()
            retained = [
                episode
                for episode in episodes
                if _parse_runtime_timestamp(episode["timestamp"]) >= cutoff
            ]
            removed = len(episodes) - len(retained)
            if removed:
                self._write_unlocked(retained)
            return removed


@dataclass(frozen=True)
class HITLDecisionOutcome:
    state: Literal["updated", "not_found", "not_pending", "safety_blocked"]
    case: dict[str, Any] | None = None
    blocking_checks: tuple[str, ...] = ()


class HITLQueue(_JsonListStore):
    """Local review queue with atomic in-process decision transitions."""

    def __init__(self, runtime_dir: Path) -> None:
        super().__init__(runtime_dir, "hitl_queue.json")

    @staticmethod
    def _normalise_case(case: dict[str, Any]) -> dict[str, Any]:
        legacy_case = {
            **case,
            "original_recommendation": case.get(
                "original_recommendation", case.get("recommendation")
            ),
            "decision_history": case.get("decision_history", []),
        }
        try:
            return HITLCase.model_validate(legacy_case).model_dump(mode="json")
        except ValidationError as error:
            raise RuntimeStateError("Local HITL queue has an invalid case.") from error

    def _cases_unlocked(self) -> list[dict[str, Any]]:
        cases = [self._normalise_case(case) for case in self._read_unlocked()]
        case_ids = [str(case["case_id"]) for case in cases]
        if len(case_ids) != len(set(case_ids)):
            raise RuntimeStateError("Local HITL queue contains duplicate case IDs.")
        return cases

    def enqueue(self, case: dict[str, Any]) -> None:
        validated_case = self._normalise_case(case)
        with self._locked_transaction():
            cases = self._cases_unlocked()
            if any(existing["case_id"] == validated_case["case_id"] for existing in cases):
                raise RuntimeStateError("A local HITL case already uses this ID.")
            cases.append(validated_case)
            self._write_unlocked(cases)

    def get(self, case_id: str) -> dict[str, Any] | None:
        with self._locked_transaction():
            return next(
                (copy.deepcopy(case) for case in self._cases_unlocked() if case["case_id"] == case_id),
                None,
            )

    def list(self) -> list[dict[str, Any]]:
        """Return newest review cases first without exposing a write path."""

        with self._locked_transaction():
            cases = self._cases_unlocked()
        return sorted(cases, key=lambda case: str(case.get("created_at", "")), reverse=True)

    def purge_farmer(self, farmer_id: str) -> int:
        """Remove only local runtime HITL cases for a governed deletion request."""

        with self._locked_transaction():
            cases = self._cases_unlocked()
            retained = [case for case in cases if case["farmer_id"] != farmer_id]
            removed = len(cases) - len(retained)
            if removed:
                self._write_unlocked(retained)
            return removed

    def purge_before(self, cutoff: datetime) -> int:
        """Apply the configured local retention period to runtime review cases."""

        with self._locked_transaction():
            cases = self._cases_unlocked()
            retained = [
                case
                for case in cases
                if not case["created_at"] or _parse_runtime_timestamp(case["created_at"]) >= cutoff
            ]
            removed = len(cases) - len(retained)
            if removed:
                self._write_unlocked(retained)
            return removed

    def decide(
        self,
        case_id: str,
        decision: str,
        note: str,
        reviewer_name: str,
        edited_recommendation: str | None,
    ) -> HITLDecisionOutcome:
        with self._locked_transaction():
            cases = self._cases_unlocked()
            for index, case in enumerate(cases):
                if case["case_id"] != case_id:
                    continue
                if case["status"] != "pending":
                    return HITLDecisionOutcome(state="not_pending")
                blocking_checks = tuple(
                    str(check["name"])
                    for check in case["verification"]
                    if check["status"] == "fail"
                )
                if blocking_checks and decision != "reject":
                    return HITLDecisionOutcome(
                        state="safety_blocked",
                        case=copy.deepcopy(case),
                        blocking_checks=blocking_checks,
                    )

                audit_event = {
                    "decision": decision,
                    "reviewer_name": reviewer_name,
                    "reviewer_note": note,
                    "edited_recommendation": edited_recommendation,
                    "decided_at": datetime.now(timezone.utc).isoformat(),
                }
                updated_case = {
                    **case,
                    "status": "rejected" if decision == "reject" else "approved",
                    "reviewer_note": note,
                    "edited_recommendation": edited_recommendation,
                    "decision_history": [*case["decision_history"], audit_event],
                }
                cases[index] = self._normalise_case(updated_case)
                self._write_unlocked(cases)
                return HITLDecisionOutcome(state="updated", case=copy.deepcopy(cases[index]))

        return HITLDecisionOutcome(state="not_found")


class LocalAuditLog(_JsonListStore):
    """Append-only, data-minimised audit metadata for protected API actions."""

    def __init__(self, runtime_dir: Path) -> None:
        super().__init__(runtime_dir, "audit_log.json")

    @staticmethod
    def _validate_event(event: dict[str, Any]) -> dict[str, Any]:
        try:
            return AuditEvent.model_validate(event).model_dump(mode="json")
        except ValidationError as error:
            raise RuntimeStateError("Local audit log has an invalid event.") from error

    def append(self, event: dict[str, Any]) -> None:
        validated_event = self._validate_event(event)
        with self._locked_transaction():
            events = [self._validate_event(item) for item in self._read_unlocked()]
            events.append(validated_event)
            self._write_unlocked(events)

    def list(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._locked_transaction():
            events = [self._validate_event(item) for item in self._read_unlocked()]
        return sorted(events, key=lambda event: str(event["timestamp"]), reverse=True)[:limit]


class LocalDeletionRequestStore(_JsonListStore):
    """Append-only record of local purges that need external-system follow-up."""

    def __init__(self, runtime_dir: Path) -> None:
        super().__init__(runtime_dir, "deletion_requests.json")

    @staticmethod
    def _validate_request(request: dict[str, Any]) -> dict[str, Any]:
        try:
            return DeletionRequest.model_validate(request).model_dump(mode="json")
        except ValidationError as error:
            raise RuntimeStateError("Local deletion request has an invalid record.") from error

    def append(self, request: dict[str, Any]) -> None:
        validated_request = self._validate_request(request)
        with self._locked_transaction():
            requests = [self._validate_request(item) for item in self._read_unlocked()]
            requests.append(validated_request)
            self._write_unlocked(requests)
