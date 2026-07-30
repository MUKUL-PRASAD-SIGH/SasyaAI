"""Seed-data retrieval and local persistence owned by the Memory Agent boundary."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class SeedRepository:
    """Read-only adapter over checked-in synthetic seed data.

    This provides the same ownership boundary that Qdrant and PostgreSQL will
    use later. It is intentionally deterministic for a credential-free demo.
    """

    def __init__(self, seed_data_dir: Path) -> None:
        self.seed_data_dir = seed_data_dir

    def _load_json(self, relative_path: str) -> Any:
        with (self.seed_data_dir / relative_path).open(encoding="utf-8") as file:
            return json.load(file)

    def get_farmer(self, farmer_id: str) -> dict[str, Any] | None:
        for path in sorted((self.seed_data_dir / "farmers").glob("*.json")):
            farmer = self._load_json(f"farmers/{path.name}")
            if farmer["farmer_id"] == farmer_id:
                return farmer
        return None

    def list_knowledge(self, collection: str) -> list[dict[str, Any]]:
        """Return a copy of a seed collection for deterministic filtering."""

        return list(self._load_json(f"kb/{collection}.json"))

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


class LocalMemoryStore:
    """Append-only runtime episode store used only through the Memory boundary."""

    def __init__(self, runtime_dir: Path) -> None:
        self.runtime_dir = runtime_dir
        self.path = runtime_dir / "farmer_memory.json"

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as file:
            return json.load(file)

    def _write(self, episodes: list[dict[str, Any]]) -> None:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(episodes, file, ensure_ascii=False, indent=2)

    def append(self, episode: dict[str, Any]) -> None:
        episodes = self._read()
        episodes.append(episode)
        self._write(episodes)

    def search(self, farmer_id: str, query: str) -> list[dict[str, Any]]:
        query_terms = {term.lower() for term in query.split() if len(term) > 2}
        matches = []
        for episode in self._read():
            if episode["farmer_id"] != farmer_id:
                continue
            text = " ".join(str(value) for value in episode.values()).lower()
            score = sum(term in text for term in query_terms)
            if score:
                matches.append(episode | {"score": score})
        return sorted(matches, key=lambda item: item["score"], reverse=True)[:5]


class HITLQueue:
    """Local queue that can later be replaced by a durable review service."""

    def __init__(self, runtime_dir: Path) -> None:
        self.runtime_dir = runtime_dir
        self.path = runtime_dir / "hitl_queue.json"

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as file:
            cases = json.load(file)
        # Preserve compatibility with cases written by the first demo release.
        return [
            {
                **case,
                "original_recommendation": case.get(
                    "original_recommendation", case.get("recommendation")
                ),
                "decision_history": case.get("decision_history", []),
            }
            for case in cases
        ]

    def _write(self, cases: list[dict[str, Any]]) -> None:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(cases, file, ensure_ascii=False, indent=2)

    def enqueue(self, case: dict[str, Any]) -> None:
        cases = self._read()
        cases.append(case)
        self._write(cases)

    def get(self, case_id: str) -> dict[str, Any] | None:
        return next((case for case in self._read() if case["case_id"] == case_id), None)

    def list(self) -> list[dict[str, Any]]:
        """Return newest review cases first without exposing a write path."""

        return sorted(
            self._read(),
            key=lambda case: str(case.get("created_at", "")),
            reverse=True,
        )

    def decide(
        self,
        case_id: str,
        decision: str,
        note: str,
        reviewer_name: str,
        edited_recommendation: str | None,
    ) -> dict[str, Any] | None:
        cases = self._read()
        for case in cases:
            if case["case_id"] != case_id:
                continue
            if case["status"] != "pending":
                return None

            audit_event = {
                "decision": decision,
                "reviewer_name": reviewer_name,
                "reviewer_note": note,
                "edited_recommendation": edited_recommendation,
                "decided_at": datetime.now(timezone.utc).isoformat(),
            }
            case["status"] = "rejected" if decision == "reject" else "approved"
            case["reviewer_note"] = note
            case["edited_recommendation"] = edited_recommendation
            case.setdefault("decision_history", []).append(audit_event)
            self._write(cases)
            return case
        return None
