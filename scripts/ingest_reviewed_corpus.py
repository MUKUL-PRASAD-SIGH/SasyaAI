"""Validate and idempotently ingest a reviewed JSONL corpus into production."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
KnowledgeIngestRequest = importlib.import_module(
    "app.models.advisory"
).KnowledgeIngestRequest


def stable_document_id(record: dict[str, Any]) -> str:
    identity = "\n".join(
        str(record.get(field, "")).strip()
        for field in ("collection", "state", "source_url", "title")
    )
    return f"sha256:{hashlib.sha256(identity.encode('utf-8')).hexdigest()}"


def validated_documents(path: Path) -> Iterator[Any]:
    with path.open(encoding="utf-8") as source:
        for line_number, raw_line in enumerate(source, start=1):
            if not raw_line.strip():
                continue
            try:
                payload = json.loads(raw_line)
                if not isinstance(payload, dict):
                    raise ValueError("record must be a JSON object")
                payload.setdefault("document_id", stable_document_id(payload))
                yield KnowledgeIngestRequest.model_validate(payload)
            except (json.JSONDecodeError, ValidationError, ValueError) as error:
                raise ValueError(f"Invalid record at line {line_number}: {error}") from error


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate or ingest reviewer-approved SasyaAI knowledge JSONL."
    )
    parser.add_argument("path", type=Path, help="UTF-8 JSONL input file")
    parser.add_argument(
        "--api-base-url",
        default=os.getenv("SASYAAI_API_BASE_URL", "http://127.0.0.1:8000"),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate every record without making API calls",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.path.is_file():
        raise SystemExit(f"Input file does not exist: {args.path}")

    api_key = os.getenv("SASYAAI_ADMIN_API_KEY", "").strip()
    if not args.dry_run and not api_key:
        raise SystemExit(
            "SASYAAI_ADMIN_API_KEY is required for ingestion; use --dry-run to validate only."
        )

    count = 0
    client = httpx.Client(
        base_url=str(args.api_base_url).rstrip("/"),
        headers={"X-API-Key": api_key} if api_key else {},
        timeout=30,
    )
    try:
        for document in validated_documents(args.path):
            if not args.dry_run:
                response = client.post(
                    "/api/v1/knowledge/documents",
                    json=document.model_dump(mode="json"),
                )
                response.raise_for_status()
                if response.json().get("document_id") != document.document_id:
                    raise RuntimeError("The API returned an unexpected document identifier.")
            count += 1
            if count % 100 == 0:
                print(f"Validated{' and ingested' if not args.dry_run else ''} {count} records.")
    finally:
        client.close()

    action = "Validated and ingested" if not args.dry_run else "Validated"
    print(f"{action} {count} reviewed records from {args.path}.")


if __name__ == "__main__":
    main()
