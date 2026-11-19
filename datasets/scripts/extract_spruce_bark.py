"""
从 hf-spruce-bark 中提取高质量树皮脱落 (bark_loss, 类别10) 样本及精确 YOLO 标注
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import cv2
import numpy as np
import pyarrow.parquet as pq
from PIL import Image
from tqdm import tqdm

PARQUET_PATH = Path("E:/wood/datasets/raw/hf-spruce-bark/train.parquet")
OUT_IMG = Path("E:/wood/datasets/raw/extracted_spruce_bark/images")
OUT_LBL = Path("E:/wood/datasets/raw/extracted_spruce_bark/labels")

OUT_IMG.mkdir(parents=True, exist_ok=True)
OUT_LBL.mkdir(parents=True, exist_ok=True)

TARGET_CLASS_ID = 10  # bark_loss


def extract_spruce_bark(max_samples: int = 350) -> int:
    print("=" * 60)
    print("开始从 hf-spruce-bark 提取树皮缺陷及精确边界框...")
    print("=" * 60)

    table = pq.read_table(str(PARQUET_PATH))
    num_rows = table.num_rows
    print(f"Parquet 总条目数: {num_rows}")

    saved_count = 0

    # 数据集结构：偶数索引是原图，奇数索引是对应 mask
    for i in tqdm(range(0, num_rows - 1, 2), desc="提取树皮缺陷"):
        if saved_count >= max_samples:
            break

        img_item = table["image"][i].as_py()
        mask_item = table["image"][i + 1].as_py()

        img_path_str = img_item["path"]
        mask_path_str = mask_item["path"]

        if "mask" not in mask_path_str:
            continue

        mask_img = Image.open(io.BytesIO(mask_item["bytes"]))
        mask_arr = np.array(mask_img)

        # 缺陷值: 2 (defect)
        defect_mask = (mask_arr == 2).astype(np.uint8) * 255
        contours, _ = cv2.findContours(defect_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        H, W = mask_arr.shape
        boxes = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            # 过滤微小噪点（宽高至少 12 像素，且面积 >= 150）
            if w >= 12 and h >= 12 and w * h >= 150:
                cx = (x + w / 2.0) / W
                cy = (y + h / 2.0) / H
                bw = w / float(W)
                bh = h / float(H)
                boxes.append((cx, cy, bw, bh))

        # 如果没有 defect 标签，但有较大面积的 bark (0) 与木材的夹杂边缘，也可以作为夹皮特征
        if not boxes:
            bark_mask = (mask_arr == 0).astype(np.uint8) * 255
            b_contours, _ = cv2.findContours(bark_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in b_contours:
                x, y, w, h = cv2.boundingRect(c)
                if 20 <= w <= W * 0.9 and 20 <= h <= H * 0.9 and w * h >= 800:
                    cx = (x + w / 2.0) / W
                    cy = (y + h / 2.0) / H
                    bw = w / float(W)
                    bh = h / float(H)
                    boxes.append((cx, cy, bw, bh))
                    break

        if not boxes:
            continue

        # 保存原图
        stem = Path(img_path_str).stem
        img_out_file = OUT_IMG / f"{stem}.jpg"
        lbl_out_file = OUT_LBL / f"{stem}.txt"

        img = Image.open(io.BytesIO(img_item["bytes"])).convert("RGB")
        img.save(img_out_file, format="JPEG", quality=92)

        # 写入 YOLO 格式
        lines = [f"{TARGET_CLASS_ID} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}" for (cx, cy, bw, bh) in boxes]
        lbl_out_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        saved_count += 1

    print(f"\n提取完成！共提取 {saved_count} 张带有高精度掩码转 bbox 的 bark_loss 样本。")
    return saved_count


if __name__ == "__main__":
    extract_spruce_bark()
