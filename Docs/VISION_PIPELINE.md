# Vision pipeline

Crop image upload runs **preprocess → infer → calibrate**.

| Backend | When used |
|---|---|
| **ONNX YOLO11 plant-disease** | `models/yolov8_npss/best.onnx` exists (`VISION_BACKEND=auto` or `onnx`) |
| **Pixel vegetation CV** | Fallback when ONNX weights are missing |

**Do not commit** `.pt` / `.onnx` to GitHub (100MB+). Keep them local / download via script.

See also: [ARCHITECTURE.md](ARCHITECTURE.md), [SasyaAI_PRD.md](SasyaAI_PRD.md) (FR-020).

---

## What exists today

| Layer | Status | Location |
|---|---|---|
| Upload API | Done | `POST /api/v1/farmers/{farmer_id}/images` |
| Preprocess | Done | EXIF strip, letterbox/resize, quality gates — [preprocess.py](../backend/app/services/vision/preprocess.py) |
| Pixel inference | Done | Vegetation / chlorosis / necrosis / speck metrics |
| **ONNX YOLO detect** | Done | Ultralytics `(1, 4+nc, N)` decode + NMS — [onnx_backend.py](../backend/app/services/vision/onnx_backend.py) |
| Labels | Done | `models/yolov8_npss/labels.yaml` (116 classes from PlantDiseaseDetection) |
| Calibration / HITL | Done | `VISION_HITL_THRESHOLD` |
| Provenance | Done | `vision` block on stored images + advisory `image_processor` trace |
| Setup script | Done | [scripts/setup_vision.py](../scripts/setup_vision.py) |

```mermaid
flowchart LR
    upload[FarmerUpload] --> validate[ValidateAndStripEXIF]
    validate --> preprocess[ResizeQualityGates]
    preprocess --> infer[OnnxYoloOrPixel]
    infer --> calibrate[ConfidenceCalibration]
    calibrate --> store[ImageStorePlusProvenance]
    store --> advisory[AdvisoryQuery]
    calibrate --> hitl[LowConfidenceHITL]
```

Public contract unchanged: `(analysis_summary, suspected_issue, confidence)`.
Filename is never used for labels.

---

## Local model layout (gitignored binaries)

```text
models/yolov8_npss/
  PlantDiseaseDetection.pt   # source weights (~457 MB) — do not push
  best.onnx                  # exported detect graph (~218 MB) — do not push
  labels.yaml                # class names — safe to commit
  README.md
```

Your project already has the `.pt` at `models/yolov8_npss/PlantDiseaseDetection.pt`.

### Convert + enable (Windows / local Python)

```powershell
cd C:\Users\Mukul Prasad\Desktop\PROJECTS\SasyaAI
pip install ultralytics onnx onnxruntime pyyaml pillow numpy
python scripts/setup_vision.py --pt models/yolov8_npss/PlantDiseaseDetection.pt
```

This writes `labels.yaml` and `best.onnx`.

In `.env`:

```env
VISION_BACKEND=auto
VISION_HITL_THRESHOLD=0.70
```

Restart API:

```powershell
# local
python -m uvicorn app.main:app --app-dir backend --reload

# or Docker (mount models so the container sees best.onnx)
docker compose up -d --build api
```

For Docker, either bake a private image with weights or bind-mount:

```yaml
# optional override — do not commit secrets/weights
services:
  api:
    volumes:
      - ./models:/app/models:ro
      - ./var:/app/var
```

### Why not push the model to GitHub?

| File | Size | GitHub |
|---|---|---|
| `PlantDiseaseDetection.pt` | ~457 MB | Rejected (100 MB hard limit) |
| `best.onnx` | ~218 MB | Rejected / LFS pain for hackathons |

`.gitignore` already ignores `*.pt` / `*.onnx` / most of `/models/**`, while allowing `labels.yaml` + folder README.

Reviewers without weights still run: pixel CV fallback is automatic when `best.onnx` is absent.

---

## ONNX output contract

Export shape from this weights file: **`(1, 120, 8400)`**

- `4` box channels (xywh) + `116` class scores
- Post-process: transpose → score threshold → NMS → top label
- Prefers disease / damage labels over generic `* leaf` / `* healthy` when multiple boxes fire

---

## Config

| Variable | Default | Meaning |
|---|---|---|
| `VISION_BACKEND` | `auto` | `auto` / `pixel` / `onnx` |
| `VISION_HITL_THRESHOLD` | `0.70` | Soft confidence floor |

---

## Tests

```powershell
python -m pytest tests/vision -q
```

Pixel fixtures always run. ONNX smoke test skips if `best.onnx` is missing.

---

## Still future work

| Item | Notes |
|---|---|
| Pin Hugging Face `--hf-id` in `setup_vision.py` | Fill when you publish a stable repo revision for reviewers |
| Disease severity grading | Separate head |
| Dedicated vision microservice (:8002) | Optional scale-out |
| Gemini multimodal | Not required when ONNX is local |
| GPU / TensorRT | Optional speed-up |

---

## Changelog

| Date | Note |
|---|---|
| 2026-07-31 | Heuristic stub only. |
| 2026-08-03 | Preprocess + pixel CV + ONNX hook. |
| 2026-08-03 | Exported PlantDiseaseDetection → `best.onnx`; real YOLO decode/NMS; setup script. |
