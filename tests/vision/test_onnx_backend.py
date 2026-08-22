"""ONNX backend tests — skip cleanly when best.onnx is not installed."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.core.config import ROOT_DIR
from app.services.vision.onnx_backend import (
    PEST_MODEL,
    onnx_weights_available,
    run_onnx_detector,
)
from app.services.vision.pipeline import analyse_crop_image
from app.services.vision.preprocess import preprocess_crop_image

ONNX_PATH = ROOT_DIR / "models" / "yolov8_npss" / "best.onnx"
PEST_ONNX_PATH = ROOT_DIR / "models" / "pest" / "best.onnx"
disease_weights_required = pytest.mark.skipif(
    not ONNX_PATH.is_file(),
    reason="models/yolov8_npss/best.onnx not present (optional local weights)",
)
pest_weights_required = pytest.mark.skipif(
    not PEST_ONNX_PATH.is_file(),
    reason="models/pest/best.onnx not present (optional local weights)",
)


def _png(size: int = 320) -> bytes:
    image = Image.new("RGB", (size, size), (40, 150, 50))
    pixels = image.load()
    assert pixels is not None
    for y in range(40, size - 40):
        for x in range(40, size - 40):
            if (x // 8 + y // 8) % 2 == 0:
                pixels[x, y] = (160, 120, 40)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@disease_weights_required
def test_onnx_weights_flag_true_when_present():
    assert onnx_weights_available() is True


@disease_weights_required
def test_onnx_detector_runs_and_returns_available():
    preprocessed = preprocess_crop_image(payload=_png(), content_type="image/png")
    result = run_onnx_detector(preprocessed)
    assert result.available is True
    assert result.confidence >= 0.0
    assert "ONNX" in result.summary or "onnx" in result.summary.lower() or result.label is not None or result.confidence == 0.0


@pest_weights_required
def test_pest_detector_uses_its_declared_896_input():
    preprocessed = preprocess_crop_image(payload=_png(), content_type="image/png")
    result = run_onnx_detector(preprocessed, model=PEST_MODEL)
    assert result.available is True
    assert result.extras is not None
    assert result.extras["input_size"] == [896, 896]


@disease_weights_required
def test_pipeline_auto_selects_onnx_when_weights_exist():
    result = analyse_crop_image(
        payload=_png(),
        content_type="image/png",
        filename="ignored-name-aphid.jpg",
        backend="auto",
    )
    assert result.backend == "onnx"
    assert result.model_version.startswith("yolo")
    assert result.input_hash
    assert result.inference_ms > 0
    assert result.specialists["disease"]["available"] is True
    if PEST_ONNX_PATH.is_file():
        assert result.specialists["pest"]["available"] is True
        assert result.model_version == "yolo-dual-specialist-onnx-v1"
