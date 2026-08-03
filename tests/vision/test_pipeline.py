"""Vision pipeline tests — preprocess, pixel inference, and end-to-end analyse."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.services.vision import VisionPreprocessError, analyse_crop_image
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
