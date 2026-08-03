"""Decode, EXIF-strip, resize, and quality-gate crop uploads."""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_CONTENT_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
MAX_BYTES = 5_000_000
TARGET_EDGE = 512
MIN_EDGE = 64


@dataclass(frozen=True)
class PreprocessedImage:
    """Pixel tensor ready for inference plus audit metadata."""

    rgb: list[list[tuple[int, int, int]]]
    width: int
    height: int
    input_hash: str
    quality_flags: tuple[str, ...]
    anomaly_score: float


class VisionPreprocessError(ValueError):
    """Raised when an upload fails validation or quality gates."""


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _laplacian_variance(gray: list[list[int]]) -> float:
    """Cheap blur proxy without OpenCV — 3x3 Laplacian variance."""

    height = len(gray)
    width = len(gray[0]) if height else 0
    if height < 3 or width < 3:
        return 0.0
    values: list[float] = []
    for y in range(1, height - 1):
        row = gray[y]
        for x in range(1, width - 1):
            centre = 4 * row[x]
            lap = (
                -gray[y - 1][x]
                - gray[y + 1][x]
                - row[x - 1]
                - row[x + 1]
                + centre
            )
            values.append(float(lap))
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / len(values)


def _to_gray(rgb: list[list[tuple[int, int, int]]]) -> list[list[int]]:
    return [
        [int(0.299 * r + 0.587 * g + 0.114 * b) for r, g, b in row]
        for row in rgb
    ]


def _solid_color_ratio(rgb: list[list[tuple[int, int, int]]]) -> float:
    """Fraction of pixels within a narrow band of the mean colour."""

    pixels = [pixel for row in rgb for pixel in row]
    if not pixels:
        return 1.0
    mean_r = sum(p[0] for p in pixels) / len(pixels)
    mean_g = sum(p[1] for p in pixels) / len(pixels)
    mean_b = sum(p[2] for p in pixels) / len(pixels)
    close = 0
    for r, g, b in pixels:
        if abs(r - mean_r) < 12 and abs(g - mean_g) < 12 and abs(b - mean_b) < 12:
            close += 1
    return close / len(pixels)


def preprocess_crop_image(*, payload: bytes, content_type: str) -> PreprocessedImage:
    """Validate bytes, strip EXIF, resize, and compute quality/anomaly scores."""

    if content_type not in ALLOWED_CONTENT_TYPES:
        raise VisionPreprocessError("Only JPEG, PNG, or WebP images are accepted.")
    if len(payload) > MAX_BYTES:
        raise VisionPreprocessError("Image exceeds the 5 MB upload limit.")
    if not payload:
        raise VisionPreprocessError("Empty image payload.")

    input_hash = _sha256(payload)
    try:
        with Image.open(io.BytesIO(payload)) as image:
            # Orientation from EXIF, then drop all EXIF/metadata.
            image = ImageOps.exif_transpose(image)
            rgb_image = image.convert("RGB")
    except UnidentifiedImageError as error:
        raise VisionPreprocessError("Uploaded bytes are not a valid image.") from error
    except OSError as error:
        raise VisionPreprocessError("Uploaded image could not be decoded.") from error

    width, height = rgb_image.size
    if min(width, height) < MIN_EDGE:
        raise VisionPreprocessError(
            f"Image is too small for analysis (min edge {MIN_EDGE}px)."
        )

    # Letterbox-free longest-edge resize preserves aspect for leaf framing.
    scale = TARGET_EDGE / max(width, height)
    if scale < 1.0:
        rgb_image = rgb_image.resize(
            (max(1, int(width * scale)), max(1, int(height * scale))),
            Image.Resampling.LANCZOS,
        )

    pixels = list(rgb_image.getdata())
    out_w, out_h = rgb_image.size
    rgb = [
        [pixels[y * out_w + x] for x in range(out_w)]
        for y in range(out_h)
    ]

    gray = _to_gray(rgb)
    flat_gray = [value for row in gray for value in row]
    mean_luma = sum(flat_gray) / len(flat_gray)
    blur_var = _laplacian_variance(gray)
    solid_ratio = _solid_color_ratio(rgb)

    flags: list[str] = []
    anomaly = 0.0
    if mean_luma < 35:
        flags.append("too_dark")
        anomaly += 0.25
    if mean_luma > 230:
        flags.append("too_bright")
        anomaly += 0.25
    if blur_var < 18.0:
        flags.append("blurry")
        anomaly += 0.35
    if solid_ratio > 0.92:
        flags.append("near_solid")
        anomaly += 0.45
    if out_w * out_h < 12_000:
        flags.append("low_resolution")
        anomaly += 0.15

    anomaly_score = min(1.0, anomaly)
    if anomaly_score >= 0.85 and "near_solid" in flags:
        raise VisionPreprocessError(
            "Image failed quality gates (near-solid / adversarial input)."
        )

    return PreprocessedImage(
        rgb=rgb,
        width=out_w,
        height=out_h,
        input_hash=input_hash,
        quality_flags=tuple(flags),
        anomaly_score=anomaly_score,
    )
