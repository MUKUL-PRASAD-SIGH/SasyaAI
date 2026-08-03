"""Pixel-space crop symptom screening (no neural weights required).

This is real computer vision over decoded pixels — vegetation index,
chlorosis/necrosis colour ratios, and dark speck density — not a filename
heuristic. It is not a substitute for a trained NPSS/YOLO detector; when an
ONNX weight file is present the pipeline prefers that backend.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.vision.preprocess import PreprocessedImage

PIXEL_MODEL_VERSION = "pixel-vegetation-v1"


@dataclass(frozen=True)
class PixelInference:
    label: str | None
    confidence: float
    summary: str
    metrics: dict[str, float]


def _exg(r: int, g: int, b: int) -> float:
    """Excess green index commonly used for vegetation segmentation."""

    return (2 * g - r - b) / 255.0


def analyse_pixels(image: PreprocessedImage) -> PixelInference:
    """Score leaf health cues from resized RGB pixels."""

    veg = 0
    chlorosis = 0
    necrosis = 0
    dark_specks = 0
    total = image.width * image.height
    if total == 0:
        return PixelInference(
            label=None,
            confidence=0.4,
            summary="Empty frame after preprocessing; officer review recommended.",
            metrics={},
        )

    for row in image.rgb:
        for r, g, b in row:
            if _exg(r, g, b) > 0.12 and g > r and g > b:
                veg += 1
            # Yellowish leaf tissue → possible chlorosis / early blight cue.
            if g > 90 and r > 90 and b < 90 and (r + g) > 2.2 * (b + 1):
                chlorosis += 1
            # Brown necrotic patches.
            if 40 < r < 140 and 20 < g < 100 and b < 70 and r > g > b:
                necrosis += 1
            # Dark compact speckles (aphid / sooty mold cue).
            if r < 55 and g < 55 and b < 55 and max(r, g, b) - min(r, g, b) < 18:
                dark_specks += 1

    veg_ratio = veg / total
    chloro_ratio = chlorosis / total
    necro_ratio = necrosis / total
    speck_ratio = dark_specks / total
    metrics = {
        "vegetation_ratio": round(veg_ratio, 4),
        "chlorosis_ratio": round(chloro_ratio, 4),
        "necrosis_ratio": round(necro_ratio, 4),
        "dark_speck_ratio": round(speck_ratio, 4),
        "anomaly_score": round(image.anomaly_score, 4),
    }

    if veg_ratio < 0.08:
        return PixelInference(
            label=None,
            confidence=max(0.35, 0.55 - image.anomaly_score * 0.2),
            summary=(
                "Pixel screen found little green canopy. Reframe on crop leaves "
                "and request extension-officer review if symptoms persist."
            ),
            metrics=metrics,
        )

    # Rank symptom cues; prefer insect speckles when both fire.
    if speck_ratio > 0.045 and speck_ratio > necro_ratio:
        confidence = min(0.86, 0.62 + speck_ratio * 4 + veg_ratio * 0.1)
        confidence = max(0.45, confidence - image.anomaly_score * 0.25)
        return PixelInference(
            label="aphid",
            confidence=round(confidence, 3),
            summary=(
                "Pixel vegetation screen detected dense dark speckles on leafy tissue "
                f"(vegetation {veg_ratio:.0%}, speckles {speck_ratio:.1%}). "
                "Possible insect pressure — confirm with an extension officer before treatment."
            ),
            metrics=metrics,
        )

    if chloro_ratio > 0.06 or necro_ratio > 0.04:
        confidence = min(
            0.84,
            0.58 + max(chloro_ratio, necro_ratio) * 3.5 + veg_ratio * 0.08,
        )
        confidence = max(0.45, confidence - image.anomaly_score * 0.25)
        return PixelInference(
            label="leaf spot",
            confidence=round(confidence, 3),
            summary=(
                "Pixel vegetation screen detected chlorosis/necrosis patches on canopy "
                f"(yellow {chloro_ratio:.1%}, brown {necro_ratio:.1%}). "
                "Possible leaf spotting — IPM confirmation recommended before spraying."
            ),
            metrics=metrics,
        )

    confidence = max(0.5, min(0.72, 0.6 + veg_ratio * 0.15 - image.anomaly_score * 0.2))
    return PixelInference(
        label=None,
        confidence=round(confidence, 3),
        summary=(
            "Pixel vegetation screen found healthy green canopy without a confident "
            f"pest or disease label (vegetation {veg_ratio:.0%}). "
            "Officer review recommended if field symptoms continue."
        ),
        metrics=metrics,
    )
