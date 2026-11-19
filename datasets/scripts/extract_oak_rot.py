"""
从 hf-oak-rot 提取木材腐朽 (decay, 类别6) 精确标注与局部多尺度切块
"""

from __future__ import annotations

import random
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from tqdm import tqdm

IMG_DIR = Path("E:/wood/datasets/raw/hf-oak-rot/images")
MASK_DIR = Path("E:/wood/datasets/raw/hf-oak-rot/masks")
OUT_IMG = Path("E:/wood/datasets/raw/extracted_oak_rot/images")
OUT_LBL = Path("E:/wood/datasets/raw/extracted_oak_rot/labels")

OUT_IMG.mkdir(parents=True, exist_ok=True)
OUT_LBL.mkdir(parents=True, exist_ok=True)

TARGET_CLASS_ID = 6  # decay


def process_oak_rot() -> int:
    print("=" * 60)
    print("开始从 hf-oak-rot 提取高精度腐朽区域及切块样本...")
    print("=" * 60)

    images = sorted(list(IMG_DIR.glob("*.tif")))
    masks = sorted(list(MASK_DIR.glob("*.tif")))

    saved_count = 0

    for m_path in tqdm(masks, desc="处理腐朽掩码"):
        prefix = m_path.stem.replace("_Bin_Black_Rot", "")
        matching = [img for img in images if prefix in img.stem]
        if not matching:
            continue

        img_path = matching[0]

        try:
            pil_img = Image.open(img_path).convert("RGB")
            pil_mask = Image.open(m_path)
        except Exception:
            continue

        img_arr = np.array(pil_img)
        mask_arr = np.array(pil_mask)

        H, W = mask_arr.shape[:2]

        bin_mask = (mask_arr > 127).astype(np.uint8) * 255
        contours, _ = cv2.findContours(bin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        full_boxes = []
        raw_boxes = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            if w * h >= 300:  # 面积阈值过滤噪点
                cx = (x + w / 2.0) / W
                cy = (y + h / 2.0) / H
                bw = w / float(W)
                bh = h / float(H)
                full_boxes.append((cx, cy, bw, bh))
                raw_boxes.append((x, y, w, h))

        if not full_boxes:
            continue

        # 1. 保存全图及标注
        stem = img_path.stem
        full_img_out = OUT_IMG / f"{stem}_full.jpg"
        full_lbl_out = OUT_LBL / f"{stem}_full.txt"

        pil_img.save(full_img_out, format="JPEG", quality=90)
        lines = [f"{TARGET_CLASS_ID} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}" for (cx, cy, bw, bh) in full_boxes]
        full_lbl_out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        saved_count += 1

        # 2. 针对每个显著腐朽区域进行局部切块（crop），保留高分辨率微观腐朽特征
        for idx, (bx, by, bw, bh) in enumerate(raw_boxes[:5]):
            # 确定裁切窗口尺寸（围绕目标中心）
            crop_size = max(512, int(max(bw, bh) * 1.8))
            crop_size = min(crop_size, min(H, W))

            center_x = bx + bw // 2
            center_y = by + bh // 2

            x1 = max(0, center_x - crop_size // 2)
            y1 = max(0, center_y - crop_size // 2)

            if x1 + crop_size > W:
                x1 = max(0, W - crop_size)
            if y1 + crop_size > H:
                y1 = max(0, H - crop_size)

            x2 = min(W, x1 + crop_size)
            y2 = min(H, y1 + crop_size)

            actual_w = x2 - x1
            actual_h = y2 - y1

            if actual_w < 200 or actual_h < 200:
                continue

            crop_img = img_arr[y1:y2, x1:x2]

            # 计算在裁切图片中的相对坐标
            crop_boxes = []
            for (ox, oy, ow, oh) in raw_boxes:
                # 检查相交
                ix1 = max(x1, ox)
                iy1 = max(y1, oy)
                ix2 = min(x2, ox + ow)
                iy2 = min(y2, oy + oh)

                if ix2 > ix1 and iy2 > iy1:
                    inter_w = ix2 - ix1
                    inter_h = iy2 - iy1
                    if inter_w * inter_h >= 100:
                        rcx = (ix1 + inter_w / 2.0 - x1) / actual_w
                        rcy = (iy1 + inter_h / 2.0 - y1) / actual_h
                        rbw = inter_w / float(actual_w)
                        rbh = inter_h / float(actual_h)
                        crop_boxes.append((rcx, rcy, rbw, rbh))

            if crop_boxes:
                crop_stem = f"{stem}_crop_{idx:02d}"
                c_img_out = OUT_IMG / f"{crop_stem}.jpg"
                c_lbl_out = OUT_LBL / f"{crop_stem}.txt"

                Image.fromarray(crop_img).save(c_img_out, format="JPEG", quality=90)
                clines = [f"{TARGET_CLASS_ID} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}" for (cx, cy, bw, bh) in crop_boxes]
                c_lbl_out.write_text("\n".join(clines) + "\n", encoding="utf-8")
                saved_count += 1

    print(f"\n处理完成！共生成 {saved_count} 张带有精确掩码与切块标注的 decay 腐朽样本。")
    return saved_count


if __name__ == "__main__":
    process_oak_rot()
