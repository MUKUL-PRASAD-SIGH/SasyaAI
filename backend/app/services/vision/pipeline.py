"""Orchestrate preprocess → infer → calibrate for crop uploads."""

from __future__ import annotations

import time
from typing import Literal

from app.services.vision.onnx_backend import (
    ONNX_MODELS,
    OnnxInference,
    OnnxModelSpec,
    onnx_weights_available,
    run_onnx_detector,
)
from app.services.vision.pixel_analyser import PIXEL_MODEL_VERSION, analyse_pixels
from app.services.vision.preprocess import VisionPreprocessError, preprocess_crop_image
from app.services.vision.schemas import VisionAnalysisResult

VisionBackend = Literal["auto", "pixel", "onnx"]
HITL_VISION_THRESHOLD = 0.70
FUSION_MODEL_VERSION = "yolo-dual-specialist-onnx-v1"


def calibrate_confidence(
    *,
    raw_confidence: float,
    anomaly_score: float,
    quality_flags: tuple[str, ...],
    hitl_threshold: float = HITL_VISION_THRESHOLD,
) -> tuple[float, bool]:
    """Down-weight poor frames and flag low-confidence for officer review."""

    confidence = max(0.0, min(1.0, raw_confidence - anomaly_score * 0.3))
    if "blurry" in quality_flags:
        confidence = min(confidence, 0.62)
    if "too_dark" in quality_flags or "too_bright" in quality_flags:
        confidence = min(confidence, 0.64)
    needs_review = confidence < hitl_threshold or anomaly_score >= 0.5
    return round(confidence, 3), needs_review


def _specialist_record(
    *,
    spec: OnnxModelSpec,
    result: OnnxInference,
    inference_ms: float,
    anomaly_score: float,
    quality_flags: tuple[str, ...],
    hitl_threshold: float,
) -> dict[str, object]:
    confidence, needs_review = calibrate_confidence(
        raw_confidence=result.confidence,
        anomaly_score=anomaly_score,
        quality_flags=quality_flags,
        hitl_threshold=hitl_threshold,
    )
    return {
        "kind": spec.kind,
        "display_name": spec.display_name,
        "installed": spec.model_path.is_file(),
        "available": result.available,
        "detected": bool(result.label),
        "label": result.label,
        "confidence": confidence,
        "raw_confidence": result.confidence,
        "needs_officer_review": needs_review,
        "model_version": spec.model_version,
        "inference_ms": round(inference_ms, 2),
        "summary": result.summary,
        "detections": list((result.extras or {}).get("detections", [])),
    }


def _unavailable_specialist(spec: OnnxModelSpec, summary: str) -> dict[str, object]:
    return {
        "kind": spec.kind,
        "display_name": spec.display_name,
        "installed": spec.model_path.is_file(),
        "available": False,
        "detected": False,
        "label": None,
        "confidence": 0.0,
        "raw_confidence": 0.0,
        "needs_officer_review": False,
        "model_version": spec.model_version,
        "inference_ms": 0.0,
        "summary": summary,
        "detections": [],
    }


def _fusion_summary(specialists: dict[str, dict[str, object]]) -> str:
    phrases: list[str] = []
    for kind in ("disease", "pest"):
        evidence = specialists[kind]
        title = kind.capitalize()
        label = evidence.get("label")
        if evidence.get("available") and label:
            phrases.append(
                f"{title} specialist: '{label}' ({float(evidence['confidence']):.0%})."
            )
        elif evidence.get("available"):
            phrases.append(f"{title} specialist: no detection above threshold.")
        elif evidence.get("installed"):
            phrases.append(f"{title} specialist: model could not run.")
        else:
            phrases.append(f"{title} specialist: model not installed.")
    phrases.append("Confirm visual findings with an extension officer before treatment.")
    return " ".join(phrases)


def analyse_crop_image(
    *,
    payload: bytes,
    content_type: str,
    filename: str = "",
    backend: VisionBackend = "auto",
    hitl_threshold: float = HITL_VISION_THRESHOLD,
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

    extras: dict[str, object] = {}
    chosen_backend = "pixel"
    model_version = PIXEL_MODEL_VERSION
    specialists = {
        spec.kind: _unavailable_specialist(
            spec,
            (
                "Skipped because VISION_BACKEND=pixel."
                if backend == "pixel"
                else "ONNX weights not installed."
            ),
        )
        for spec in ONNX_MODELS
    }
    label: str | None
    raw_confidence: float
    summary: str

    installed_models = [spec for spec in ONNX_MODELS if onnx_weights_available(spec.model_path)]
    successful_models: list[OnnxModelSpec] = []
    onnx_details: dict[str, object] = {}
    if backend != "pixel" and installed_models:
        for spec in installed_models:
            specialist_started = time.perf_counter()
            result = run_onnx_detector(preprocessed, model=spec)
            specialist_ms = (time.perf_counter() - specialist_started) * 1000.0
            specialists[spec.kind] = _specialist_record(
                spec=spec,
                result=result,
                inference_ms=specialist_ms,
                anomaly_score=preprocessed.anomaly_score,
                quality_flags=preprocessed.quality_flags,
                hitl_threshold=hitl_threshold,
            )
            if result.extras:
                onnx_details[spec.kind] = result.extras
            if result.available:
                successful_models.append(spec)

    if successful_models:
        chosen_backend = "onnx"
        model_version = (
            FUSION_MODEL_VERSION
            if len(successful_models) > 1
            else successful_models[0].model_version
        )
        detected = [
            specialists[spec.kind]
            for spec in ONNX_MODELS
            if specialists[spec.kind].get("label")
        ]
        labels = [str(item["label"]) for item in detected]
        label = " + ".join(dict.fromkeys(labels)) or None
        raw_confidence = max(
            (float(item["raw_confidence"]) for item in detected),
            default=0.0,
        )
        summary = _fusion_summary(specialists)
        extras["onnx"] = onnx_details
        extras["fusion"] = {
            "strategy": "preserve-both-specialists-select-strongest-confidence",
            "detected_labels": labels,
            "primary_confidence": raw_confidence,
        }
    else:
        if backend == "onnx":
            raise VisionPreprocessError(
                "VISION_BACKEND=onnx but no installed ONNX specialist could run."
            )
        pixel = analyse_pixels(preprocessed)
        label = pixel.label
        raw_confidence = pixel.confidence
        summary = pixel.summary
        extras["pixel_metrics"] = pixel.metrics
        failed = [
            str(specialists[spec.kind]["summary"])
            for spec in installed_models
            if specialists[spec.kind].get("summary")
        ]
        if failed:
            extras["onnx_fallback"] = failed

    confidence, needs_review = calibrate_confidence(
        raw_confidence=raw_confidence,
        anomaly_score=preprocessed.anomaly_score,
        quality_flags=preprocessed.quality_flags,
        hitl_threshold=hitl_threshold,
    )
    if chosen_backend == "onnx":
        # A low-confidence positive secondary finding must still reach HITL,
        # even when the primary specialist is confident.
        needs_review = needs_review or any(
            bool(item.get("detected")) and bool(item.get("needs_officer_review"))
            for item in specialists.values()
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
        specialists=specialists,
        extras=extras,
    )
