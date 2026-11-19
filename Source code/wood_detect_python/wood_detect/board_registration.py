"""Register two overlapping, equal-scale views from a fixed, board-aligned camera."""
import cv2
import numpy as np


def translation_between(current, anchor):
    if current.shape[:2] != anchor.shape[:2]:
        raise ValueError("两张照片的分辨率不同，请使用固定机位或指定格位")
    height, width = current.shape[:2]
    scale = min(1.0, 1400 / max(width, height))
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    detector = cv2.SIFT_create(nfeatures=2500)
    def describe(image):
        return detector.detectAndCompute(cv2.resize(image, size, interpolation=cv2.INTER_AREA), None)

    points, descriptors = describe(current)
    refs, reference = describe(anchor)
    if descriptors is None or reference is None or min(len(descriptors), len(reference)) < 12:
        raise ValueError("纹理特征不足，请增加重叠区域或指定格位")
    matcher = cv2.BFMatcher()
    def reliable(source, target):
        return {m.queryIdx: m.trainIdx for m, n in matcher.knnMatch(source, target, k=2)
                if m.distance < 0.72 * n.distance}
    forward = reliable(descriptors, reference)
    reverse = reliable(reference, descriptors)
    pairs = [(a, b) for a, b in forward.items() if reverse.get(b) == a]
    if len(pairs) < 12:
        raise ValueError("相邻照片缺少可靠的双向匹配")
    source = np.float32([points[a].pt for a, _ in pairs])
    target = np.float32([refs[b].pt for _, b in pairs])
    # Fixed camera calibration permits translation only. Reject perspective, zoom and rotation.
    offsets = target - source
    shift = np.median(offsets, axis=0)
    consistent = np.linalg.norm(offsets - shift, axis=1) < 3
    good = source[consistent]
    if len(good) < 12 or len(good) / len(pairs) < 0.70 or np.any(np.ptp(good, axis=0) < np.array(size) * 0.08):
        raise ValueError("重叠证据不一致，请保持同一朝向、倍率和拍摄距离")
    dx, dy = np.median(offsets[consistent], axis=0) / size
    if (1 - abs(dx)) * (1 - abs(dy)) < 0.10:
        raise ValueError("照片有效重叠面积不足")
    return {"shiftX": float(dx), "shiftY": float(dy), "matches": len(good)}

