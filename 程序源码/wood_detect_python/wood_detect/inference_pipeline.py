from __future__ import annotations

from dataclasses import dataclass
import os
from time import perf_counter
from typing import Callable, Mapping, Sequence

import cv2
import numpy as np


FAST_IMAGE_SIZE = int(os.getenv("FAST_IMAGE_SIZE", "512"))
TILE_IMAGE_SIZE = int(os.getenv("TILE_IMAGE_SIZE", "896"))
TILE_OVERLAP = float(os.getenv("TILE_OVERLAP", "0.20"))
NMS_IOU_THRESHOLD = float(os.getenv("NMS_IOU_THRESHOLD", "0.50"))
AUTO_MAX_DIMENSION = int(os.getenv("AUTO_MAX_DIMENSION", "2560"))
AUTO_PIXEL_COUNT = int(os.getenv("AUTO_PIXEL_COUNT", "4000000"))
AUTO_CONFIDENCE_THRESHOLD = float(os.getenv("AUTO_CONFIDENCE_THRESHOLD", "0.55"))
AUTO_SMALL_BOX_RATIO = float(os.getenv("AUTO_SMALL_BOX_RATIO", "0.01"))
AUTO_EDGE_MARGIN_RATIO = float(os.getenv("AUTO_EDGE_MARGIN_RATIO", "0.02"))
ANOMALY_FALLBACK_ENABLED = os.getenv("ANOMALY_FALLBACK_ENABLED", "true").lower() == "true"
ANOMALY_MIN_WOOD_RATIO = float(os.getenv("ANOMALY_MIN_WOOD_RATIO", "0.30"))
ANOMALY_MIN_COMPONENT_RATIO = float(os.getenv("ANOMALY_MIN_COMPONENT_RATIO", "0.001"))
ANOMALY_MAX_COMPONENT_RATIO = float(os.getenv("ANOMALY_MAX_COMPONENT_RATIO", "0.15"))
ANOMALY_MAX_CANDIDATES = int(os.getenv("ANOMALY_MAX_CANDIDATES", "5"))
SUSPECTED_ANOMALY_CLASS_ID = 6
SUSPECTED_ANOMALY_CLASS_NAME = "suspected_anomaly"

if FAST_IMAGE_SIZE < 32 or TILE_IMAGE_SIZE < 32:
    raise ValueError("推理尺寸必须至少为 32")
if not 0 <= TILE_OVERLAP < 1:
    raise ValueError("TILE_OVERLAP 必须在 [0, 1) 范围内")
if not 0 < NMS_IOU_THRESHOLD <= 1:
    raise ValueError("NMS_IOU_THRESHOLD 必须在 (0, 1] 范围内")
if not 0 <= AUTO_EDGE_MARGIN_RATIO < 0.5:
    raise ValueError("AUTO_EDGE_MARGIN_RATIO 必须在 [0, 0.5) 范围内")
if not 0 <= ANOMALY_MIN_WOOD_RATIO <= 1:
    raise ValueError("ANOMALY_MIN_WOOD_RATIO 必须在 [0, 1] 范围内")
if not 0 < ANOMALY_MIN_COMPONENT_RATIO < ANOMALY_MAX_COMPONENT_RATIO < 1:
    raise ValueError("异常候选面积比例配置无效")
if ANOMALY_MAX_CANDIDATES < 1:
    raise ValueError("ANOMALY_MAX_CANDIDATES 必须大于 0")


@dataclass(frozen=True)
class Detection:
    class_id: int
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(frozen=True)
class InferenceOutcome:
    requested_mode: str
    actual_mode: str
    decision_reason: str
    duration_ms: int
    tile_count: int
    image_width: int
    image_height: int
    detections: tuple[Detection, ...]
    plotted_image: np.ndarray


PredictFunction = Callable[[np.ndarray, int], tuple[Sequence[Detection], Mapping[int, str]]]


def sliding_positions(length: int, tile_size: int, overlap: float) -> list[int]:
    """Return deterministic tile starts and always include the far edge."""
    if length <= tile_size:
        return [0]
    step = max(1, int(round(tile_size * (1 - overlap))))
    positions = list(range(0, max(1, length - tile_size + 1), step))
    final = length - tile_size
    if positions[-1] != final:
        positions.append(final)
    return positions


def offset_detections(detections: Sequence[Detection], offset_x: int, offset_y: int) -> list[Detection]:
    return [
        Detection(
            class_id=item.class_id,
            confidence=item.confidence,
            x1=item.x1 + offset_x,
            y1=item.y1 + offset_y,
            x2=item.x2 + offset_x,
            y2=item.y2 + offset_y,
        )
        for item in detections
    ]


def intersection_over_union(first: Detection, second: Detection) -> float:
    intersection_width = max(0.0, min(first.x2, second.x2) - max(first.x1, second.x1))
    intersection_height = max(0.0, min(first.y2, second.y2) - max(first.y1, second.y1))
    intersection = intersection_width * intersection_height
    first_area = max(0.0, first.x2 - first.x1) * max(0.0, first.y2 - first.y1)
    second_area = max(0.0, second.x2 - second.x1) * max(0.0, second.y2 - second.y1)
    union = first_area + second_area - intersection
    return intersection / union if union > 0 else 0.0


def overlap_over_smaller(first: Detection, second: Detection) -> float:
    intersection_width = max(0.0, min(first.x2, second.x2) - max(first.x1, second.x1))
    intersection_height = max(0.0, min(first.y2, second.y2) - max(first.y1, second.y1))
    intersection = intersection_width * intersection_height
    first_area = max(0.0, first.x2 - first.x1) * max(0.0, first.y2 - first.y1)
    second_area = max(0.0, second.x2 - second.x1) * max(0.0, second.y2 - second.y1)
    smaller_area = min(first_area, second_area)
    return intersection / smaller_area if smaller_area > 0 else 0.0


def class_aware_nms(detections: Sequence[Detection], iou_threshold: float = NMS_IOU_THRESHOLD) -> list[Detection]:
    """Greedy NMS that only suppresses boxes from the same class."""
    kept: list[Detection] = []
    for class_id in sorted({item.class_id for item in detections}):
        pending = sorted(
            (item for item in detections if item.class_id == class_id),
            key=lambda item: item.confidence,
            reverse=True,
        )
        while pending:
            selected = pending.pop(0)
            kept.append(selected)
            pending = [
                item
                for item in pending
                if intersection_over_union(selected, item) < iou_threshold
                and overlap_over_smaller(selected, item) < 0.80
            ]
    return sorted(kept, key=lambda item: item.confidence, reverse=True)


def touches_image_edge(
    detection: Detection,
    image_width: int,
    image_height: int,
    margin_ratio: float = AUTO_EDGE_MARGIN_RATIO,
) -> bool:
    margin = max(2.0, min(image_width, image_height) * margin_ratio)
    return (
        detection.x1 <= margin
        or detection.y1 <= margin
        or detection.x2 >= image_width - margin
        or detection.y2 >= image_height - margin
    )


def wood_tone_ratio(image: np.ndarray) -> float:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    wood_tone = (
        (hsv[:, :, 0] >= 3)
        & (hsv[:, :, 0] <= 35)
        & (hsv[:, :, 1] >= 25)
        & (hsv[:, :, 2] >= 35)
    )
    return float(np.count_nonzero(wood_tone) / wood_tone.size)


def propose_suspected_anomalies(
    image: np.ndarray,
    existing: Sequence[Detection] = (),
) -> list[Detection]:
    """Find enclosed dark regions on wood-toned images as review-only candidates.

    These candidates are deliberately assigned a separate class. They are not
    model predictions and must never be reported as one of the six trained classes.
    """
    if not ANOMALY_FALLBACK_ENABLED or wood_tone_ratio(image) < ANOMALY_MIN_WOOD_RATIO:
        return []

    height, width = image.shape[:2]
    image_area = float(width * height)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)
    _, dark_mask = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    kernel_size = max(5, min(21, int(round(min(width, height) * 0.018))))
    if kernel_size % 2 == 0:
        kernel_size += 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_CLOSE, kernel)

    component_count, _, stats, _ = cv2.connectedComponentsWithStats(dark_mask, 8)
    edge_margin = max(4, int(round(min(width, height) * AUTO_EDGE_MARGIN_RATIO)))
    candidates: list[tuple[int, Detection]] = []
    for index in range(1, component_count):
        x, y, box_width, box_height, area = (int(value) for value in stats[index])
        area_ratio = area / image_area
        if not ANOMALY_MIN_COMPONENT_RATIO <= area_ratio <= ANOMALY_MAX_COMPONENT_RATIO:
            continue
        if (
            x <= edge_margin
            or y <= edge_margin
            or x + box_width >= width - edge_margin
            or y + box_height >= height - edge_margin
        ):
            continue
        if box_width < 8 or box_height < 8:
            continue
        fill_ratio = area / float(box_width * box_height)
        score = min(0.75, 0.35 + min(0.25, area_ratio * 5) + min(0.15, fill_ratio * 0.3))
        candidate = Detection(
            class_id=SUSPECTED_ANOMALY_CLASS_ID,
            confidence=score,
            x1=float(x),
            y1=float(y),
            x2=float(x + box_width),
            y2=float(y + box_height),
        )
        if any(intersection_over_union(candidate, item) >= 0.35 for item in existing):
            continue
        candidates.append((area, candidate))

    candidates.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in candidates[:ANOMALY_MAX_CANDIDATES]]


def adaptive_tiling_reason(image: np.ndarray, detections: Sequence[Detection]) -> str | None:
    height, width = image.shape[:2]
    if max(width, height) >= AUTO_MAX_DIMENSION or width * height >= AUTO_PIXEL_COUNT:
        return "HIGH_RESOLUTION"
    if not detections:
        return "NO_FIRST_PASS_DETECTION"
    if all(touches_image_edge(item, width, height) for item in detections):
        return "EDGE_ONLY_FIRST_PASS"
    if max(item.confidence for item in detections) < AUTO_CONFIDENCE_THRESHOLD:
        return "LOW_FIRST_PASS_CONFIDENCE"
    image_area = float(width * height)
    smallest_ratio = min(
        max(0.0, item.x2 - item.x1) * max(0.0, item.y2 - item.y1) / image_area for item in detections
    )
    if smallest_ratio <= AUTO_SMALL_BOX_RATIO:
        return "SMALL_FIRST_PASS_TARGET"
    return None


def run_tiled_prediction(
    image: np.ndarray,
    predict: PredictFunction,
    tile_size: int = TILE_IMAGE_SIZE,
    overlap: float = TILE_OVERLAP,
) -> tuple[list[Detection], Mapping[int, str], int]:
    height, width = image.shape[:2]
    effective_width = min(tile_size, width)
    effective_height = min(tile_size, height)
    x_positions = sliding_positions(width, effective_width, overlap)
    y_positions = sliding_positions(height, effective_height, overlap)
    combined: list[Detection] = []
    names: Mapping[int, str] = {}
    for y in y_positions:
        for x in x_positions:
            tile = image[y : y + effective_height, x : x + effective_width]
            tile_detections, names = predict(tile, tile_size)
            combined.extend(offset_detections(tile_detections, x, y))
    return combined, names, len(x_positions) * len(y_positions)


def draw_detections(
    image: np.ndarray,
    detections: Sequence[Detection],
    class_names: Mapping[int, str],
) -> np.ndarray:
    canvas = image.copy()
    height, width = canvas.shape[:2]
    palette = (
        (39, 103, 73),
        (31, 81, 59),
        (183, 121, 31),
        (72, 103, 122),
        (177, 58, 58),
        (92, 107, 98),
        (14, 100, 154),
    )
    for item in detections:
        color = palette[item.class_id % len(palette)]
        x1 = max(0, min(width - 1, int(round(item.x1))))
        y1 = max(0, min(height - 1, int(round(item.y1))))
        x2 = max(0, min(width - 1, int(round(item.x2))))
        y2 = max(0, min(height - 1, int(round(item.y2))))
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2, cv2.LINE_AA)
        label_name = "review" if item.class_id == SUSPECTED_ANOMALY_CLASS_ID else class_names.get(
            item.class_id, str(item.class_id)
        )
        label = f"{label_name} {item.confidence:.2f}"
        (text_width, text_height), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        label_top = max(0, y1 - text_height - baseline - 6)
        cv2.rectangle(canvas, (x1, label_top), (min(width - 1, x1 + text_width + 8), y1), color, -1)
        cv2.putText(
            canvas,
            label,
            (x1 + 4, max(text_height + 1, y1 - baseline - 3)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (246, 249, 246),
            1,
            cv2.LINE_AA,
        )
    return canvas


def run_inference(
    image: np.ndarray,
    requested_mode: str,
    predict: PredictFunction,
    standard_image_size: int,
) -> InferenceOutcome:
    started = perf_counter()
    height, width = image.shape[:2]
    class_names: Mapping[int, str] = {}

    if requested_mode == "FAST":
        detections, class_names = predict(image, FAST_IMAGE_SIZE)
        actual_mode = "FAST_WHOLE"
        reason = "REQUESTED_FAST"
        tile_count = 1
    elif requested_mode == "ACCURATE":
        detections, class_names, tile_count = run_tiled_prediction(image, predict)
        actual_mode = "TILED_ACCURATE"
        reason = "REQUESTED_ACCURATE"
    else:
        first_pass, class_names = predict(image, standard_image_size)
        reason = adaptive_tiling_reason(image, first_pass)
        if reason:
            tiled, tiled_names, tiled_count = run_tiled_prediction(image, predict)
            class_names = tiled_names or class_names
            detections = [*first_pass, *tiled]
            actual_mode = "ADAPTIVE_TILED"
            tile_count = 1 + tiled_count
        else:
            detections = list(first_pass)
            actual_mode = "STANDARD_WHOLE"
            reason = "FIRST_PASS_CONFIDENT"
            tile_count = 1

    merged = class_aware_nms(detections)
    should_review_anomalies = requested_mode != "FAST" and (
        not merged or all(touches_image_edge(item, width, height) for item in merged)
    )
    if should_review_anomalies:
        suspected = propose_suspected_anomalies(image, merged)
        if suspected:
            merged = class_aware_nms([*merged, *suspected])
            class_names = {**class_names, SUSPECTED_ANOMALY_CLASS_ID: SUSPECTED_ANOMALY_CLASS_NAME}
    plotted = draw_detections(image, merged, class_names)
    duration_ms = max(1, round((perf_counter() - started) * 1000))
    return InferenceOutcome(
        requested_mode=requested_mode,
        actual_mode=actual_mode,
        decision_reason=reason,
        duration_ms=duration_ms,
        tile_count=tile_count,
        image_width=width,
        image_height=height,
        detections=tuple(merged),
        plotted_image=plotted,
    )
