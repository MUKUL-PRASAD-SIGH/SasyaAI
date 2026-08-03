"""Crop-image vision pipeline (preprocess → infer → calibrate).

See Docs/VISION_PIPELINE.md for status, ONNX weight layout, and roadmap.
"""

from app.services.vision.pipeline import analyse_crop_image
from app.services.vision.preprocess import VisionPreprocessError
from app.services.vision.schemas import VisionAnalysisResult

__all__ = [
    "VisionAnalysisResult",
    "VisionPreprocessError",
    "analyse_crop_image",
]
