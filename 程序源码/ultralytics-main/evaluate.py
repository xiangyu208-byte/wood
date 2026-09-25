from __future__ import annotations

import argparse
import platform
from datetime import datetime, timezone

import torch
import ultralytics
from ultralytics import YOLO

from wood_pipeline.common import (
    dataset_fingerprint,
    git_revision,
    normalized_names,
    require_expected_names,
    resolve_project_path,
    validate_dataset_yaml,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="评估 6 类木材缺陷模型并生成曲线")
    parser.add_argument("--model", default="runs/detect/best.pt")
    parser.add_argument("--data", default="yolo-bvn.yaml")
    parser.add_argument("--split", default="val", choices=("val", "test"))
    parser.add_argument("--imgsz", type=int, default=896)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--project", default="runs/evaluate")
    parser.add_argument("--name", default="wood-best")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    model_path = resolve_project_path(args.model)
    if not model_path.is_file():
        raise FileNotFoundError(f"模型文件不存在: {model_path}")
    data_path, _ = validate_dataset_yaml(args.data, require_files=True)
    device = 0 if args.device == "auto" and torch.cuda.is_available() else args.device
    if device == "auto":
        device = "cpu"

    model = YOLO(str(model_path))
    require_expected_names(model.names, str(model_path))
    metrics = model.val(
        data=str(data_path),
        split=args.split,
        imgsz=args.imgsz,
        batch=args.batch,
        device=device,
        project=str(resolve_project_path(args.project)),
        name=args.name,
        plots=True,
        save_json=False,
    )
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_revision": git_revision(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "ultralytics": ultralytics.__version__,
        "model": str(model_path),
        "class_names": list(normalized_names(model.names)),
        "dataset_yaml": str(data_path),
        "dataset_sha256": dataset_fingerprint(data_path),
        "split": args.split,
        "imgsz": args.imgsz,
        "batch": args.batch,
        "device": str(device),
        "metrics": {key: float(value) for key, value in metrics.results_dict.items()},
        "artifacts_directory": str(metrics.save_dir.resolve()),
    }
    output = write_json(metrics.save_dir / "evaluation.json", payload)
    print(f"评估完成，指标与曲线目录: {output.parent}")


if __name__ == "__main__":
    main()
