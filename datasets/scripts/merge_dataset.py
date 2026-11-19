"""
数据集整合脚本：将所有来源合并为 12 类训练数据集

来源与目标类别映射：
  [0] dry_knot      ← zenodo-wooddefect (原始6类) + VSB-TUO Dead_Knot
  [1] sound_knot    ← zenodo-wooddefect (原始6类) + VSB-TUO Live_Knot
  [2] edge_knot     ← zenodo-wooddefect (原始6类)
  [3] small_knot    ← zenodo-wooddefect (原始6类)
  [4] split         ← zenodo-wooddefect (原始6类) + VSB-TUO knot_with_crack/Crack
  [5] wave          ← zenodo-wooddefect (原始6类)
  [6] decay         ← hf-oak-rot + openverse-decay (需要手工标注 bbox)
  [7] large_hole    ← hf-tree-cavity + hf-mvtec-wood-hole (需要手工标注 bbox)
  [8] insect_damage ← openverse-insect + wikimedia-insect (需要手工标注 bbox)
  [9] mold          ← 经人工复核的霉变样本
  [10] bark_loss    ← Spruce Bark 缺陷掩码
  [11] stain        ← VSB-TUO Blue_Stain
  [11] stain        ← VSB-TUO resin/Quartzity

运行方式：
    python datasets/scripts/merge_dataset.py

输出：E:/wood/datasets/wood_defect_12class/
"""

from __future__ import annotations

import json
import random
import shutil
from collections import defaultdict
from pathlib import Path

from PIL import Image

# ─── 配置 ─────────────────────────────────────────────────────────────────────
WOOD_ROOT = Path(__file__).resolve().parents[2]
OUT_ROOT = WOOD_ROOT / "datasets" / "wood_defect_12class"
RAW_ROOT = WOOD_ROOT / "datasets" / "raw"
RAW_HF_VSB = WOOD_ROOT / "datasets" / "datasets" / "raw" / "hf-vsb-tuo"

TRAIN_RATIO = 0.80
VAL_RATIO   = 0.15
# TEST = 1 - TRAIN - VAL = 0.05

RANDOM_SEED = 42

# 12 类定义
TARGET_NAMES = {
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

# VSB-TUO 前缀 → 目标 ID（用于 hf-vsb-tuo/images 的文件名前缀识别）
VSB_PREFIX_TO_ID = {
    "knot_with_crack": 4,   # split
    "resin":           11,  # stain
    "Blue_Stain":      11,  # stain, not mold
    "Knot_missing":     7,  # large_hole
    "Dead_Knot":        0,  # dry_knot
    "Live_Knot":        1,  # sound_knot
}


# ─── 工具函数 ──────────────────────────────────────────────────────────────────
def copy_image(src: Path, dst: Path) -> bool:
    """复制图片，统一转为 JPEG 格式。"""
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        if src.suffix.lower() in (".png", ".tif", ".tiff", ".bmp"):
            img = Image.open(src).convert("RGB")
            img.save(dst.with_suffix(".jpg"), format="JPEG", quality=90)
        else:
            shutil.copy2(src, dst)
        return True
    except Exception as exc:
        print(f"  [警告] 复制失败 {src.name}: {exc}")
        return False


def write_label(label_path: Path, class_id: int, bbox_cx=0.5, bbox_cy=0.5, bbox_w=0.8, bbox_h=0.8) -> None:
    """写 YOLO 格式标注（无精确 bbox 时用大框占位，后续需人工校正）。"""
    label_path.parent.mkdir(parents=True, exist_ok=True)
    label_path.write_text(f"{class_id} {bbox_cx:.4f} {bbox_cy:.4f} {bbox_w:.4f} {bbox_h:.4f}\n", encoding="utf-8")


def split_and_copy(entries: list[dict], split_name: str) -> int:
    """
    entries: [{"img": Path, "lbl": Path | None, "class_id": int, "bbox": str | None}]
    split_name: "train" | "val" | "test"
    返回复制的文件数。
    """
    count = 0
    for entry in entries:
        img_src: Path = entry["img"]
        dst_stem = f"{entry.get('prefix', img_src.stem)}"
        dst_img = OUT_ROOT / "images" / split_name / f"{dst_stem}.jpg"
        dst_lbl = OUT_ROOT / "labels" / split_name / f"{dst_stem}.txt"

        # 复制图片
        if not copy_image(img_src, dst_img):
            continue

        # 复制或生成标注
        lbl_src: Path | None = entry.get("lbl")
        if lbl_src and lbl_src.exists():
            shutil.copy2(lbl_src, dst_lbl)
        elif entry.get("bbox"):
            dst_lbl.write_text(entry["bbox"], encoding="utf-8")
        else:
            # NOTE: 无精确标注，用全图大框占位，需人工在 Roboflow/Label Studio 中修正
            write_label(dst_lbl, entry["class_id"])
        count += 1
    return count


def stratified_split(entries: list[dict]) -> tuple[list, list, list]:
    """按类别分层划分 train/val/test。"""
    random.seed(RANDOM_SEED)
    by_class: dict[int, list] = defaultdict(list)
    for e in entries:
        by_class[e["class_id"]].append(e)

    train_all, val_all, test_all = [], [], []
    for cid, items in by_class.items():
        random.shuffle(items)
        n = len(items)
        n_train = max(1, int(n * TRAIN_RATIO))
        n_val   = max(1, int(n * VAL_RATIO))
        train_all.extend(items[:n_train])
        val_all.extend(items[n_train:n_train + n_val])
        test_all.extend(items[n_train + n_val:])

    return train_all, val_all, test_all


# ─── 数据收集函数 ──────────────────────────────────────────────────────────────
def collect_zenodo_original() -> list[dict]:
    """原始 6 类数据（zenodo-wooddefect，已有 YOLO 标注）。"""
    entries = []
    base = RAW_ROOT / "zenodo-wooddefect" / "wood_defect_detection"
    for split in ("train", "val"):
        img_dir = base / "images" / split
        lbl_dir = base / "labels" / split
        if not img_dir.exists():
            continue
        for img_path in img_dir.glob("*"):
            if img_path.suffix.lower() not in (".jpg", ".png", ".jpeg"):
                continue
            lbl_path = lbl_dir / (img_path.stem + ".txt")
            # 读取标注中的第一个类别 ID（用于分层统计）
            class_id = 0  # 默认
            if lbl_path.exists():
                first_line = lbl_path.read_text(encoding="utf-8").strip().split("\n")[0]
                if first_line:
                    class_id = int(first_line.split()[0])
            entries.append({
                "img": img_path,
                "lbl": lbl_path,
                "class_id": class_id,
                "prefix": f"zenodo_{split}_{img_path.stem}",
            })
    print(f"  [zenodo-original] {len(entries)} 张（原始6类，含完整标注）")
    return entries


def collect_vsb_tuo_hf() -> list[dict]:
    """VSB-TUO HuggingFace 版本（已转 YOLO 标注）。"""
    entries = []
    img_dir = RAW_HF_VSB / "images"
    lbl_dir = RAW_HF_VSB / "labels"

    if not img_dir.exists():
        print("  [vsb-tuo-hf] 目录不存在，跳过")
        return entries

    for img_path in img_dir.glob("*.jpg"):
        # 通过文件名前缀识别类别
        prefix = None
        for pfx in VSB_PREFIX_TO_ID:
            if img_path.stem.startswith(pfx + "_"):
                prefix = pfx
                break
        if prefix is None:
            continue

        class_id = VSB_PREFIX_TO_ID[prefix]
        lbl_path = lbl_dir / (img_path.stem + ".txt")

        entries.append({
            "img": img_path,
            "lbl": lbl_path if lbl_path.exists() else None,
            "class_id": class_id,
            "prefix": f"vsb_{img_path.stem}",
        })

    print(f"  [vsb-tuo-hf] {len(entries)} 张（新增类别，含YOLO标注）")
    return entries


def collect_oak_rot() -> list[dict]:
    """Oak-Rot TIF 图片 → decay 类（需手工标注，用全图大框占位）。"""
    entries = []
    img_dir = RAW_ROOT / "hf-oak-rot" / "images"
    if not img_dir.exists():
        return entries
    for i, img_path in enumerate(img_dir.glob("*.tif")):
        entries.append({
            "img": img_path,
            "lbl": None,
            "class_id": 6,  # decay
            "prefix": f"oak_rot_{i:04d}",
            # NOTE: TIF 图为整根原木横截面/纵截面，腐朽区域需人工在标注工具中框选
            "bbox": f"6 0.50 0.50 0.80 0.80\n",
        })
    print(f"  [oak-rot] {len(entries)} 张（decay，占位标注，需人工校正）")
    return entries


def collect_tree_cavity() -> list[dict]:
    """Tree-Cavity 图片 → large_hole 类。"""
    entries = []
    img_dir = RAW_ROOT / "hf-tree-cavity" / "images"
    if not img_dir.exists():
        return entries
    for i, img_path in enumerate(sorted(img_dir.glob("*.jpg"))):
        entries.append({
            "img": img_path,
            "lbl": None,
            "class_id": 7,  # large_hole
            "prefix": f"tree_cavity_{i:04d}",
            "bbox": f"7 0.50 0.50 0.70 0.70\n",
        })
    print(f"  [tree-cavity] {len(entries)} 张（large_hole，占位标注）")
    return entries


def collect_mvtec_hole() -> list[dict]:
    """MVTec 木材孔洞 PNG → large_hole 类。"""
    entries = []
    img_dir = RAW_ROOT / "hf-mvtec-wood-hole" / "image"
    if not img_dir.exists():
        return entries
    for i, img_path in enumerate(sorted(img_dir.glob("*.png"))):
        entries.append({
            "img": img_path,
            "lbl": None,
            "class_id": 7,  # large_hole
            "prefix": f"mvtec_hole_{i:04d}",
            "bbox": f"7 0.50 0.50 0.60 0.60\n",
        })
    print(f"  [mvtec-hole] {len(entries)} 张（large_hole，占位标注）")
    return entries


def collect_openverse_wikimedia() -> list[dict]:
    """Openverse + Wikimedia 候选图片。"""
    entries = []
    class_map = {
        "decay":         6,
        "insect_damage": 8,
        "mold":          9,
    }
    # Openverse
    for class_name, class_id in class_map.items():
        d = RAW_ROOT / "openverse-candidates" / class_name
        if not d.exists():
            continue
        for i, img_path in enumerate(sorted(d.glob("*.jpg"))):
            entries.append({
                "img": img_path,
                "lbl": None,
                "class_id": class_id,
                "prefix": f"openverse_{class_name}_{i:04d}",
                "bbox": f"{class_id} 0.50 0.50 0.80 0.80\n",
            })

    # Wikimedia insect
    wiki_insect = RAW_ROOT / "wikimedia-candidates" / "insect_damage"
    if wiki_insect.exists():
        for i, img_path in enumerate(sorted(wiki_insect.glob("*.jpg"))):
            entries.append({
                "img": img_path,
                "lbl": None,
                "class_id": 8,  # insect_damage
                "prefix": f"wikimedia_insect_{i:04d}",
                "bbox": f"8 0.50 0.50 0.80 0.80\n",
            })

    by_class = defaultdict(int)
    for e in entries:
        by_class[TARGET_NAMES[e["class_id"]]] += 1
    print(f"  [openverse+wikimedia] {len(entries)} 张: " + ", ".join(f"{k}:{v}" for k, v in sorted(by_class.items())))
    return entries


# ─── 主函数 ────────────────────────────────────────────────────────────────────
def main() -> None:
    raise SystemExit(
        "此脚本已停用：旧映射会混淆 blue stain/mold/overgrown，并使用猜测框。"
        "请使用 build_12class_dataset.py。"
    )
    print("=" * 60)
    print("12 类木材缺陷数据集整合脚本")
    print("=" * 60)

    # 清空输出目录（确保干净合并）
    for split in ("train", "val", "test"):
        for sub in ("images", "labels"):
            d = OUT_ROOT / sub / split
            if d.exists():
                shutil.rmtree(d)
            d.mkdir(parents=True, exist_ok=True)

    # 收集所有数据
    print("\n[1/3] 收集各来源数据...")
    all_entries: list[dict] = []
    all_entries.extend(collect_zenodo_original())
    all_entries.extend(collect_vsb_tuo_hf())
    all_entries.extend(collect_oak_rot())
    all_entries.extend(collect_tree_cavity())
    all_entries.extend(collect_mvtec_hole())
    all_entries.extend(collect_openverse_wikimedia())

    print(f"\n  合计: {len(all_entries)} 张")

    # 按类别统计
    by_class = defaultdict(int)
    for e in all_entries:
        by_class[e["class_id"]] += 1
    print("\n  各类别数量（合并前）:")
    for cid in sorted(TARGET_NAMES.keys()):
        cnt = by_class.get(cid, 0)
        name = TARGET_NAMES[cid]
        flag = " *** 不足200张，需补充 ***" if cnt < 200 else ""
        print(f"    [{cid}] {name:15s}: {cnt:>4} 张{flag}")

    # 分层划分
    print("\n[2/3] 分层划分 train/val/test...")
    train_list, val_list, test_list = stratified_split(all_entries)
    print(f"  train: {len(train_list)}, val: {len(val_list)}, test: {len(test_list)}")

    # 复制文件
    print("\n[3/3] 复制图片和标注...")
    n_train = split_and_copy(train_list, "train")
    n_val   = split_and_copy(val_list,   "val")
    n_test  = split_and_copy(test_list,  "test")

    print(f"\n  train: {n_train} 张, val: {n_val} 张, test: {n_test} 张")

    # 写最终统计报告
    report = {
        "total": n_train + n_val + n_test,
        "train": n_train, "val": n_val, "test": n_test,
        "class_counts_before_split": dict(by_class),
        "classes_needing_annotation": [
            TARGET_NAMES[cid] for cid in sorted(TARGET_NAMES.keys())
            if by_class.get(cid, 0) < 200
        ],
        "notes": {
            "decay": "oak-rot TIF 已复制，但 bbox 为占位大框，需在 Roboflow/Label Studio 中精确框选腐朽区域",
            "large_hole": "tree-cavity + mvtec 已复制，bbox 为占位框",
            "insect_damage": "openverse + wikimedia 来源，bbox 为占位框",
            "mold": "仅使用经人工复核的真实霉变样本；Blue_Stain 属于 stain",
        }
    }
    report_path = OUT_ROOT / "metadata" / "merge_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n[完成] 数据集已整合至: {OUT_ROOT}")
    print(f"报告: {report_path}")

    if report["classes_needing_annotation"]:
        print(f"\n[警告] 以下类别数据不足200张，需要补充标注:")
        for c in report["classes_needing_annotation"]:
            print(f"  - {c}")


if __name__ == "__main__":
    main()
