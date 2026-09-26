"""
木材缺陷数据集下载脚本（12 类版本，不含髓心破坏）

数据来源：
  - HuggingFace iluvvatar/wood_surface_defects（VSB-TUO 的 HF 版本）
    已内嵌图片 + YOLO 格式标注，覆盖：
      Blue_Stain → stain
      missing_knot → large_hole
      Quartzity → stain
      crack → split（补充原有类）
      dead_knot → dry_knot（补充原有类）
      live_knot → sound_knot（补充原有类）
  - VSB-TUO Zenodo Bounding_Boxes.zip（仅 5 MB，标注索引）

类别映射（VSB-TUO → 12 类目标）：
  live_knot      → 1  sound_knot   （原有，补充）
  dead_knot      → 0  dry_knot     （原有，补充）
  knot_with_crack→ 4  split        （原有，补充）
  crack          → 4  split        （原有，补充）
  resin          → 跳过（树脂不等于污渍）
  marrow         → 跳过（不需要）
  Quartzity      → 11 stain        （新增）
  missing_knot   → 7  large_hole   （新增）
  Blue_Stain     → 11 stain        （新增，蓝变属于颜色异常，不等于霉变）
  overgrown      → 跳过（愈合组织不等于树皮脱落）

每类最多下载 300 张（新增类别），原有 6 类最多补充 150 张。
decay 和 insect_damage 在 VSB-TUO 中无直接对应，需后续自采或从其他来源补充。
"""

from __future__ import annotations

import io
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import requests
from PIL import Image
from tqdm import tqdm

# ─── 配置 ─────────────────────────────────────────────────────────────────────

# 输出目录（在 wood 项目根目录下）
OUT_ROOT = Path(__file__).resolve().parents[1] / "raw" / "hf-vsb-tuo"

# 每个 VSB-TUO 原始类别最多保留多少张
MAX_PER_CLASS: dict[str, int] = {
    "Live_Knot":       150,   # → sound_knot（原有，适量补充）
    "Dead_Knot":       150,   # → dry_knot（原有，适量补充）
    "knot_with_crack": 100,   # → split（原有，少量补充）
    "crack":           150,   # → split（原有，适量补充）
    "resin":           0,     # 跳过
    "Quartzity":       200,   # → stain（新增）
    "Knot_missing":    300,   # → large_hole（新增）
    "Blue_Stain":      300,   # → stain（新增）
    "overgrown":       0,     # 跳过
    "Marrow":          0,     # 跳过
}

# 12 类目标体系（ID → 英文名）
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

# VSB-TUO 类别 → 目标类别 ID（-1 表示跳过）
VSB_TO_TARGET_ID: dict[str, int] = {
    "Live_Knot":       1,   # sound_knot
    "Dead_Knot":       0,   # dry_knot
    "knot_with_crack": 4,   # split
    "crack":           4,   # split
    "resin":           -1,  # 跳过
    "Marrow":          -1,  # 跳过
    "Quartzity":       11,  # stain
    "Knot_missing":    7,   # large_hole
    "Blue_Stain":      11,  # stain
    "overgrown":       -1,  # 跳过
}

# HuggingFace Parquet 文件列表
HF_BASE = "https://huggingface.co/datasets/iluvvatar/wood_surface_defects/resolve/main/data"
PARQUET_FILES = [
    "train-00000-of-00005-aee708e5dcec3620.parquet",
    "train-00001-of-00005-2be8dd5a78dccedb.parquet",
    "train-00002-of-00005-81cab1be3ef4b976.parquet",
    "train-00003-of-00005-46f348d8df59f63c.parquet",
    "train-00004-of-00005-cfde1ad8fb3dd17a.parquet",
]

# ─── 工具函数 ──────────────────────────────────────────────────────────────────

def download_file(url: str, dest: Path, desc: str = "") -> bool:
    """带进度条的文件下载，返回是否成功。"""
    try:
        resp = requests.get(url, stream=True, timeout=60)
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as f, tqdm(
            desc=desc or dest.name,
            total=total,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            leave=False,
        ) as bar:
            for chunk in resp.iter_content(chunk_size=1024 * 64):
                f.write(chunk)
                bar.update(len(chunk))
        return True
    except Exception as exc:
        print(f"  [错误] 下载失败 {url}: {exc}", file=sys.stderr)
        return False


def save_image_and_label(
    image_bytes: bytes,
    bboxes: list[list[float]],
    labels: list[str],
    img_path: Path,
    label_path: Path,
) -> bool:
    """保存图片（JPEG）和对应的 YOLO 格式标注文件。"""
    # 将数据集中的图片字节写为 JPEG
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img.save(img_path, format="JPEG", quality=90)
    except Exception as exc:
        print(f"  [警告] 图片保存失败: {exc}", file=sys.stderr)
        return False

    # 写 YOLO 标注
    lines = []
    for bb, label in zip(bboxes, labels):
        target_id = VSB_TO_TARGET_ID.get(label, -1)
        if target_id < 0:
            continue
        # bb 已是 YOLO 归一化格式 [cx, cy, w, h]
        cx, cy, w, h = bb
        lines.append(f"{target_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")

    label_path.parent.mkdir(parents=True, exist_ok=True)
    label_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return True


# ─── 主下载逻辑 ────────────────────────────────────────────────────────────────

def process_parquet(parquet_path: Path, counters: dict[str, int]) -> int:
    """
    读取一个 Parquet 文件，按类别限额提取图片和标注。
    返回本批次保存的图片总数。
    """
    try:
        import pyarrow.parquet as pq  # type: ignore
    except ImportError:
        print("[错误] 缺少 pyarrow，请运行: pip install pyarrow", file=sys.stderr)
        sys.exit(1)

    table = pq.read_table(str(parquet_path))
    saved = 0

    for row_idx in tqdm(range(table.num_rows), desc=f"  处理 {parquet_path.name}", leave=False):
        row_id = int(table["id"][row_idx].as_py())
        image_data = table["image"][row_idx].as_py()
        objects = table["objects"][row_idx].as_py()

        if not objects or not image_data:
            continue

        bboxes: list[list[float]] = [obj["bb"] for obj in objects]
        labels: list[str] = [obj["label"] for obj in objects]

        # 找出这张图片主要对应哪个 VSB-TUO 类别（取第一个有效标签）
        primary_label = None
        for label in labels:
            if label in MAX_PER_CLASS and MAX_PER_CLASS[label] > 0:
                primary_label = label
                break
        if primary_label is None:
            continue

        # 检查配额
        if counters[primary_label] >= MAX_PER_CLASS[primary_label]:
            continue

        # 确定目标 ID（确保有有效的目标类别）
        has_valid_target = any(VSB_TO_TARGET_ID.get(l, -1) >= 0 for l in labels)
        if not has_valid_target:
            continue

        # 保存图片和标注
        img_filename = f"{primary_label}_{row_id:06d}.jpg"
        label_filename = f"{primary_label}_{row_id:06d}.txt"
        img_path = OUT_ROOT / "images" / img_filename
        label_path = OUT_ROOT / "labels" / label_filename

        # 获取图片字节
        if isinstance(image_data, dict):
            img_bytes = image_data.get("bytes") or b""
        elif isinstance(image_data, bytes):
            img_bytes = image_data
        else:
            img_bytes = b""

        if not img_bytes:
            continue

        if save_image_and_label(img_bytes, bboxes, labels, img_path, label_path):
            counters[primary_label] += 1
            saved += 1

    return saved


def download_vsb_bounding_boxes() -> None:
    """下载 VSB-TUO 的原始标注 ZIP（仅 5 MB，用于参考）。"""
    url = "https://zenodo.org/api/records/4694695/files/Bouding_Boxes.zip/content"
    dest = OUT_ROOT.parent / "vsb-tuo" / "Bouding_Boxes.zip"
    if dest.exists():
        print(f"[跳过] 标注 ZIP 已存在: {dest}")
        return
    print("[下载] VSB-TUO 原始标注索引（约 5 MB）...")
    download_file(url, dest, desc="Bouding_Boxes.zip")


def write_summary(counters: dict[str, int]) -> None:
    """写入下载统计报告。"""
    summary = {
        "vsb_tuo_class_counts": dict(counters),
        "target_class_totals": defaultdict(int),
        "target_classes": TARGET_CLASSES,
        "vsb_to_target": VSB_TO_TARGET_ID,
    }
    for vsb_label, count in counters.items():
        target_id = VSB_TO_TARGET_ID.get(vsb_label, -1)
        if target_id >= 0:
            summary["target_class_totals"][str(target_id)] += count

    report_path = OUT_ROOT / "download_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n下载报告已保存至: {report_path}")

    print("\n── 各 VSB-TUO 类别下载数量 ──")
    for vsb_label, count in sorted(counters.items()):
        target_id = VSB_TO_TARGET_ID.get(vsb_label, -1)
        target_name = TARGET_CLASSES.get(target_id, "（跳过）")
        quota = MAX_PER_CLASS.get(vsb_label, 0)
        print(f"  {vsb_label:<20} → {target_name:<15} {count:>4}/{quota} 张")

    print("\n── 目标类别合计 ──")
    for tid, count in sorted(summary["target_class_totals"].items(), key=lambda x: int(x[0])):
        name = TARGET_CLASSES.get(int(tid), "?")
        print(f"  [{tid}] {name:<15} {count:>4} 张")


def main() -> None:
    print("=" * 60)
    print("木材缺陷数据集下载脚本（HuggingFace VSB-TUO 版本）")
    print("=" * 60)

    # 确保 pyarrow 可用
    try:
        import pyarrow  # noqa: F401
    except ImportError:
        print("[安装] 正在安装 pyarrow...")
        os.system(f"{sys.executable} -m pip install pyarrow -q")

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    (OUT_ROOT / "images").mkdir(exist_ok=True)
    (OUT_ROOT / "labels").mkdir(exist_ok=True)

    # 下载 VSB-TUO 原始标注 ZIP（参考用）
    download_vsb_bounding_boxes()

    # 每类计数器
    counters: dict[str, int] = defaultdict(int)
    total_saved = 0

    # 逐个 Parquet 文件处理
    parquet_dir = OUT_ROOT / "_parquet_cache"
    parquet_dir.mkdir(exist_ok=True)

    for pq_filename in PARQUET_FILES:
        pq_url = f"{HF_BASE}/{pq_filename}"
        pq_local = parquet_dir / pq_filename

        # 检查是否所有需要的类别都已满配额
        all_full = all(
            counters[cls] >= quota
            for cls, quota in MAX_PER_CLASS.items()
            if quota > 0
        )
        if all_full:
            print("[完成] 所有类别均已达到配额，停止下载。")
            break

        # 检查本文件是否有任何类别还未满（才值得下载/处理）
        any_needed = any(
            counters[cls] < quota
            for cls, quota in MAX_PER_CLASS.items()
            if quota > 0
        )
        if not any_needed:
            print(f"[跳过] {pq_filename}（所有类别已满）")
            continue

        # 下载 Parquet 文件
        if not pq_local.exists():
            print(f"\n[下载] {pq_filename} （约 440 MB）...")
            if not download_file(pq_url, pq_local, desc=pq_filename):
                print(f"  [跳过] 下载失败，继续下一个文件")
                continue
        else:
            # 检查文件完整性（简单：>400MB 认为完整）
            file_size_mb = pq_local.stat().st_size / (1024 * 1024)
            if file_size_mb < 400:
                print(f"\n[重新下载] {pq_filename} 不完整（{file_size_mb:.0f} MB），重新下载...")
                pq_local.unlink()
                if not download_file(pq_url, pq_local, desc=pq_filename):
                    print(f"  [跳过] 下载失败，继续下一个文件")
                    continue
            else:
                print(f"\n[缓存] {pq_filename} 已完整（{file_size_mb:.0f} MB），直接读取")

        # 处理 Parquet
        batch_saved = process_parquet(pq_local, counters)
        total_saved += batch_saved
        print(f"  本批次保存: {batch_saved} 张，累计: {total_saved} 张")


    # 输出统计
    write_summary(counters)
    print(f"\n[完成] 共保存 {total_saved} 张图片至: {OUT_ROOT}")
    print(f"图片目录: {OUT_ROOT / 'images'}")
    print(f"标注目录: {OUT_ROOT / 'labels'}")


if __name__ == "__main__":
    main()
