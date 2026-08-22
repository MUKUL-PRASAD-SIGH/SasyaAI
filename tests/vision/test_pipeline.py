"""Vision pipeline tests — preprocess, pixel inference, and end-to-end analyse."""

from __future__ import annotations

import io

import pytest
from PIL import Image

import app.services.vision.pipeline as vision_pipeline
from app.services.vision import VisionPreprocessError, analyse_crop_image
from app.services.vision.onnx_backend import OnnxInference
from app.services.vision.pixel_analyser import analyse_pixels
from app.services.vision.preprocess import preprocess_crop_image


def _png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _green_leaf(size: int = 256) -> bytes:
    image = Image.new("RGB", (size, size), (34, 140, 45))
    pixels = image.load()
    assert pixels is not None
    # Light texture so quality gates do not treat the frame as adversarial solid.
    for y in range(0, size, 8):
        for x in range(0, size, 8):
            pixels[x, y] = (30, 125, 40)
    return _png_bytes(image)


def _spotted_leaf(size: int = 256) -> bytes:
    image = Image.new("RGB", (size, size), (40, 150, 50))
    pixels = image.load()
    assert pixels is not None
    for y in range(30, size - 30):
        for x in range(30, size - 30):
            if (x // 4 + y // 4) % 3 == 0:
                pixels[x, y] = (170, 155, 25)  # chlorosis blocks
            if (x // 6) % 5 == 0 and (y // 6) % 5 == 0:
                for dy in range(4):
                    for dx in range(4):
                        if x + dx < size and y + dy < size:
                            pixels[x + dx, y + dy] = (95, 45, 20)  # necrosis blobs
    return _png_bytes(image)


def _aphid_leaf(size: int = 256) -> bytes:
    image = Image.new("RGB", (size, size), (36, 145, 48))
    pixels = image.load()
    assert pixels is not None
    for y in range(16, size - 16, 2):
        for x in range(16, size - 16, 2):
            pixels[x, y] = (15, 15, 15)
            if x + 1 < size:
                pixels[x + 1, y] = (12, 12, 14)
            if y + 1 < size:
                pixels[x, y + 1] = (18, 16, 16)
    return _png_bytes(image)


def test_preprocess_strips_and_resizes_large_images():
    payload = _green_leaf(900)
    result = preprocess_crop_image(payload=payload, content_type="image/png")
    assert result.width <= 512
    assert result.height <= 512
    assert len(result.input_hash) == 64
    assert result.anomaly_score < 0.85


def test_preprocess_rejects_tiny_images():
    payload = _png_bytes(Image.new("RGB", (32, 32), (0, 200, 0)))
    with pytest.raises(VisionPreprocessError, match="too small"):
        preprocess_crop_image(payload=payload, content_type="image/png")


def test_preprocess_rejects_invalid_bytes():
    with pytest.raises(VisionPreprocessError, match="valid image"):
        preprocess_crop_image(payload=b"not-an-image", content_type="image/png")


def test_pixel_analyser_flags_chlorosis_patches():
    preprocessed = preprocess_crop_image(payload=_spotted_leaf(), content_type="image/png")
    inference = analyse_pixels(preprocessed)
    assert inference.label == "leaf spot"
    assert inference.confidence >= 0.45
    assert inference.metrics["chlorosis_ratio"] > 0 or inference.metrics["necrosis_ratio"] > 0


def test_pixel_analyser_flags_dark_specks():
    preprocessed = preprocess_crop_image(payload=_aphid_leaf(), content_type="image/png")
    inference = analyse_pixels(preprocessed)
    assert inference.label == "aphid"
    assert inference.confidence >= 0.45


def test_analyse_crop_image_ignores_filename_heuristics():
    """Filename must not drive labels — pixels do."""

    # Name says aphid, pixels are uniform healthy green → no insect label required.
    result = analyse_crop_image(
        payload=_green_leaf(),
        content_type="image/png",
        filename="severe-aphid-outbreak.jpg",
        backend="pixel",
    )
    assert result.backend == "pixel"
    assert result.model_version.startswith("pixel-")
    assert result.input_hash
    assert result.inference_ms >= 0
    # Healthy green canopy should not invent aphids from the filename.
    assert result.suspected_issue != "aphid"


def test_analyse_crop_image_returns_provenance_for_spotted_leaf():
    result = analyse_crop_image(
        payload=_spotted_leaf(),
        content_type="image/png",
        filename="field.jpg",
        backend="pixel",
    )
    summary, label, confidence = result.as_tuple()
    assert "Pixel" in summary or "pixel" in summary.lower() or "chlorosis" in summary.lower() or "spot" in summary.lower()
    assert label == "leaf spot"
    assert 0.0 <= confidence <= 1.0
    provenance = result.provenance()
    assert provenance["model_version"]
    assert "pixel_metrics" in provenance["extras"]


def test_auto_runs_and_fuses_both_onnx_specialists(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(vision_pipeline, "onnx_weights_available", lambda _path: True)

    def fake_detector(_image, *, model):
        calls.append(model.kind)
        label, confidence = (
            ("Tomato___Early_blight", 0.91)
            if model.kind == "disease"
            else ("whitefly", 0.83)
        )
        return OnnxInference(
            label=label,
            confidence=confidence,
            summary=f"{model.display_name} detected {label}.",
            available=True,
            extras={"detections": [{"label": label, "confidence": confidence}]},
        )

    monkeypatch.setattr(vision_pipeline, "run_onnx_detector", fake_detector)
    result = vision_pipeline.analyse_crop_image(
        payload=_spotted_leaf(),
        content_type="image/png",
        backend="auto",
    )

    assert calls == ["disease", "pest"]
    assert result.backend == "onnx"
    assert result.model_version == "yolo-dual-specialist-onnx-v1"
    assert result.suspected_issue == "Tomato___Early_blight + whitefly"
    assert result.specialists["disease"]["label"] == "Tomato___Early_blight"
    assert result.specialists["pest"]["label"] == "whitefly"
    assert "Disease specialist" in result.analysis_summary
    assert "Pest specialist" in result.analysis_summary
    assert len(result.as_tuple()) == 3


def test_auto_uses_pixel_only_when_no_onnx_specialist_exists(monkeypatch):
    monkeypatch.setattr(vision_pipeline, "onnx_weights_available", lambda _path: False)

    def unexpected_detector(*_args, **_kwargs):
        raise AssertionError("ONNX detector must not run without weights")

    monkeypatch.setattr(vision_pipeline, "run_onnx_detector", unexpected_detector)
    result = vision_pipeline.analyse_crop_image(
        payload=_spotted_leaf(),
        content_type="image/png",
        backend="auto",
    )

    assert result.backend == "pixel"
    assert result.suspected_issue == "leaf spot"
    assert result.specialists["disease"]["available"] is False


def test_explicit_onnx_fails_when_no_specialist_is_installed(monkeypatch):
    monkeypatch.setattr(vision_pipeline, "onnx_weights_available", lambda _path: False)
    with pytest.raises(VisionPreprocessError, match="no installed ONNX specialist"):
        vision_pipeline.analyse_crop_image(
            payload=_green_leaf(),
            content_type="image/png",
            backend="onnx",
        )
