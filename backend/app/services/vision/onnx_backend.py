"""Reusable Ultralytics YOLO ONNX detector for SasyaAI vision specialists.

Expects Ultralytics detect export layout ``(1, 4+nc, num_anchors)`` as produced by
``yolo export format=onnx`` (e.g. YOLO11 PlantDiseaseDetection → ``1,120,8400``).

Supported specialist weights live at::

    models/yolov8_npss/best.onnx
    models/yolov8_npss/labels.yaml
    models/pest/best.onnx
    models/pest/labels.yaml

Without weights the pipeline stays on pixel analysis. Do not commit large
``.pt`` / ``.onnx`` files — use ``scripts/setup_vision.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from app.core.config import ROOT_DIR
from app.services.vision.preprocess import PreprocessedImage

DEFAULT_ONNX_PATH = ROOT_DIR / "models" / "yolov8_npss" / "best.onnx"
DEFAULT_LABELS_PATH = ROOT_DIR / "models" / "yolov8_npss" / "labels.yaml"
ONNX_MODEL_VERSION = "yolo11-plant-disease-onnx-v1"
PEST_ONNX_PATH = ROOT_DIR / "models" / "pest" / "best.onnx"
PEST_LABELS_PATH = ROOT_DIR / "models" / "pest" / "labels.yaml"
PEST_ONNX_MODEL_VERSION = "yolo-pest-102-onnx-v1"
INPUT_SIZE = 640
CONF_THRESHOLD = 0.25
IOU_THRESHOLD = 0.45


@dataclass(frozen=True)
class OnnxModelSpec:
    """Files and presentation metadata for one ONNX vision specialist."""

    kind: Literal["disease", "pest"]
    display_name: str
    model_path: Path
    labels_path: Path
    model_version: str


DISEASE_MODEL = OnnxModelSpec(
    kind="disease",
    display_name="Disease model",
    model_path=DEFAULT_ONNX_PATH,
    labels_path=DEFAULT_LABELS_PATH,
    model_version=ONNX_MODEL_VERSION,
)
PEST_MODEL = OnnxModelSpec(
    kind="pest",
    display_name="Pest model",
    model_path=PEST_ONNX_PATH,
    labels_path=PEST_LABELS_PATH,
    model_version=PEST_ONNX_MODEL_VERSION,
)
ONNX_MODELS = (DISEASE_MODEL, PEST_MODEL)


@dataclass(frozen=True)
class OnnxInference:
    label: str | None
    confidence: float
    summary: str
    available: bool
    extras: dict | None = None


def onnx_weights_available(path: Path | None = None) -> bool:
    return (path or DEFAULT_ONNX_PATH).is_file()


@lru_cache(maxsize=4)
def _load_session(model_path: str):
    import onnxruntime as ort  # type: ignore

    return ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])


@lru_cache(maxsize=4)
def _load_labels(labels_path: str) -> dict[int, str]:
    path = Path(labels_path)
    if not path.is_file():
        return {}
    try:
        import yaml  # type: ignore

        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return _parse_labels_fallback(path)

    names = payload.get("names", payload)
    if isinstance(names, dict):
        return {int(k): str(v) for k, v in names.items()}
    if isinstance(names, list):
        return {index: str(name) for index, name in enumerate(names)}
    return {}


def _parse_labels_fallback(path: Path) -> dict[int, str]:
    labels: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip().strip("'\"")
        if key.isdigit():
            labels[int(key)] = value.strip().strip("'\"")
    return labels


def _letterbox_tensor(
    image: PreprocessedImage,
    size: tuple[int, int] = (INPUT_SIZE, INPUT_SIZE),
):
    """Resize with aspect ratio preserved and pad to square (Ultralytics letterbox)."""

    import numpy as np  # type: ignore

    array = np.asarray(image.rgb, dtype=np.float32) / 255.0  # HWC
    height, width = array.shape[:2]
    target_h, target_w = size
    scale = min(target_h / height, target_w / width)
    new_w = max(1, int(round(width * scale)))
    new_h = max(1, int(round(height * scale)))

    # Nearest-neighbour resize is fine at inference; preprocess already LANCZOS'd.
    ys = (np.linspace(0, height - 1, new_h)).astype(np.int32)
    xs = (np.linspace(0, width - 1, new_w)).astype(np.int32)
    resized = array[ys][:, xs]

    canvas = np.full((target_h, target_w, 3), 114.0 / 255.0, dtype=np.float32)
    pad_x = (target_w - new_w) // 2
    pad_y = (target_h - new_h) // 2
    canvas[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = resized
    tensor = np.transpose(canvas, (2, 0, 1))[None, ...]  # NCHW
    return tensor, scale, pad_x, pad_y


def _session_input_size(session) -> tuple[int, int]:
    """Read static model input dimensions, falling back for dynamic exports."""

    shape = session.get_inputs()[0].shape
    if len(shape) >= 4:
        height, width = shape[-2], shape[-1]
        if (
            isinstance(height, int)
            and not isinstance(height, bool)
            and height > 0
            and isinstance(width, int)
            and not isinstance(width, bool)
            and width > 0
        ):
            return height, width
    return INPUT_SIZE, INPUT_SIZE


def _xywh_to_xyxy(boxes):
    import numpy as np  # type: ignore

    out = np.empty_like(boxes)
    out[:, 0] = boxes[:, 0] - boxes[:, 2] / 2
    out[:, 1] = boxes[:, 1] - boxes[:, 3] / 2
    out[:, 2] = boxes[:, 0] + boxes[:, 2] / 2
    out[:, 3] = boxes[:, 1] + boxes[:, 3] / 2
    return out


def _nms(boxes, scores, iou_threshold: float) -> list[int]:
    import numpy as np  # type: ignore

    if len(boxes) == 0:
        return []
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = np.maximum(0.0, x2 - x1) * np.maximum(0.0, y2 - y1)
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        if order.size == 1:
            break
        rest = order[1:]
        xx1 = np.maximum(x1[i], x1[rest])
        yy1 = np.maximum(y1[i], y1[rest])
        xx2 = np.minimum(x2[i], x2[rest])
        yy2 = np.minimum(y2[i], y2[rest])
        inter = np.maximum(0.0, xx2 - xx1) * np.maximum(0.0, yy2 - yy1)
        union = areas[i] + areas[rest] - inter + 1e-9
        iou = inter / union
        order = rest[iou <= iou_threshold]
    return keep


def _decode_ultralytics_detect(
    output,
    *,
    labels: dict[int, str],
    conf_threshold: float = CONF_THRESHOLD,
    iou_threshold: float = IOU_THRESHOLD,
) -> list[dict]:
    """Decode ``(1, 4+nc, N)`` Ultralytics ONNX detect output to scored boxes."""

    import numpy as np  # type: ignore

    raw = np.asarray(output[0] if isinstance(output, (list, tuple)) else output)
    if raw.ndim == 3:
        raw = raw[0]
    # Accept (4+nc, N) or (N, 4+nc)
    if raw.shape[0] < raw.shape[1] and raw.shape[0] <= 512:
        pred = raw.transpose(1, 0)  # → (N, 4+nc)
    else:
        pred = raw

    if pred.shape[1] < 5:
        return []

    boxes_xywh = pred[:, :4]
    class_scores = pred[:, 4:]
    class_ids = class_scores.argmax(axis=1)
    scores = class_scores.max(axis=1)
    mask = scores >= conf_threshold
    if not np.any(mask):
        return []

    boxes_xywh = boxes_xywh[mask]
    scores = scores[mask]
    class_ids = class_ids[mask]
    boxes_xyxy = _xywh_to_xyxy(boxes_xywh)
    keep = _nms(boxes_xyxy, scores, iou_threshold)

    detections: list[dict] = []
    for index in keep:
        class_id = int(class_ids[index])
        label = labels.get(class_id, f"class_{class_id}")
        detections.append(
            {
                "label": label,
                "class_id": class_id,
                "confidence": float(scores[index]),
                "box_xyxy": [float(v) for v in boxes_xyxy[index]],
            }
        )
    detections.sort(key=lambda item: item["confidence"], reverse=True)
    return detections


def run_onnx_detector(
    image: PreprocessedImage,
    *,
    model: OnnxModelSpec = DISEASE_MODEL,
    model_path: Path | None = None,
    labels_path: Path | None = None,
) -> OnnxInference:
    """Run ONNX YOLO detect inference when weights + onnxruntime are installed."""

    path = model_path or model.model_path
    labels_file = labels_path or model.labels_path
    if not path.is_file():
        return OnnxInference(
            label=None,
            confidence=0.0,
            summary="ONNX weights not installed.",
            available=False,
        )
    try:
        import numpy  # noqa: F401
    except ImportError:
        return OnnxInference(
            label=None,
            confidence=0.0,
            summary="numpy is required for ONNX vision inference.",
            available=False,
        )
    try:
        session = _load_session(str(path.resolve()))
    except ImportError:
        return OnnxInference(
            label=None,
            confidence=0.0,
            summary="onnxruntime is not installed in this environment.",
            available=False,
        )
    except Exception as error:  # noqa: BLE001 — surface load errors to callers
        return OnnxInference(
            label=None,
            confidence=0.0,
            summary=f"ONNX model failed to load: {error}",
            available=False,
        )

    try:
        labels = _load_labels(str(labels_file.resolve())) if labels_file.is_file() else {}
        input_size = _session_input_size(session)
        tensor, _scale, _pad_x, _pad_y = _letterbox_tensor(image, input_size)
        input_name = session.get_inputs()[0].name
        outputs = session.run(None, {input_name: tensor})
        detections = _decode_ultralytics_detect(outputs, labels=labels)
    except Exception as error:  # noqa: BLE001 — degrade one specialist without losing the other
        return OnnxInference(
            label=None,
            confidence=0.0,
            summary=f"{model.display_name} inference failed: {error}",
            available=False,
            extras={"model_version": model.model_version},
        )

    if not detections:
        return OnnxInference(
            label=None,
            confidence=0.0,
            summary=(
                f"ONNX {model.kind} detector found no class above threshold; "
                "officer review recommended."
            ),
            available=True,
            extras={
                "detections": [],
                "model_version": model.model_version,
                "input_size": list(input_size),
            },
        )

    top = detections[0]
    # Disease datasets often contain plain healthy-leaf classes. Prefer an
    # actionable disease/damage label when it is among the strongest boxes.
    if model.kind == "disease":
        for candidate in detections[:5]:
            name = str(candidate["label"]).lower()
            if "healthy" in name or name.endswith(" leaf") or name.endswith("leaf"):
                continue
            top = candidate
            break

    label = str(top["label"])
    confidence = float(top["confidence"])
    extras = {
        "detections": detections[:8],
        "model_version": model.model_version,
        "top_class_id": top["class_id"],
        "input_size": list(input_size),
    }
    return OnnxInference(
        label=label,
        confidence=round(confidence, 3),
        summary=(
            f"ONNX {model.kind} detector ({model.model_version}) predicted '{label}' "
            f"at confidence {confidence:.0%} "
            f"({len(detections)} box{'es' if len(detections) != 1 else ''}). "
            "Confirm with an extension officer before treatment."
        ),
        available=True,
        extras=extras,
    )
