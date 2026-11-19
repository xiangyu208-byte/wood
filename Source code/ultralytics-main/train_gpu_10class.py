"""使用 NVIDIA GPU 训练正式 10 类木材缺陷检测模型。

推荐从项目现有的 6 类 C2fPSA 权重迁移可兼容层，新的 10 类检测头会重新训练。
本脚本只接受 CUDA 设备；未检测到可用 GPU 时会直接退出，避免误用 CPU 长时间训练。
"""

from __future__ import annotations

import argparse
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from wood_pipeline.common import (
    EXPECTED_NAMES,
    dataset_fingerprint,
    git_revision,
    load_yaml,
    require_expected_names,
    resolve_project_path,
    validate_dataset_yaml,
    write_json,
)


ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = "configs/train-10class.yaml"
DEFAULT_WEIGHTS = "runs/detect/best.pt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="使用 NVIDIA GPU 训练正式 10 类木材缺陷模型")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="训练配置 YAML")
    parser.add_argument(
        "--weights",
        default=DEFAULT_WEIGHTS,
        help="用于迁移学习的 PT 权重；传入 none 可从头训练",
    )
    parser.add_argument("--resume", help="从 last.pt/best.pt 检查点断点续训")
    parser.add_argument("--device", default="0", help="CUDA 设备，例如 0 或 0,1")
    parser.add_argument("--epochs", type=int, help="覆盖训练轮数")
    parser.add_argument("--batch", type=int, help="覆盖批大小；显存不足时可改为 8 或 4")
    parser.add_argument("--imgsz", type=int, help="覆盖输入尺寸")
    parser.add_argument("--workers", type=int, help="覆盖数据加载线程数")
    parser.add_argument("--patience", type=int, help="覆盖早停等待轮数")
    parser.add_argument("--name", help="覆盖实验名称")
    parser.add_argument("--project", help="覆盖训练结果目录")
    parser.add_argument(
        "--cache",
        choices=("false", "ram", "disk"),
        default="false",
        help="图片缓存策略；默认关闭，内存充足时可用 ram",
    )
    parser.add_argument(
        "--no-amp",
        action="store_true",
        help="关闭自动混合精度；默认启用 AMP 以减少显存占用",
    )
    return parser.parse_args()


def import_gpu_runtime():
    try:
        import torch
        from ultralytics import YOLO
    except Exception as exc:
        raise SystemExit(
            "无法加载 PyTorch/Ultralytics。请安装与 NVIDIA 驱动匹配的 CUDA 版 PyTorch，"
            f"并确认其 DLL/动态库可正常加载。原始错误：{exc}"
        ) from exc
    return torch, YOLO


def parse_device_ids(value: str) -> list[int]:
    try:
        device_ids = [int(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as exc:
        raise SystemExit(f"--device 必须是 GPU 编号，例如 0 或 0,1；当前值：{value!r}") from exc
    if not device_ids or any(device_id < 0 for device_id in device_ids):
        raise SystemExit("--device 至少要包含一个非负 GPU 编号")
    if len(set(device_ids)) != len(device_ids):
        raise SystemExit("--device 中不能出现重复 GPU 编号")
    return device_ids


def require_cuda(torch: Any, device_ids: list[int]) -> None:
    if not torch.cuda.is_available():
        raise SystemExit(
            "未检测到可用 NVIDIA CUDA GPU，训练已停止。请先检查 nvidia-smi、显卡驱动、"
            "CUDA 版 PyTorch，以及 torch.cuda.is_available()。"
        )
    device_count = torch.cuda.device_count()
    invalid = [device_id for device_id in device_ids if device_id >= device_count]
    if invalid:
        raise SystemExit(
            f"请求的 GPU {invalid} 不存在；PyTorch 当前只检测到 {device_count} 张 GPU。"
        )


def validate_model_yaml(path: Path) -> None:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if payload.get("nc") != len(EXPECTED_NAMES):
        raise SystemExit(
            f"模型 YAML 的 nc={payload.get('nc')!r}，正式类别数应为 {len(EXPECTED_NAMES)}。"
        )


def apply_overrides(config: dict[str, Any], args: argparse.Namespace) -> None:
    for key in ("epochs", "batch", "imgsz", "workers", "patience", "name", "project"):
        value = getattr(args, key)
        if value is not None:
            config[key] = value
    config["device"] = args.device
    config["amp"] = not args.no_amp
    config["cache"] = False if args.cache == "false" else args.cache


def print_summary(torch: Any, device_ids: list[int], config: dict[str, Any], data_path: Path) -> None:
    print("=" * 72)
    print("正式 10 类木材缺陷 GPU 训练")
    print(f"数据集: {data_path}")
    print(f"类别: {', '.join(EXPECTED_NAMES)}")
    print(f"epochs={config['epochs']} batch={config['batch']} imgsz={config['imgsz']}")
    print(f"AMP: {config['amp']}  cache: {config['cache']}")
    for device_id in device_ids:
        props = torch.cuda.get_device_properties(device_id)
        memory_gib = props.total_memory / (1024**3)
        print(f"GPU {device_id}: {props.name} ({memory_gib:.1f} GiB)")
    print("=" * 72)


def main() -> None:
    args = parse_args()
    torch, YOLO = import_gpu_runtime()
    device_ids = parse_device_ids(args.device)
    require_cuda(torch, device_ids)

    config = load_yaml(args.config)
    apply_overrides(config, args)
    data_path, _ = validate_dataset_yaml(config["data"], require_files=True)
    config["data"] = str(data_path)

    model_value = str(config.pop("model"))
    model_yaml = resolve_project_path(model_value)
    if not model_yaml.is_file():
        raise SystemExit(f"模型结构文件不存在：{model_yaml}")
    validate_model_yaml(model_yaml)

    if config.get("project"):
        config["project"] = str(resolve_project_path(config["project"]))

    resume_path: Path | None = None
    transfer_weights: Path | None = None
    if args.resume:
        resume_path = resolve_project_path(args.resume)
        if not resume_path.is_file():
            raise SystemExit(f"断点权重不存在：{resume_path}")
        model = YOLO(str(resume_path))
        config["resume"] = True
        config.pop("pretrained", None)
    else:
        model = YOLO(str(model_yaml))
        if args.weights.lower() not in {"none", "false", "scratch"}:
            transfer_weights = resolve_project_path(args.weights)
            if not transfer_weights.is_file():
                raise SystemExit(f"迁移学习权重不存在：{transfer_weights}")
            model.load(str(transfer_weights))
        # 权重已由 model.load() 显式载入；布尔 pretrained=True 不会指定具体权重。
        config["pretrained"] = False

    print_summary(torch, device_ids, config, data_path)
    if resume_path:
        print(f"断点续训: {resume_path}")
    elif transfer_weights:
        print(f"迁移学习权重: {transfer_weights}")
    else:
        print("训练方式: 从头训练")

    model.train(**config)
    require_expected_names(model.names, "训练后模型")

    save_dir = Path(model.trainer.save_dir).resolve()
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_revision": git_revision(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "gpu_devices": [
            {
                "id": device_id,
                "name": torch.cuda.get_device_name(device_id),
                "total_memory_bytes": torch.cuda.get_device_properties(device_id).total_memory,
            }
            for device_id in device_ids
        ],
        "class_names": list(EXPECTED_NAMES),
        "dataset_yaml": str(data_path),
        "dataset_sha256": dataset_fingerprint(data_path),
        "model_yaml": str(model_yaml),
        "transfer_weights": str(transfer_weights) if transfer_weights else None,
        "resume_checkpoint": str(resume_path) if resume_path else None,
        "train_parameters": config,
        "best_model": str(save_dir / "weights" / "best.pt"),
        "last_model": str(save_dir / "weights" / "last.pt"),
    }
    output = write_json(save_dir / "run_manifest.json", manifest)
    print(f"训练完成，最佳权重：{save_dir / 'weights' / 'best.pt'}")
    print(f"运行清单：{output}")


if __name__ == "__main__":
    # Windows 多 GPU/DDP 启动需要保留 main 保护。
    main()
