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
    load_yaml,
    require_expected_names,
    resolve_project_path,
    validate_dataset_yaml,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="训练最终 6 类木材缺陷检测模型")
    parser.add_argument("--config", default="configs/train.yaml", help="训练配置 YAML")
    parser.add_argument("--data", help="覆盖数据集 YAML")
    parser.add_argument("--model", help="覆盖模型 YAML/PT")
    parser.add_argument("--device", help="覆盖设备，例如 cpu、0、0,1")
    parser.add_argument("--epochs", type=int, help="覆盖训练轮数")
    parser.add_argument("--batch", type=int, help="覆盖批大小")
    parser.add_argument("--name", help="覆盖实验名称")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_yaml(args.config)
    overrides = {key: getattr(args, key) for key in ("data", "model", "device", "epochs", "batch", "name")}
    config.update({key: value for key, value in overrides.items() if value is not None})

    data_path, _ = validate_dataset_yaml(config["data"], require_files=True)
    config["data"] = str(data_path)
    model_value = str(config.pop("model"))
    model_path = resolve_project_path(model_value)
    model_source = str(model_path) if model_path.exists() else model_value
    if config.get("device") == "auto":
        config["device"] = 0 if torch.cuda.is_available() else "cpu"

    model = YOLO(model_source)
    model.train(**config)
    require_expected_names(model.names, "训练后模型")

    save_dir = model.trainer.save_dir.resolve()
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_revision": git_revision(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "ultralytics": ultralytics.__version__,
        "cuda_available": torch.cuda.is_available(),
        "model_source": model_source,
        "class_names": list(model.names.values()),
        "dataset_yaml": str(data_path),
        "dataset_sha256": dataset_fingerprint(data_path),
        "train_parameters": config,
        "best_model": str(save_dir / "weights" / "best.pt"),
    }
    output = write_json(save_dir / "run_manifest.json", manifest)
    print(f"训练完成，运行清单: {output}")


if __name__ == "__main__":
    main()
