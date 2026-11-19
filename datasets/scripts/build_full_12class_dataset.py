"""
全链路 12 类木材表面缺陷数据集构建与增强脚本

整合数据源：
1. Zenodo WoodDefect (原 6 类完整训练集，含高精度标注)
2. VSB-TUO HuggingFace (全量提取的工业木材缺陷：Dead_Knot, Live_Knot, Crack, Resin, Blue_Stain, Knot_missing, overgrown)
3. Spruce Bark 树皮缺陷 (掩码精准转框，类别 10 bark_loss)
4. Oak Rot 腐朽原木及多尺度切块 (黑腐掩码精准转框，91 张，类别 6 decay)
5. Tree Cavity & MVTec Wood Holes (树洞与木材大孔洞，109 张，类别 7 large_hole)
6. Openverse & Wikimedia 真实虫蛀样本 (类别 8 insect_damage)
7. 对样本较少的类别（decay, insect_damage, mold）进行保真数据增强（翻转、适度旋转、HSV色彩微扰），使每类训练样本均 >= 200 张！

按 80% train / 15% val / 5% test 分层划分。
"""

from __future__ import annotations

import copy
import json
import math
import random
import shutil
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageEnhance
from tqdm import tqdm

WOOD_ROOT = Path("E:/wood")
DATASETS_ROOT = WOOD_ROOT / "datasets"
OUT_ROOT = DATASETS_ROOT / "wood_defect_12class"

RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

TARGET_CLASSES = {
    0:  "dry_knot",
    1:  "sound_knot",
    2:  "edge_knot",
    3:  "small_knot",
    4:  "split",
    5:  "wave",
    6:  "decay",
    7:  "large_hole",
    8:  "insect_damage",
    9:  "mold",
10: "bark_loss",
    11: "stain",
}


def sanitize_box(box: list[float]) -> list[float] | None:
    """校验并纠正 bbox，确保 0 <= cx, cy, bw, bh <= 1 且面积大于0"""
    cx, cy, bw, bh = box
    if not (0 < bw <= 1 and 0 < bh <= 1):
        return None
    # 限制中心点在 [0, 1]
    cx = min(max(cx, 0.0), 1.0)
    cy = min(max(cy, 0.0), 1.0)
    # 限制边界不超出范围
    x1 = max(0.0, cx - bw / 2.0)
    y1 = max(0.0, cy - bh / 2.0)
    x2 = min(1.0, cx + bw / 2.0)
    y2 = min(1.0, cy + bh / 2.0)
    bw = x2 - x1
    bh = y2 - y1
    if bw <= 0.005 or bh <= 0.005:
        return None
    cx = x1 + bw / 2.0
    cy = y1 + bh / 2.0
    return [cx, cy, bw, bh]


def augment_sample(img: Image.Image, boxes: list[tuple[int, list[float]]], aug_type: str) -> tuple[Image.Image, list[tuple[int, list[float]]]]:
    """对单张图片和 bbox 实施几何与色彩增强"""
    w, h = img.size
    new_boxes = []

    if aug_type == "hflip":
        aug_img = img.transpose(Image.FLIP_LEFT_RIGHT)
        for cid, (cx, cy, bw, bh) in boxes:
            new_boxes.append((cid, [1.0 - cx, cy, bw, bh]))
    elif aug_type == "vflip":
        aug_img = img.transpose(Image.FLIP_TOP_BOTTOM)
        for cid, (cx, cy, bw, bh) in boxes:
            new_boxes.append((cid, [cx, 1.0 - cy, bw, bh]))
    elif aug_type == "rot180":
        aug_img = img.transpose(Image.ROTATE_180)
        for cid, (cx, cy, bw, bh) in boxes:
            new_boxes.append((cid, [1.0 - cx, 1.0 - cy, bw, bh]))
    elif aug_type == "bright_contrast":
        aug_img = img.copy()
        enh_b = ImageEnhance.Brightness(aug_img)
        aug_img = enh_b.enhance(random.uniform(0.85, 1.15))
        enh_c = ImageEnhance.Contrast(aug_img)
        aug_img = enh_c.enhance(random.uniform(0.9, 1.2))
        new_boxes = copy.deepcopy(boxes)
    else:
        aug_img = img.copy()
        new_boxes = copy.deepcopy(boxes)

    valid_boxes = []
    for cid, b in new_boxes:
        sb = sanitize_box(b)
        if sb is not None:
            valid_boxes.append((cid, sb))

    return aug_img, valid_boxes


def collect_all_sources() -> list[dict]:
    """统一搜集各数据源样本"""
    all_samples = []

    # 1. Zenodo WoodDefect 原版 6 类
    zenodo_base = DATASETS_ROOT / "raw" / "zenodo-wooddefect" / "wood_defect_detection"
    for split in ("train", "val"):
        img_dir = zenodo_base / "images" / split
        lbl_dir = zenodo_base / "labels" / split
        if not img_dir.exists():
            continue
        for ip in img_dir.glob("*.*"):
            if ip.suffix.lower() not in (".jpg", ".jpeg", ".png"):
                continue
            lp = lbl_dir / f"{ip.stem}.txt"
            if not lp.exists():
                continue
            boxes = []
            for line in lp.read_text(encoding="utf-8").strip().splitlines():
                parts = line.strip().split()
                if len(parts) >= 5:
                    cid = int(parts[0])
                    coords = [float(x) for x in parts[1:5]]
                    sb = sanitize_box(coords)
                    if sb:
                        boxes.append((cid, sb))
            if boxes:
                all_samples.append({
                    "id": f"zenodo_{split}_{ip.stem}",
                    "img_path": ip,
                    "boxes": boxes,
                    "primary_class": boxes[0][0],
                })
    print(f"  [1] Zenodo 原始训练集: {len(all_samples)} 个样本")

    # 2. VSB-TUO HuggingFace 工业木材缺陷
    vsb_img_dir = DATASETS_ROOT / "datasets" / "raw" / "hf-vsb-tuo" / "images"
    vsb_lbl_dir = DATASETS_ROOT / "datasets" / "raw" / "hf-vsb-tuo" / "labels"
    vsb_count = 0
    if vsb_img_dir.exists():
        for ip in vsb_img_dir.glob("*.jpg"):
            lp = vsb_lbl_dir / f"{ip.stem}.txt"
            if not lp.exists():
                continue
            boxes = []
            for line in lp.read_text(encoding="utf-8").strip().splitlines():
                parts = line.strip().split()
                if len(parts) >= 5:
                    cid = int(parts[0])
                    coords = [float(x) for x in parts[1:5]]
                    sb = sanitize_box(coords)
                    if sb:
                        boxes.append((cid, sb))
            if boxes:
                all_samples.append({
                    "id": f"vsb_{ip.stem}",
                    "img_path": ip,
                    "boxes": boxes,
                    "primary_class": boxes[0][0],
                })
                vsb_count += 1
    print(f"  [2] VSB-TUO 工业缺陷: {vsb_count} 个样本")

    # 3. Spruce Bark 树皮缺陷 (类别 10)
    spruce_img_dir = DATASETS_ROOT / "raw" / "extracted_spruce_bark" / "images"
    spruce_lbl_dir = DATASETS_ROOT / "raw" / "extracted_spruce_bark" / "labels"
    spruce_count = 0
    if spruce_img_dir.exists():
        for ip in spruce_img_dir.glob("*.jpg"):
            lp = spruce_lbl_dir / f"{ip.stem}.txt"
            if not lp.exists():
                continue
            boxes = []
            for line in lp.read_text(encoding="utf-8").strip().splitlines():
                parts = line.strip().split()
                if len(parts) >= 5:
                    cid = int(parts[0])
                    coords = [float(x) for x in parts[1:5]]
                    sb = sanitize_box(coords)
                    if sb:
                        boxes.append((cid, sb))
            if boxes:
                all_samples.append({
                    "id": f"spruce_{ip.stem}",
                    "img_path": ip,
                    "boxes": boxes,
                    "primary_class": 10,
                })
                spruce_count += 1
    print(f"  [3] Spruce Bark 树皮缺陷: {spruce_count} 个样本")

    # 4. Oak Rot 腐朽样本及切块 (类别 6)
    oak_img_dir = DATASETS_ROOT / "raw" / "extracted_oak_rot" / "images"
    oak_lbl_dir = DATASETS_ROOT / "raw" / "extracted_oak_rot" / "labels"
    oak_count = 0
    if oak_img_dir.exists():
        for ip in oak_img_dir.glob("*.jpg"):
            lp = oak_lbl_dir / f"{ip.stem}.txt"
            if not lp.exists():
                continue
            boxes = []
            for line in lp.read_text(encoding="utf-8").strip().splitlines():
                parts = line.strip().split()
                if len(parts) >= 5:
                    cid = int(parts[0])
                    coords = [float(x) for x in parts[1:5]]
                    sb = sanitize_box(coords)
                    if sb:
                        boxes.append((cid, sb))
            if boxes:
                all_samples.append({
                    "id": f"oak_{ip.stem}",
                    "img_path": ip,
                    "boxes": boxes,
                    "primary_class": 6,
                })
                oak_count += 1
    print(f"  [4] Oak Rot 腐朽样本及切块: {oak_count} 个样本")

    # 5. Tree-Cavity (类别 7) 与 MVTec Wood Hole (类别 7)
    tc_dir = DATASETS_ROOT / "raw" / "hf-tree-cavity" / "images"
    tc_count = 0
    if tc_dir.exists():
        for ip in tc_dir.glob("*.jpg"):
            all_samples.append({
                "id": f"tree_cavity_{ip.stem}",
                "img_path": ip,
                "boxes": [(7, [0.5, 0.5, 0.65, 0.65])],
                "primary_class": 7,
            })
            tc_count += 1

    mvtec_dir = DATASETS_ROOT / "raw" / "hf-mvtec-wood-hole" / "image"
    mvtec_mask_dir = DATASETS_ROOT / "raw" / "hf-mvtec-wood-hole" / "mask"
    mvtec_count = 0
    if mvtec_dir.exists():
        for ip in mvtec_dir.glob("*.png"):
            mp = mvtec_mask_dir / f"{ip.stem}_mask.png"
            boxes = []
            if mp.exists():
                m_arr = np.array(Image.open(mp))
                bin_m = (m_arr > 0).astype(np.uint8) * 255
                contours, _ = cv2.findContours(bin_m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                H, W = m_arr.shape
                for c in contours:
                    x, y, w, h = cv2.boundingRect(c)
                    if w * h >= 100:
                        boxes.append((7, [(x + w / 2.0) / W, (y + h / 2.0) / H, w / float(W), h / float(H)]))
            if not boxes:
                boxes = [(7, [0.5, 0.5, 0.5, 0.5])]
            all_samples.append({
                "id": f"mvtec_{ip.stem}",
                "img_path": ip,
                "boxes": boxes,
                "primary_class": 7,
            })
            mvtec_count += 1
    print(f"  [5] 大孔洞与树洞样本 (TreeCavity+MVTec): {tc_count + mvtec_count} 个样本")

    # 6. Openverse & Wikimedia 虫蛀 (类别 8)
    insect_dirs = [
        DATASETS_ROOT / "raw" / "openverse-candidates" / "insect_damage",
        DATASETS_ROOT / "raw" / "wikimedia-candidates" / "insect_damage",
    ]
    insect_count = 0
    for idir in insect_dirs:
        if idir.exists():
            for ip in idir.glob("*.jpg"):
                all_samples.append({
                    "id": f"insect_{ip.stem}",
                    "img_path": ip,
                    "boxes": [(8, [0.5, 0.5, 0.75, 0.75])],
                    "primary_class": 8,
                })
                insect_count += 1
    print(f"  [6] 真实虫蛀样本 (Openverse+Wikimedia): {insect_count} 个样本")

    # 7. Openverse 腐朽 (类别 6) 与 霉变 (类别 9)
    decay_open_dir = DATASETS_ROOT / "raw" / "openverse-candidates" / "decay"
    if decay_open_dir.exists():
        for ip in decay_open_dir.glob("*.jpg"):
            all_samples.append({
                "id": f"open_decay_{ip.stem}",
                "img_path": ip,
                "boxes": [(6, [0.5, 0.5, 0.8, 0.8])],
                "primary_class": 6,
            })

    mold_open_dir = DATASETS_ROOT / "raw" / "openverse-candidates" / "mold"
    if mold_open_dir.exists():
        for ip in mold_open_dir.glob("*.jpg"):
            all_samples.append({
                "id": f"open_mold_{ip.stem}",
                "img_path": ip,
                "boxes": [(9, [0.5, 0.5, 0.75, 0.75])],
                "primary_class": 9,
            })

    return all_samples


def main():
    raise SystemExit(
        "此脚本已停用：它会在切分前生成增强样本并把弱占位框混入验证/测试集，"
        "会造成数据泄漏。请使用 build_12class_dataset.py。"
    )
    print("=" * 60)
    print("开始整合构建 12 类木材表面缺陷终版训练数据集")
    print("=" * 60)

    # 1. 搜集样本
    samples = collect_all_sources()
    print(f"\n搜集到原始样本总数: {len(samples)} 个")

    # 2. 统计各类别样本
    class_groups = defaultdict(list)
    for s in samples:
        class_groups[s["primary_class"]].append(s)

    print("\n原始各类别样本数:")
    for cid in range(12):
        print(f"  [{cid:2d}] {TARGET_CLASSES[cid]:15s}: {len(class_groups[cid]):4d} 个")

    # 3. 数据增强：针对样本较少的类别 (decay, insect_damage, mold)，进行保真扩展至 >= 200 张
    print("\n正在对样本不足类别进行专业数据增强扩充...")
    augmented_samples = []
    aug_techniques = ["hflip", "vflip", "rot180", "bright_contrast"]

    for cid in [6, 8, 9]:  # decay, insect_damage, mold
        base_list = class_groups[cid]
        curr_len = len(base_list)
        target_len = 220
        if curr_len < target_len and curr_len > 0:
            need_more = target_len - curr_len
            print(f"  扩充类别 [{cid}] {TARGET_CLASSES[cid]}: 当前 {curr_len} -> 目标 {target_len} (需生成 {need_more} 张)")
            aug_idx = 0
            while len(augmented_samples) < need_more:
                src_sample = random.choice(base_list)
                aug_type = aug_techniques[aug_idx % len(aug_techniques)]
                aug_idx += 1

                try:
                    src_pil = Image.open(src_sample["img_path"]).convert("RGB")
                    aug_pil, aug_boxes = augment_sample(src_pil, src_sample["boxes"], aug_type)
                    if aug_boxes:
                        aug_item = {
                            "id": f"{src_sample['id']}_aug_{aug_type}_{aug_idx}",
                            "pil_img": aug_pil,
                            "boxes": aug_boxes,
                            "primary_class": cid,
                        }
                        class_groups[cid].append(aug_item)
                        if len(class_groups[cid]) >= target_len:
                            break
                except Exception as e:
                    continue

    # 4. 分层划分 (train: 80%, val: 15%, test: 5%)
    splits = {"train": [], "val": [], "test": []}

    for cid in range(12):
        items = class_groups[cid]
        random.shuffle(items)
        n = len(items)
        n_train = int(n * 0.80)
        n_val = int(n * 0.15)
        # 保证每类在 val 和 test 中至少有样本
        if n_val == 0 and n >= 2:
            n_val = 1
        n_test = n - n_train - n_val

        splits["train"].extend(items[:n_train])
        splits["val"].extend(items[n_train:n_train + n_val])
        splits["test"].extend(items[n_train + n_val:])

    # 5. 写入磁盘目录
    print("\n清空并重新初始化输出目录...")
    for split_name in ("train", "val", "test"):
        for sub in ("images", "labels"):
            d = OUT_ROOT / sub / split_name
            if d.exists():
                shutil.rmtree(d)
            d.mkdir(parents=True, exist_ok=True)

    print("\n开始并行写入各划分集 (train/val/test)...")
    summary_stats = {
        "splits": {},
        "class_distribution": {cid: 0 for cid in range(12)},
        "target_classes": TARGET_CLASSES,
    }

    for split_name in ("train", "val", "test"):
        split_items = splits[split_name]
        random.shuffle(split_items)
        img_out_dir = OUT_ROOT / "images" / split_name
        lbl_out_dir = OUT_ROOT / "labels" / split_name

        saved_files = 0
        for item in tqdm(split_items, desc=f"  写入 {split_name}"):
            stem = item["id"]
            img_dest = img_out_dir / f"{stem}.jpg"
            lbl_dest = lbl_out_dir / f"{stem}.txt"

            # 写入图片
            if "pil_img" in item:
                item["pil_img"].save(img_dest, format="JPEG", quality=90)
            else:
                try:
                    src_p = item["img_path"]
                    if src_p.suffix.lower() in (".jpg", ".jpeg"):
                        shutil.copy2(src_p, img_dest)
                    else:
                        Image.open(src_p).convert("RGB").save(img_dest, format="JPEG", quality=90)
                except Exception:
                    continue

            # 写入标注
            lines = []
            for cid, (cx, cy, bw, bh) in item["boxes"]:
                lines.append(f"{cid} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
                summary_stats["class_distribution"][cid] += 1

            lbl_dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
            saved_files += 1

        summary_stats["splits"][split_name] = saved_files

    # 6. 保存元数据与摘要报告
    report_file = OUT_ROOT / "metadata" / "dataset_summary.json"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(summary_stats, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "=" * 60)
    print("数据集构建圆满完成！统计结果如下：")
    print("=" * 60)
    print(f"训练集 (train): {summary_stats['splits']['train']} 张")
    print(f"验证集 (val):   {summary_stats['splits']['val']} 张")
    print(f"测试集 (test):  {summary_stats['splits']['test']} 张")
    print(f"图片总计:       {sum(summary_stats['splits'].values())} 张")
    print("\n各类别标注总条数分布:")
    for cid in range(12):
        print(f"  [{cid:2d}] {TARGET_CLASSES[cid]:15s}: {summary_stats['class_distribution'][cid]:5d} 条标注")
    print("=" * 60)
    print(f"元数据报告: {report_file}")


if __name__ == "__main__":
    main()
