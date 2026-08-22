"""Structured outputs for the crop-image vision pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class VisionAnalysisResult:
    """Contract returned to advisory/upload callers.

    Keeps the public `(summary, suspected_issue, confidence)` shape while
    carrying preprocess and inference provenance for audits and HITL.
    """

    analysis_summary: str
    suspected_issue: str | None
    confidence: float
    model_version: str
    inference_ms: float
    input_hash: str
    anomaly_score: float
    quality_flags: tuple[str, ...] = ()
    needs_officer_review: bool = False
    backend: str = "pixel"
    specialists: dict[str, dict[str, Any]] = field(default_factory=dict)
    extras: dict[str, Any] = field(default_factory=dict)

    def as_tuple(self) -> tuple[str, str | None, float]:
        return self.analysis_summary, self.suspected_issue, self.confidence

    def provenance(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["quality_flags"] = list(self.quality_flags)
        return payload
