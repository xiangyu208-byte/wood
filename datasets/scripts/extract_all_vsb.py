"""
VSB-TUO 全量未提取类别提取脚本

目标：
1. 全量提取 Blue_Stain -> stain (类别11)
2. 补充提取 Knot_missing -> large_hole (类别7)

``overgrown`` 是包生/愈合节，不等同于树皮脱落，因此明确排除。
"""

from __future__ import annotations

import io
import json
import sys
from collections import defaultdict
from pathlib import Path

import pyarrow.parquet as pq
from PIL import Image
from tqdm import tqdm

CACHE_DIR = Path("E:/wood/datasets/datasets/raw/hf-vsb-tuo/_parquet_cache")
OUT_IMG = Path("E:/wood/datasets/datasets/raw/hf-vsb-tuo/images")
OUT_LBL = Path("E:/wood/datasets/datasets/raw/hf-vsb-tuo/labels")

OUT_IMG.mkdir(parents=True, exist_ok=True)
OUT_LBL.mkdir(parents=True, exist_ok=True)

TARGETS = {
    "Blue_Stain":   ("stain", 11, 300),
    "Knot_missing": ("large_hole", 7, 300),
}


def main():
    print("=" * 60)
    print("开始全量扫描 VSB-TUO parquet 提取 Blue_Stain / Knot_missing")
    print("=" * 60)

    parquet_files = sorted(list(CACHE_DIR.glob("*.parquet")))
    print(f"找到 {len(parquet_files)} 个 parquet 文件。")

    counters = defaultdict(int)
    total_new_saved = 0

    for pq_path in parquet_files:
        print(f"\n处理: {pq_path.name}")
        table = pq.read_table(str(pq_path))
        num_rows = table.num_rows

        for row_idx in tqdm(range(num_rows), desc=f"  {pq_path.stem[:12]}"):
            row_id = int(table["id"][row_idx].as_py())
            objects = table["objects"][row_idx].as_py()
            if not objects:
                continue

            labels_in_row = [obj["label"] for obj in objects]
            bboxes_in_row = [obj["bb"] for obj in objects]

            # 检查是否有我们关心的目标
            matched_targets = []
            for label in labels_in_row:
                if label in TARGETS and counters[label] < TARGETS[label][2]:
                    matched_targets.append(label)

            if not matched_targets:
                continue

            primary = matched_targets[0]
            img_stem = f"{primary}_{row_id:06d}"
            img_file = OUT_IMG / f"{img_stem}.jpg"
            lbl_file = OUT_LBL / f"{img_stem}.txt"

            if img_file.exists() and lbl_file.exists():
                # 已经存在过，计入统计
                for t in set(matched_targets):
                    counters[t] += 1
                continue

            # 读取图片数据
            image_data = table["image"][row_idx].as_py()
            if isinstance(image_data, dict):
                img_bytes = image_data.get("bytes") or b""
            elif isinstance(image_data, bytes):
                img_bytes = image_data
            else:
                img_bytes = b""

            if not img_bytes:
                continue

            try:
                img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                img.save(img_file, format="JPEG", quality=92)
            except Exception as e:
                continue

            # 写入 YOLO 格式的标注
            lines = []
            for label, bb in zip(labels_in_row, bboxes_in_row):
                if label in TARGETS:
                    target_id = TARGETS[label][1]
                    cx, cy, w, h = bb
                    lines.append(f"{target_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")

            lbl_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

            for t in set(matched_targets):
                counters[t] += 1
            total_new_saved += 1

    print("\n" + "=" * 60)
    print(f"提取完成！新增提取图片: {total_new_saved} 张")
    for label, (name, cid, quota) in TARGETS.items():
        print(f"  {label:15s} -> [{cid}] {name:15s}: {counters[label]} 个")
    print("=" * 60)


if __name__ == "__main__":
    main()
