"""Orchestrate preprocess → infer → calibrate for crop uploads."""

from __future__ import annotations

import time
from typing import Literal

from app.services.vision.onnx_backend import (
    ONNX_MODEL_VERSION,
    onnx_weights_available,
    run_onnx_detector,
)
from app.services.vision.pixel_analyser import PIXEL_MODEL_VERSION, analyse_pixels
from app.services.vision.preprocess import VisionPreprocessError, preprocess_crop_image
from app.services.vision.schemas import VisionAnalysisResult

VisionBackend = Literal["auto", "pixel", "onnx"]
HITL_VISION_THRESHOLD = 0.70


def calibrate_confidence(
    *,
    raw_confidence: float,
    anomaly_score: float,
    quality_flags: tuple[str, ...],
) -> tuple[float, bool]:
    """Down-weight poor frames and flag low-confidence for officer review."""

    confidence = max(0.0, min(1.0, raw_confidence - anomaly_score * 0.3))
    if "blurry" in quality_flags:
        confidence = min(confidence, 0.62)
    if "too_dark" in quality_flags or "too_bright" in quality_flags:
        confidence = min(confidence, 0.64)
    needs_review = confidence < HITL_VISION_THRESHOLD or anomaly_score >= 0.5
    return round(confidence, 3), needs_review


def analyse_crop_image(
    *,
    payload: bytes,
    content_type: str,
    filename: str = "",
    backend: VisionBackend = "auto",
) -> VisionAnalysisResult:
    """Run the full vision pipeline. Filename is unused for labelling.

    ``filename`` remains in the signature for call-site compatibility only.
    """

    del filename  # Explicit: do not use name-based heuristics.
    started = time.perf_counter()
    try:
        preprocessed = preprocess_crop_image(payload=payload, content_type=content_type)
    except VisionPreprocessError:
        raise

    use_onnx = backend == "onnx" or (backend == "auto" and onnx_weights_available())
    extras: dict[str, object] = {}
    chosen_backend = "pixel"
    model_version = PIXEL_MODEL_VERSION
    label: str | None
    raw_confidence: float
    summary: str

    if use_onnx:
        onnx_result = run_onnx_detector(preprocessed)
        if onnx_result.available:
            chosen_backend = "onnx"
            model_version = ONNX_MODEL_VERSION
            label = onnx_result.label
            raw_confidence = onnx_result.confidence
            summary = onnx_result.summary
            if onnx_result.extras:
                extras["onnx"] = onnx_result.extras
        elif backend == "onnx":
            raise VisionPreprocessError(
                "VISION_BACKEND=onnx but weights/onnxruntime are unavailable."
            )
        else:
            pixel = analyse_pixels(preprocessed)
            label = pixel.label
            raw_confidence = pixel.confidence
            summary = pixel.summary
            extras["pixel_metrics"] = pixel.metrics
            extras["onnx_fallback"] = onnx_result.summary
    else:
        pixel = analyse_pixels(preprocessed)
        label = pixel.label
        raw_confidence = pixel.confidence
        summary = pixel.summary
        extras["pixel_metrics"] = pixel.metrics

    confidence, needs_review = calibrate_confidence(
        raw_confidence=raw_confidence,
        anomaly_score=preprocessed.anomaly_score,
        quality_flags=preprocessed.quality_flags,
    )
    if needs_review and "officer" not in summary.lower():
        summary = f"{summary} Low confidence — routed toward officer review."

    if preprocessed.quality_flags:
        extras["quality_flags"] = list(preprocessed.quality_flags)

    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return VisionAnalysisResult(
        analysis_summary=summary,
        suspected_issue=label,
        confidence=confidence,
        model_version=model_version,
        inference_ms=round(elapsed_ms, 2),
        input_hash=preprocessed.input_hash,
        anomaly_score=round(preprocessed.anomaly_score, 4),
        quality_flags=preprocessed.quality_flags,
        needs_officer_review=needs_review,
        backend=chosen_backend,
        extras=extras,
    )
