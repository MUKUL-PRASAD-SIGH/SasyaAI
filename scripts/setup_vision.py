#!/usr/bin/env python3
"""Prepare optional YOLO disease or pest ONNX weights for SasyaAI.

Never commit large ``.pt`` / ``.onnx`` files. This script:

1. Locates the selected specialist's ``.pt`` weights
2. Writes its ``labels.yaml`` from model class names
3. Exports Ultralytics ONNX (opset 17) as that specialist's ``best.onnx``

Usage (from repo root)::

    pip install ultralytics onnx onnxruntime pyyaml
    python scripts/setup_vision.py
    python scripts/setup_vision.py --pt models/yolov8_npss/PlantDiseaseDetection.pt
    python scripts/setup_vision.py --model pest --pt models/pest/best.pt
    python scripts/setup_vision.py --hf-id <org/model>   # optional download

Then set ``VISION_BACKEND=auto`` (default) or ``onnx`` in ``.env``.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISEASE_MODEL_DIR = ROOT / "models" / "yolov8_npss"
PEST_MODEL_DIR = ROOT / "models" / "pest"
# Kept as an alias for callers that imported the original setup helper.
MODEL_DIR = DISEASE_MODEL_DIR
DEFAULT_PT_NAMES = (
    "PlantDiseaseDetection.pt",
    "best.pt",
)
PEST_PT_NAMES = ("best.pt",)
DEFAULT_HF_ID = ""  # Fill when you publish a pinned HF revision for reviewers.


def _require_ultralytics():
    try:
        import yaml  # noqa: F401
        from ultralytics import YOLO  # noqa: F401
    except ImportError as error:
        raise SystemExit(
            "Missing export deps. Install with:\n"
            "  pip install ultralytics onnx onnxruntime pyyaml\n"
            f"({error})"
        ) from error


def _find_pt(
    explicit: Path | None,
    *,
    model_dir: Path = MODEL_DIR,
    default_names: tuple[str, ...] = DEFAULT_PT_NAMES,
) -> Path:
    if explicit is not None:
        path = explicit if explicit.is_absolute() else ROOT / explicit
        if not path.is_file():
            raise SystemExit(f"PT weights not found: {path}")
        return path
    for name in default_names:
        candidate = model_dir / name
        if candidate.is_file():
            return candidate
    raise SystemExit(
        "No .pt weights found for the selected specialist. Place weights under:\n"
        f"  {model_dir}\n"
        "or pass --pt PATH"
    )


def _download_hf(
    repo_id: str,
    filename: str = "best.pt",
    *,
    model_dir: Path = MODEL_DIR,
) -> Path:
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as error:
        raise SystemExit(
            "huggingface_hub is required for --hf-id. Install with:\n"
            "  pip install huggingface_hub\n"
            f"({error})"
        ) from error
    model_dir.mkdir(parents=True, exist_ok=True)
    downloaded = hf_hub_download(repo_id=repo_id, filename=filename, local_dir=str(model_dir))
    return Path(downloaded)


def export_onnx(
    pt_path: Path,
    *,
    opset: int = 17,
    model_dir: Path = MODEL_DIR,
) -> tuple[Path, Path]:
    import yaml
    from ultralytics import YOLO

    model_dir.mkdir(parents=True, exist_ok=True)
    print(f"Loading {pt_path} ({pt_path.stat().st_size / 1e6:.1f} MB)…")
    model = YOLO(str(pt_path))
    print(f"task={getattr(model, 'task', '?')} classes={len(model.names)}")

    labels_path = model_dir / "labels.yaml"
    labels = {"names": {int(k): str(v) for k, v in model.names.items()}}
    labels_path.write_text(
        yaml.dump(labels, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print(f"Wrote {labels_path}")

    print(f"Exporting ONNX opset={opset}…")
    exported = Path(model.export(format="onnx", opset=opset, simplify=True))
    best_onnx = model_dir / "best.onnx"
    if exported.resolve() != best_onnx.resolve():
        shutil.copy2(exported, best_onnx)
    print(f"Wrote {best_onnx} ({best_onnx.stat().st_size / 1e6:.1f} MB)")
    return best_onnx, labels_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        choices=("disease", "pest"),
        default="disease",
        help="Vision specialist to prepare (default: disease)",
    )
    parser.add_argument("--pt", type=Path, default=None, help="Path to Ultralytics .pt weights")
    parser.add_argument("--hf-id", default=DEFAULT_HF_ID, help="Optional Hugging Face repo id")
    parser.add_argument("--hf-file", default="best.pt", help="Filename inside the HF repo")
    parser.add_argument("--opset", type=int, default=17)
    args = parser.parse_args(argv)

    _require_ultralytics()
    model_dir = DISEASE_MODEL_DIR if args.model == "disease" else PEST_MODEL_DIR
    default_names = DEFAULT_PT_NAMES if args.model == "disease" else PEST_PT_NAMES
    pt_path = (
        _download_hf(args.hf_id, args.hf_file, model_dir=model_dir)
        if args.hf_id
        else _find_pt(args.pt, model_dir=model_dir, default_names=default_names)
    )
    export_onnx(pt_path, opset=args.opset, model_dir=model_dir)
    print("\nDone. Keep .pt/.onnx gitignored. Set VISION_BACKEND=auto and restart the API.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
