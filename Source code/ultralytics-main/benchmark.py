from __future__ import annotations

import argparse
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import torch
from ultralytics import YOLO

from wood_pipeline.common import normalized_names, require_expected_names, resolve_project_path, write_json


SUPPORTED_IMAGES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def collect_images(source: Path) -> list[Path]:
    if source.is_file() and source.suffix.lower() in SUPPORTED_IMAGES:
        return [source]
    if source.is_dir():
        return sorted(path for path in source.rglob("*") if path.suffix.lower() in SUPPORTED_IMAGES)
    raise FileNotFoundError(f"图片源不存在或格式不支持: {source}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="比较 PyTorch/ONNX 推理性能")
    parser.add_argument("--models", nargs="+", default=["runs/detect/best.pt", "runs/detect/best.onnx"])
    parser.add_argument("--source", required=True, help="单张图片或图片目录")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--imgsz", type=int, default=896)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--repeat", type=int, default=10)
    parser.add_argument("--output", default="runs/benchmark/benchmark.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.warmup < 0:
        raise ValueError("预热次数 --warmup 不能小于 0")
    if args.repeat < 1:
        raise ValueError("重复次数 --repeat 必须大于 0")
    if args.imgsz < 1:
        raise ValueError("图像尺寸 --imgsz 必须大于 0")
    images = collect_images(resolve_project_path(args.source))
    if not images:
        raise ValueError("图片源中没有可用于基准测试的图片")
    source = [str(path) for path in images]
    reports = []
    for value in args.models:
        model_path = resolve_project_path(value)
        if not model_path.is_file():
            raise FileNotFoundError(f"模型文件不存在: {model_path}")
        model = YOLO(str(model_path))
        for _ in range(args.warmup):
            model.predict(source=source, imgsz=args.imgsz, device=args.device, verbose=False)
        timings = []
        detections = 0
        for _ in range(args.repeat):
            started = time.perf_counter()
            results = model.predict(source=source, imgsz=args.imgsz, device=args.device, verbose=False)
            timings.append((time.perf_counter() - started) * 1000 / len(source))
            detections = sum(len(result.boxes) for result in results)
        names = results[0].names
        require_expected_names(names, str(model_path))
        reports.append(
            {
                "model": str(model_path),
                "format": model_path.suffix.lower().lstrip("."),
                "class_names": list(normalized_names(names)),
                "device": args.device,
                "images": len(source),
                "repeat": args.repeat,
                "detections_last_run": detections,
                "latency_ms_per_image": {
                    "mean": statistics.fmean(timings),
                    "median": statistics.median(timings),
                    "min": min(timings),
                    "max": max(timings),
                },
                "throughput_images_per_second": 1000 / statistics.fmean(timings),
            }
        )
    output = write_json(
        args.output,
        {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "torch_cuda_available": torch.cuda.is_available(),
            "imgsz": args.imgsz,
            "source": str(resolve_project_path(args.source)),
            "results": reports,
        },
    )
    print(f"基准测试完成: {output}")


if __name__ == "__main__":
    main()
