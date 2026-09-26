"""
专项脚本：下载并提取 Parquet 4（train-00004）中的剩余类别

修复两个问题：
1. 断点续传：使用 Range 请求支持恢复中断的下载
2. 多标签修复：一张图片可以为多个不同目标类别各计一张

目标：补充 Blue_Stain→stain、Knot_missing→large_hole、
       dead_knot→dry_knot、live_knot→sound_knot 这四类数据
"""

from __future__ import annotations

import io
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests
from PIL import Image
from tqdm import tqdm

# ─── 路径配置 ──────────────────────────────────────────────────────────────────
OUT_ROOT = Path(__file__).resolve().parents[1] / "raw" / "hf-vsb-tuo"
PARQUET_DIR = OUT_ROOT / "_parquet_cache"
IMAGES_DIR = OUT_ROOT / "images"
LABELS_DIR = OUT_ROOT / "labels"
REPORT_PATH = OUT_ROOT / "download_report.json"

# 只处理 Parquet 4（其他文件已处理）
TARGET_FILE = "train-00004-of-00005-cfde1ad8fb3dd17a.parquet"
HF_URL = (
    "https://huggingface.co/datasets/iluvvatar/wood_surface_defects"
    "/resolve/main/data/" + TARGET_FILE
)

# 仅补充这四类（其余已有足够数量）
# NOTE: HuggingFace VSB-TUO 数据集标签名与原始不同，部分首字母大写
SUPPLEMENT_TARGETS = {
    "Blue_Stain":   ("stain",      11, 300),   # (目标名, ID, 配额)
    "Knot_missing": ("large_hole", 7,  300),
    "Dead_Knot":    ("dry_knot",   0,  150),
    "Live_Knot":    ("sound_knot", 1,  150),
}


# 从已有报告读取当前计数
def load_existing_counts() -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    if REPORT_PATH.exists():
        data = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        for vsb_label in SUPPLEMENT_TARGETS:
            counts[vsb_label] = data.get("vsb_tuo_class_counts", {}).get(vsb_label, 0)
    return counts


# ─── 断点续传下载 ──────────────────────────────────────────────────────────────
def download_with_resume(url: str, dest: Path, chunk_size: int = 1024 * 256) -> bool:
    """支持断点续传的下载，自动重试最多 5 次。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, 6):
        existing_size = dest.stat().st_size if dest.exists() else 0
        headers = {"Range": f"bytes={existing_size}-"} if existing_size > 0 else {}
        try:
            resp = requests.get(url, headers=headers, stream=True, timeout=120)
            if resp.status_code == 416:  # Range Not Satisfiable → 文件已完整
                print(f"  文件已完整，跳过下载")
                return True
            resp.raise_for_status()

            total = int(resp.headers.get("content-length", 0)) + existing_size
            mode = "ab" if existing_size > 0 else "wb"

            with dest.open(mode) as f, tqdm(
                desc=f"  {dest.name}（第{attempt}次）",
                total=total,
                initial=existing_size,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
            ) as bar:
                for chunk in resp.iter_content(chunk_size=chunk_size):
                    f.write(chunk)
                    bar.update(len(chunk))
            print(f"  下载完成（{dest.stat().st_size / 1024 / 1024:.0f} MB）")
            return True

        except Exception as exc:
            print(f"  [第{attempt}次失败] {exc}")
            if attempt < 5:
                wait = 10 * attempt
                print(f"  等待 {wait} 秒后重试...")
                time.sleep(wait)

    print(f"  [放弃] 5 次重试均失败")
    return False


# ─── 图片提取 ──────────────────────────────────────────────────────────────────
def extract_from_parquet(pq_path: Path, counts: dict[str, int]) -> int:
    try:
        import pyarrow.parquet as pq
    except ImportError:
        print("[错误] 缺少 pyarrow，请运行: pip install pyarrow")
        sys.exit(1)

    table = pq.read_table(str(pq_path))
    saved = 0

    for row_idx in tqdm(range(table.num_rows), desc=f"  提取 {pq_path.name}", leave=True):
        row_id = int(table["id"][row_idx].as_py())
        image_data = table["image"][row_idx].as_py()
        objects = table["objects"][row_idx].as_py()

        if not objects or not image_data:
            continue

        labels_in_row: list[str] = [obj["label"] for obj in objects]
        bboxes_in_row: list[list[float]] = [obj["bb"] for obj in objects]

        # NOTE: 修复多标签逻辑 —— 同一张图可贡献给多个目标类别
        # 但只保存一次物理图片，不同类别共用同一文件
        qualifying_labels = []
        for vsb_label, (target_name, target_id, quota) in SUPPLEMENT_TARGETS.items():
            if vsb_label in labels_in_row and counts[vsb_label] < quota:
                qualifying_labels.append(vsb_label)

        if not qualifying_labels:
            continue

        # 获取图片字节
        if isinstance(image_data, dict):
            img_bytes = image_data.get("bytes") or b""
        elif isinstance(image_data, bytes):
            img_bytes = image_data
        else:
            img_bytes = b""
        if not img_bytes:
            continue

        # 以第一个满足条件的 vsb_label 作为文件前缀保存一次
        primary_vsb = qualifying_labels[0]
        img_filename = f"{primary_vsb}_{row_id:06d}.jpg"
        lbl_filename = f"{primary_vsb}_{row_id:06d}.txt"
        img_path = IMAGES_DIR / img_filename
        lbl_path = LABELS_DIR / lbl_filename

        # 写图片
        try:
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            img.save(img_path, format="JPEG", quality=90)
        except Exception as exc:
            print(f"  [警告] 图片保存失败 row={row_id}: {exc}")
            continue

        # 写标注（包含所有 qualifying_labels 对应的框）
        lines = []
        for bb, label in zip(bboxes_in_row, labels_in_row):
            if label not in SUPPLEMENT_TARGETS:
                continue
            _, target_id, _ = SUPPLEMENT_TARGETS[label]
            cx, cy, w, h = bb
            lines.append(f"{target_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")

        lbl_path.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")

        # 更新所有满足条件的类别计数
        for vsb_label in qualifying_labels:
            counts[vsb_label] += 1
        saved += 1

    return saved


# ─── 主函数 ────────────────────────────────────────────────────────────────────
def main() -> None:
    print("=" * 60)
    print("Parquet 4 专项下载与提取脚本")
    print("=" * 60)

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    LABELS_DIR.mkdir(parents=True, exist_ok=True)

    # 读取现有计数
    counts = load_existing_counts()
    print("\n当前各类别已有数量：")
    for vsb_label, (target_name, _, quota) in SUPPLEMENT_TARGETS.items():
        print(f"  {vsb_label:20s} → {target_name:15s} {counts[vsb_label]:>4}/{quota}")

    # 检查是否还需要下载
    all_done = all(
        counts[vsb] >= quota
        for vsb, (_, _, quota) in SUPPLEMENT_TARGETS.items()
    )
    if all_done:
        print("\n[完成] 所有目标类别已达配额，无需继续。")
        return

    # 下载 Parquet 4（支持断点续传）
    pq_local = PARQUET_DIR / TARGET_FILE
    file_size_mb = pq_local.stat().st_size / 1024 / 1024 if pq_local.exists() else 0
    expected_mb = 419

    if file_size_mb >= expected_mb * 0.99:
        print(f"\n[缓存] {TARGET_FILE} 已完整（{file_size_mb:.0f} MB），直接提取")
    else:
        print(f"\n[下载] {TARGET_FILE}（已有 {file_size_mb:.0f} MB，目标 {expected_mb} MB）")
        print(f"  URL: {HF_URL}")
        if not download_with_resume(HF_URL, pq_local):
            print("\n[错误] 下载失败，退出")
            return

    # 提取数据
    print(f"\n[提取] 正在从 Parquet 4 中提取目标类别...")
    new_saved = extract_from_parquet(pq_local, counts)
    print(f"  新增保存: {new_saved} 张")

    # 保存更新后的报告
    total_target: dict[str, int] = defaultdict(int)
    for vsb_label, (_, target_id, _) in SUPPLEMENT_TARGETS.items():
        total_target[str(target_id)] += counts[vsb_label]

    # 合并原有报告
    report = {}
    if REPORT_PATH.exists():
        report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    vsb_counts = report.get("vsb_tuo_class_counts", {})
    for vsb_label, cnt in counts.items():
        vsb_counts[vsb_label] = cnt
    report["vsb_tuo_class_counts"] = vsb_counts

    existing_totals = report.get("target_class_totals", {})
    for tid, cnt in total_target.items():
        existing_totals[tid] = existing_totals.get(tid, 0) + cnt
    report["target_class_totals"] = existing_totals

    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # 打印最终统计
    print("\n-- 最终各类别数量 --")
    for vsb_label, (target_name, _, quota) in SUPPLEMENT_TARGETS.items():
        status = "[OK]" if counts[vsb_label] >= quota else "[MISSING]"
        print(f"  {vsb_label:20s} -> {target_name:15s} {counts[vsb_label]:>4}/{quota} {status}")

    total_imgs = len(list(IMAGES_DIR.glob("*.jpg")))
    print(f"\n图片目录总数: {total_imgs} 张")
    print(f"图片路径: {IMAGES_DIR}")


if __name__ == "__main__":
    main()
