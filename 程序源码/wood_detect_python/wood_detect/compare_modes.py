from __future__ import annotations

import argparse
import json
import statistics
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import cv2


SUPPORTED_IMAGES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
CLASS_NAMES = ("dry_knot", "sound_knot", "edge_knot", "small_knot", "split", "wave")


@dataclass(frozen=True)
class Box:
    class_id: int
    x1: float
    y1: float
    x2: float
    y2: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="比较快速整图、自适应和精细切片模式")
    parser.add_argument("--source", required=True, help="推理容器可访问的图片或目录")
    parser.add_argument("--labels", help="可选的 YOLO 标签目录，用于计算 Precision/Recall")
    parser.add_argument("--url", default="http://127.0.0.1:8001/predict")
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--iou", type=float, default=0.5)
    parser.add_argument("--sample-name", help="报告中展示的样本名称，默认使用源文件名")
    parser.add_argument("--sample-note", help="样本来源、标注状态等说明")
    parser.add_argument("--output", default="/data/uploads/reports/phase5-mode-comparison.json")
    return parser.parse_args()


def collect_images(source: Path) -> list[Path]:
    if source.is_file() and source.suffix.lower() in SUPPORTED_IMAGES:
        return [source]
    if source.is_dir():
        return sorted(path for path in source.rglob("*") if path.suffix.lower() in SUPPORTED_IMAGES)
    raise FileNotFoundError(f"图片源不存在或格式不支持: {source}")


def request_prediction(url: str, image: Path, mode: str, confidence: float) -> dict:
    body = json.dumps(
        {
            "imagePath": str(image),
            "modelMode": mode,
            "confidenceThreshold": confidence,
            "precision": "AUTO",
        }
    ).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=600) as response:
        return json.loads(response.read().decode("utf-8"))


def load_labels(labels_dir: Path, image: Path) -> list[Box]:
    matrix = cv2.imread(str(image))
    if matrix is None:
        raise ValueError(f"图片读取失败: {image}")
    height, width = matrix.shape[:2]
    label_path = labels_dir / f"{image.stem}.txt"
    if not label_path.is_file():
        return []
    boxes: list[Box] = []
    for line in label_path.read_text(encoding="utf-8").splitlines():
        values = line.split()
        if len(values) < 5:
            continue
        class_id, center_x, center_y, box_width, box_height = map(float, values[:5])
        boxes.append(
            Box(
                int(class_id),
                (center_x - box_width / 2) * width,
                (center_y - box_height / 2) * height,
                (center_x + box_width / 2) * width,
                (center_y + box_height / 2) * height,
            )
        )
    return boxes


def response_boxes(payload: dict) -> list[Box]:
    class_ids = {name: index for index, name in enumerate(CLASS_NAMES)}
    return [
        Box(class_ids[item["className"]], item["x1"], item["y1"], item["x2"], item["y2"])
        for item in payload.get("details", [])
        if item.get("className") in class_ids
    ]


def iou(first: Box, second: Box) -> float:
    intersection = max(0, min(first.x2, second.x2) - max(first.x1, second.x1)) * max(
        0, min(first.y2, second.y2) - max(first.y1, second.y1)
    )
    first_area = max(0, first.x2 - first.x1) * max(0, first.y2 - first.y1)
    second_area = max(0, second.x2 - second.x1) * max(0, second.y2 - second.y1)
    union = first_area + second_area - intersection
    return intersection / union if union else 0.0


def match_counts(predictions: list[Box], labels: list[Box], threshold: float) -> tuple[int, int, int]:
    unmatched = set(range(len(labels)))
    true_positive = 0
    for prediction in predictions:
        candidates = [
            (index, iou(prediction, labels[index]))
            for index in unmatched
            if prediction.class_id == labels[index].class_id
        ]
        if candidates:
            index, score = max(candidates, key=lambda item: item[1])
            if score >= threshold:
                true_positive += 1
                unmatched.remove(index)
    return true_positive, len(predictions) - true_positive, len(unmatched)


def markdown_report(report: dict) -> str:
    lines = [
        "# 第五阶段推理模式对比",
        "",
        f"生成时间：{report['createdAt']}",
        "",
        f"测试样本：{report['sampleName']}（{report['imageCount']} 张）",
        "",
        f"样本说明：{report['sampleNote']}",
        "",
        "| 模式 | 实际策略 | 平均耗时 | 平均模型检测数 | 平均复核候选数 | Precision | Recall |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for mode in report["modes"]:
        precision = "待标签" if mode["precision"] is None else f"{mode['precision']:.4f}"
        recall = "待标签" if mode["recall"] is None else f"{mode['recall']:.4f}"
        strategies = ", ".join(mode["actualModes"])
        lines.append(
            f"| {mode['requestedMode']} | {strategies} | {mode['meanDurationMs']:.2f} ms | "
            f"{mode['meanDetections']:.2f} | {mode['meanReviewCandidates']:.2f} | {precision} | {recall} |"
        )
    lines.extend(
        [
            "",
            "> mAP50、mAP50-95 和完整小目标召回必须使用原验证集与标准评估脚本计算，本工具不会用烟雾数据伪造这些指标。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    images = collect_images(Path(args.source).resolve())
    if not images:
        raise ValueError("图片源中没有支持的图片")
    labels_dir = Path(args.labels).resolve() if args.labels else None
    modes = []
    for requested_mode in ("FAST", "STANDARD", "ACCURATE"):
        durations: list[int] = []
        detection_counts: list[int] = []
        review_candidate_counts: list[int] = []
        actual_modes: set[str] = set()
        true_positive = false_positive = false_negative = 0
        samples = []
        for image in images:
            payload = request_prediction(args.url, image, requested_mode, args.confidence)
            predictions = response_boxes(payload)
            durations.append(payload["inferenceDurationMs"])
            review_candidates = sum(
                item.get("className") == "suspected_anomaly" for item in payload.get("details", [])
            )
            model_detections = sum(
                item.get("className") != "suspected_anomaly" for item in payload.get("details", [])
            )
            detection_counts.append(model_detections)
            review_candidate_counts.append(review_candidates)
            actual_modes.add(payload["actualMode"])
            sample = {
                "image": image.name,
                "actualMode": payload["actualMode"],
                "decisionReason": payload["decisionReason"],
                "durationMs": payload["inferenceDurationMs"],
                "tileCount": payload["tileCount"],
                "detections": model_detections,
                "reviewCandidates": review_candidates,
            }
            if labels_dir:
                tp, fp, fn = match_counts(predictions, load_labels(labels_dir, image), args.iou)
                true_positive += tp
                false_positive += fp
                false_negative += fn
                sample.update({"truePositive": tp, "falsePositive": fp, "falseNegative": fn})
            samples.append(sample)
        precision = true_positive / (true_positive + false_positive) if labels_dir and true_positive + false_positive else None
        recall = true_positive / (true_positive + false_negative) if labels_dir and true_positive + false_negative else None
        modes.append(
            {
                "requestedMode": requested_mode,
                "actualModes": sorted(actual_modes),
                "meanDurationMs": statistics.fmean(durations),
                "meanDetections": statistics.fmean(detection_counts),
                "meanReviewCandidates": statistics.fmean(review_candidate_counts),
                "precision": precision,
                "recall": recall,
                "samples": samples,
            }
        )
    report = {
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "source": str(Path(args.source).resolve()),
        "sampleName": args.sample_name or Path(args.source).name,
        "sampleNote": args.sample_note or "未提供样本来源说明",
        "labels": str(labels_dir) if labels_dir else None,
        "confidenceThreshold": args.confidence,
        "iouThreshold": args.iou,
        "imageCount": len(images),
        "modes": modes,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(markdown_report(report), encoding="utf-8")
    print(f"对比完成: {output}")


if __name__ == "__main__":
    main()
