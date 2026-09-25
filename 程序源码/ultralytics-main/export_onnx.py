from __future__ import annotations

import argparse
import hashlib
import platform
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
import torch
import ultralytics
from ultralytics import YOLO

from wood_pipeline.common import (
    git_revision,
    normalized_names,
    require_expected_names,
    resolve_project_path,
    write_json,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="导出并验证 ONNX Runtime CPU 模型")
    parser.add_argument("--model", default="runs/detect/best.pt")
    parser.add_argument("--imgsz", type=int, default=896)
    parser.add_argument("--opset", type=int, default=17)
    parser.add_argument("--dynamic", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.imgsz < 1:
        raise ValueError("图像尺寸 --imgsz 必须大于 0")
    if args.opset < 1:
        raise ValueError("ONNX opset 必须大于 0")
    model_path = resolve_project_path(args.model)
    if not model_path.is_file():
        raise FileNotFoundError(f"模型文件不存在: {model_path}")

    model = YOLO(str(model_path))
    require_expected_names(model.names, str(model_path))
    exported = model.export(
        format="onnx",
        imgsz=args.imgsz,
        opset=args.opset,
        dynamic=args.dynamic,
        simplify=False,
        half=False,
        device="cpu",
    )
    onnx_path = resolve_project_path(exported)
    graph = onnx.load(str(onnx_path))
    onnx.checker.check_model(graph)

    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    input_info = session.get_inputs()[0]
    shape = [1, 3, args.imgsz, args.imgsz]
    outputs = session.run(None, {input_info.name: np.zeros(shape, dtype=np.float32)})
    if not outputs:
        raise RuntimeError("ONNX Runtime 未返回输出")

    metadata = session.get_modelmeta().custom_metadata_map
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_revision": git_revision(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "ultralytics": ultralytics.__version__,
        "onnx": onnx.__version__,
        "onnxruntime": ort.__version__,
        "source_model": str(model_path),
        "source_sha256": sha256(model_path),
        "onnx_model": str(onnx_path),
        "onnx_sha256": sha256(onnx_path),
        "class_names": list(normalized_names(model.names)),
        "imgsz": args.imgsz,
        "opset": args.opset,
        "dynamic": args.dynamic,
        "providers": session.get_providers(),
        "input": {"name": input_info.name, "shape": input_info.shape, "type": input_info.type},
        "output_shapes": [list(value.shape) for value in outputs],
        "metadata": metadata,
        "smoke_test": "passed",
    }
    output = write_json(onnx_path.with_suffix(".manifest.json"), payload)
    print(f"ONNX 导出及 CPU 烟雾测试通过: {onnx_path}")
    print(f"导出清单: {output}")


if __name__ == "__main__":
    main()
