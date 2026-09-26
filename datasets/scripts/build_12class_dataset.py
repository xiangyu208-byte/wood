"""Assemble the reviewed 12-class YOLO dataset from local source caches.

No pith/marrow annotation is imported.  Pixel masks are converted to bounding
boxes.  Reviewed Openverse images are weakly annotated and restricted to the
training split; their provenance remains in ``metadata/images.jsonl``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import shutil
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np
import pyarrow.parquet as pq
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "wood_defect_12class"
META_DIR = OUT / "metadata"

CLASSES = [
    "dry_knot",
    "sound_knot",
    "edge_knot",
    "small_knot",
    "split",
    "wave",
    "decay",
    "large_hole",
    "insect_damage",
    "mold",
    "bark_loss",
    "stain",
]

VSB_MAP = {
    "Dead_Knot": 0,
    "Live_Knot": 1,
    "Crack": 4,
    "knot_with_crack": 4,
    "Knot_missing": 7,
    "Blue_Stain": 11,
    "Quartzity": 11,
}
VSB_TRIGGER = {"Knot_missing", "Blue_Stain", "Quartzity"}

# Two visually unambiguous mold close-ups are reserved only to make class 9
# observable in validation/test.  They remain explicitly tagged as weak labels.
OPENVERSE_SPLIT_OVERRIDES = {
    "d2e9d61d-3d75-44b1-ac5b-5868a83c0e9e": "val",
    "14782ce5-ceca-4e92-bbdb-1bb97fdffff9": "test",
}

SOURCES = {
    "zenodo6": {
        "url": "https://zenodo.org/records/18205890",
        "license": "CC BY 4.0",
        "annotation": "original YOLO boxes",
    },
    "vsb": {
        "url": "https://huggingface.co/datasets/iluvvatar/wood_surface_defects",
        "license": "CC BY 4.0",
        "annotation": "original YOLO boxes; marrow, resin and overgrown excluded",
    },
    "spruce_bark": {
        "url": "https://huggingface.co/datasets/jakobkreft/spruce-log-bark-segmentation",
        "license": "CC BY 4.0",
        "annotation": "class-2 masks converted to boxes",
    },
    "oak_rot": {
        "url": "https://huggingface.co/datasets/nrodgers98/Oak-Defect-Detection",
        "license": "CC BY-NC 4.0",
        "annotation": "BlackRot/YellowRot masks converted to boxes",
    },
    "mvtec_hole": {
        "url": "https://www.mvtec.com/research-teaching/datasets/mvtec-ad",
        "license": "CC BY-NC-SA 4.0",
        "annotation": "wood/hole masks converted to insect-hole proxy boxes",
    },
    "tree_cavity": {
        "url": "https://huggingface.co/datasets/neolam2024/Tree-Cavity",
        "license": "Apache-2.0",
        "annotation": "visually reviewed weak full-image boxes; train only",
    },
    "wikimedia": {
        "url": "https://commons.wikimedia.org/",
        "license": "per-image Creative Commons/Public Domain; see images.jsonl",
        "annotation": "visually reviewed weak full-image boxes; train only",
    },
    "openverse": {
        "url": "https://openverse.org/",
        "license": "per-image CC0/PDM/CC BY; see images.jsonl",
        "annotation": "reviewed weak full-image boxes; two mold audit images are reserved for val/test",
    },
}


def stable_split(key: str, train: int = 80, val: int = 10) -> str:
    bucket = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16) % 100
    if bucket < train:
        return "train"
    if bucket < train + val:
        return "val"
    return "test"


def image_dir(split: str) -> Path:
    return OUT / "images" / split


def label_dir(split: str) -> Path:
    return OUT / "labels" / split


def ensure_empty_output() -> None:
    existing = []
    for kind in ("images", "labels"):
        base = OUT / kind
        if base.exists():
            existing.extend(path for path in base.rglob("*") if path.is_file())
    if existing:
        raise SystemExit(
            f"output already contains {len(existing)} files; move it aside before rebuilding: {OUT}"
        )
    for split in ("train", "val", "test"):
        image_dir(split).mkdir(parents=True, exist_ok=True)
        label_dir(split).mkdir(parents=True, exist_ok=True)
    META_DIR.mkdir(parents=True, exist_ok=True)


def normalise_box(box: tuple[float, float, float, float], width: int, height: int) -> tuple[float, ...]:
    x, y, w, h = box
    return ((x + w / 2) / width, (y + h / 2) / height, w / width, h / height)


def boxes_from_mask(mask: np.ndarray, *, min_fraction: float = 0.0002) -> list[tuple[float, ...]]:
    binary = (mask > 0).astype(np.uint8)
    height, width = binary.shape[:2]
    count, _, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    minimum = max(20, int(width * height * min_fraction))
    boxes: list[tuple[float, ...]] = []
    for component in range(1, count):
        x, y, w, h, area = map(int, stats[component])
        if area >= minimum and w >= 3 and h >= 3:
            boxes.append(normalise_box((x, y, w, h), width, height))
    if not boxes and binary.any():
        y, x = np.where(binary > 0)
        x0, x1, y0, y1 = int(x.min()), int(x.max()), int(y.min()), int(y.max())
        boxes.append(normalise_box((x0, y0, x1 - x0 + 1, y1 - y0 + 1), width, height))
    return boxes


def write_sample(
    *,
    split: str,
    stem: str,
    image: Image.Image | bytes,
    labels: list[tuple[int, tuple[float, float, float, float]]],
    source: str,
    quality: str,
    records: list[dict],
    source_ref: str,
    extra: dict | None = None,
) -> None:
    destination_image = image_dir(split) / f"{stem}.jpg"
    destination_label = label_dir(split) / f"{stem}.txt"
    if isinstance(image, bytes):
        pil = Image.open(io.BytesIO(image)).convert("RGB")
    else:
        pil = image.convert("RGB")
    pil.thumbnail((2800, 2800), Image.Resampling.LANCZOS)
    pil.save(destination_image, "JPEG", quality=92, optimize=True)
    destination_label.write_text(
        "".join(
            f"{class_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n"
            for class_id, (cx, cy, w, h) in labels
        ),
        encoding="utf-8",
    )
    record = {
        "file": destination_image.name,
        "split": split,
        "source": source,
        "source_ref": source_ref,
        "annotation_quality": quality,
        "classes": sorted({class_id for class_id, _ in labels}),
        "objects": len(labels),
    }
    if extra:
        record.update(extra)
    records.append(record)


def add_zenodo6(records: list[dict]) -> None:
    archive = ROOT / "raw" / "zenodo-wooddefect" / "wood_defect_detection.zip"
    if not archive.exists():
        raise FileNotFoundError(archive)
    with zipfile.ZipFile(archive) as package:
        names = set(package.namelist())
        for member in sorted(names):
            if "/images/" not in member or not member.lower().endswith(".jpg"):
                continue
            parts = member.split("/")
            split = parts[-2]
            if split not in {"train", "val", "test"}:
                continue
            stem = Path(member).stem
            label_member = member.replace("/images/", "/labels/").rsplit(".", 1)[0] + ".txt"
            if label_member not in names:
                continue
            lines = package.read(label_member).decode("utf-8").splitlines()
            labels = []
            for line in lines:
                values = line.split()
                if len(values) != 5:
                    continue
                class_id = int(values[0])
                if not 0 <= class_id <= 5:
                    raise ValueError(f"unexpected original class {class_id}: {label_member}")
                labels.append((class_id, tuple(map(float, values[1:5]))))
            write_sample(
                split=split,
                stem=f"zenodo6_{stem}",
                image=package.read(member),
                labels=labels,
                source="zenodo6",
                quality="strong",
                records=records,
                source_ref=member,
            )


def add_vsb(records: list[dict]) -> None:
    parquet_files = sorted(ROOT.glob("**/hf-vsb-tuo/_parquet_cache/*.parquet"))
    if len(parquet_files) != 5:
        raise FileNotFoundError(f"expected 5 VSB parquet shards, found {len(parquet_files)}")
    seen: set[int] = set()
    for parquet_file in parquet_files:
        table = pq.read_table(parquet_file)
        for row in table.to_pylist():
            row_id = int(row["id"])
            objects = row.get("objects") or []
            labels_in_image = {item["label"] for item in objects}
            if not labels_in_image.intersection(VSB_TRIGGER) or row_id in seen:
                continue
            labels = [
                (VSB_MAP[item["label"]], tuple(map(float, item["bb"])))
                for item in objects
                if item["label"] in VSB_MAP
            ]
            if not labels:
                continue
            image_data = row["image"]
            image_bytes = image_data.get("bytes") if isinstance(image_data, dict) else image_data
            if not image_bytes:
                continue
            seen.add(row_id)
            group = str(row_id)[:-3] or str(row_id)
            split = stable_split(f"vsb:{group}")
            write_sample(
                split=split,
                stem=f"vsb_{row_id}",
                image=image_bytes,
                labels=labels,
                source="vsb",
                quality="strong",
                records=records,
                source_ref=f"{parquet_file.name}:{row_id}",
            )


def add_spruce_bark(records: list[dict]) -> None:
    root = ROOT / "raw" / "hf-spruce-bark"
    table = pq.read_table(root / "train.parquet")
    rows = {item["path"]: item["bytes"] for item in table.column("image").to_pylist()}
    mapping: dict[str, str] = {}
    with (root / "name_mapping.csv").open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            mapping[row["new_name"]] = row["original_name"]
    for image_name in sorted(name for name in rows if name.lower().endswith(".jpg")):
        stem = Path(image_name).stem
        mask_name = f"{stem}_mask.png"
        if mask_name not in rows:
            continue
        mask = np.array(Image.open(io.BytesIO(rows[mask_name])))
        boxes = boxes_from_mask((mask == 2).astype(np.uint8), min_fraction=0.0001)
        if not boxes:
            continue
        original = mapping.get(stem, stem)
        source_group = original.split("_r", 1)[0]
        split = stable_split(f"spruce:{source_group}")
        write_sample(
            split=split,
            stem=f"spruce_{stem}",
            image=rows[image_name],
            labels=[(10, box) for box in boxes],
            source="spruce_bark",
            quality="strong-mask-derived",
            records=records,
            source_ref=image_name,
            extra={"source_group": source_group},
        )


def add_oak_rot(records: list[dict]) -> None:
    root = ROOT / "raw" / "hf-oak-rot"
    manifest = json.loads((root / "selection_manifest.json").read_text(encoding="utf-8"))
    for item in manifest["images"]:
        image_path = Path(item["local_image"])
        image = Image.open(image_path).convert("RGB")
        combined: np.ndarray | None = None
        for mask_record in item["masks"]:
            mask = np.array(Image.open(mask_record["local"]).convert("L")) > 0
            combined = mask if combined is None else np.logical_or(combined, mask)
        if combined is None:
            continue
        boxes = boxes_from_mask(combined.astype(np.uint8), min_fraction=0.0001)
        if not boxes:
            continue
        base = image_path.stem.replace("_Col", "")
        source_group = base.replace("_Top", "").replace("_Bot", "")
        split = stable_split(f"oak:{source_group}")
        safe_stem = "oak_" + base.replace(".", "-")
        write_sample(
            split=split,
            stem=safe_stem,
            image=image,
            labels=[(6, box) for box in boxes],
            source="oak_rot",
            quality="strong-mask-derived",
            records=records,
            source_ref=item["remote_image"],
            extra={"source_group": source_group},
        )


def add_mvtec_holes(records: list[dict]) -> None:
    root = ROOT / "raw" / "hf-mvtec-wood-hole"
    for image_path in sorted((root / "image").glob("*.png")):
        mask_path = root / "mask" / f"{image_path.stem}_mask.png"
        if not mask_path.exists():
            continue
        mask = np.array(Image.open(mask_path).convert("L"))
        boxes = boxes_from_mask(mask, min_fraction=0.00002)
        if not boxes:
            continue
        split = stable_split(f"mvtec-hole:{image_path.stem}")
        write_sample(
            split=split,
            stem=f"mvtec_hole_{image_path.stem}",
            image=Image.open(image_path),
            labels=[(8, box) for box in boxes],
            source="mvtec_hole",
            quality="proxy-strong-mask-derived",
            records=records,
            source_ref=f"wood/hole/{image_path.name}",
        )


def add_tree_cavity(records: list[dict]) -> None:
    root = ROOT / "raw" / "hf-tree-cavity" / "images"
    accepted = json.loads((ROOT / "metadata" / "tree_cavity_accept.json").read_text(encoding="utf-8"))
    for filename in accepted:
        image_path = root / filename
        if not image_path.exists():
            raise FileNotFoundError(image_path)
        write_sample(
            split=OPENVERSE_SPLIT_OVERRIDES.get(item_id, "train"),
            stem=f"tree_cavity_{image_path.stem}",
            image=Image.open(image_path),
            labels=[(7, (0.5, 0.5, 0.98, 0.98))],
            source="tree_cavity",
            quality="weak-reviewed-full-image",
            records=records,
            source_ref=f"images/{filename}",
        )


def add_wikimedia(records: list[dict]) -> None:
    metadata_root = ROOT / "metadata"
    candidates = json.loads((metadata_root / "wikimedia_candidates.json").read_text(encoding="utf-8"))
    accepted = json.loads((metadata_root / "wikimedia_accept.json").read_text(encoding="utf-8"))
    accepted_lookup = {
        int(page_id): class_name for class_name, page_ids in accepted.items() for page_id in page_ids
    }
    by_id = {int(item["page_id"]): item for item in candidates}
    missing = sorted(set(accepted_lookup) - set(by_id))
    if missing:
        raise ValueError(f"accepted Wikimedia page ids missing from candidate manifest: {missing}")
    class_ids = {"decay": 6, "insect_damage": 8}
    for page_id, class_name in sorted(accepted_lookup.items()):
        item = by_id[page_id]
        write_sample(
            split="train",
            stem=f"wikimedia_{class_name}_{page_id}",
            image=Image.open(item["local_path"]),
            labels=[(class_ids[class_name], (0.5, 0.5, 0.98, 0.98))],
            source="wikimedia",
            quality="weak-reviewed-full-image",
            records=records,
            source_ref=item["description_url"],
            extra={
                "wikimedia_page_id": page_id,
                "title": item.get("title"),
                "artist": item.get("artist"),
                "license": item.get("license"),
                "license_url": item.get("license_url"),
            },
        )


def add_openverse(records: list[dict]) -> None:
    metadata_root = ROOT / "metadata"
    candidates = json.loads((metadata_root / "openverse_candidates.json").read_text(encoding="utf-8"))
    accepted = json.loads((metadata_root / "openverse_accept.json").read_text(encoding="utf-8"))
    accepted_lookup = {
        item_id: class_name for class_name, ids in accepted.items() for item_id in ids
    }
    by_id = {item["id"]: item for item in candidates}
    missing = sorted(set(accepted_lookup) - set(by_id))
    if missing:
        raise ValueError(f"accepted Openverse ids missing from candidate manifest: {missing}")
    class_ids = {"decay": 6, "insect_damage": 8, "mold": 9}
    for item_id, class_name in sorted(accepted_lookup.items()):
        item = by_id[item_id]
        image_path = Path(item["local_path"])
        write_sample(
            split="train",
            stem=f"openverse_{class_name}_{item_id[:12]}",
            image=Image.open(image_path),
            labels=[(class_ids[class_name], (0.5, 0.5, 0.98, 0.98))],
            source="openverse",
            quality="weak-reviewed-full-image",
            records=records,
            source_ref=item["foreign_landing_url"],
            extra={
                "openverse_id": item_id,
                "title": item.get("title"),
                "creator": item.get("creator"),
                "license": item.get("license"),
                "license_url": item.get("license_url"),
            },
        )


def deduplicate(records: list[dict]) -> int:
    """Remove byte-identical generated images and merge any distinct labels.

    Train is scanned before val/test so a duplicate can never leak from train
    into an evaluation split.  Only files under this builder's output folders
    are touched.
    """
    seen: dict[str, tuple[str, str]] = {}
    removed: set[tuple[str, str]] = set()
    count = 0
    for split in ("train", "val", "test"):
        for image_path in sorted(image_dir(split).glob("*.jpg")):
            digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
            if digest not in seen:
                seen[digest] = (split, image_path.stem)
                continue
            keep_split, keep_stem = seen[digest]
            keep_label = label_dir(keep_split) / f"{keep_stem}.txt"
            duplicate_label = label_dir(split) / f"{image_path.stem}.txt"
            merged = list(dict.fromkeys(
                keep_label.read_text(encoding="utf-8").splitlines()
                + duplicate_label.read_text(encoding="utf-8").splitlines()
            ))
            keep_label.write_text("\n".join(merged) + ("\n" if merged else ""), encoding="utf-8")
            image_path.unlink()
            duplicate_label.unlink()
            removed.add((split, image_path.name))
            count += 1
    records[:] = [
        record for record in records if (record["split"], record["file"]) not in removed
    ]
    record_by_key = {(record["split"], Path(record["file"]).stem): record for record in records}
    for (split, stem), record in record_by_key.items():
        lines = (label_dir(split) / f"{stem}.txt").read_text(encoding="utf-8").splitlines()
        record["objects"] = len(lines)
        record["classes"] = sorted({int(line.split()[0]) for line in lines if line.strip()})
    return count


def validate(records: list[dict]) -> dict:
    image_counts: Counter[int] = Counter()
    object_counts: Counter[int] = Counter()
    split_counts: Counter[str] = Counter()
    split_image_counts: dict[str, Counter[int]] = {
        "train": Counter(),
        "val": Counter(),
        "test": Counter(),
    }
    source_counts: Counter[str] = Counter()
    issues: list[str] = []
    hashes: dict[str, str] = {}
    for split in ("train", "val", "test"):
        images = sorted(image_dir(split).glob("*.jpg"))
        labels = sorted(label_dir(split).glob("*.txt"))
        if {path.stem for path in images} != {path.stem for path in labels}:
            issues.append(f"image/label stem mismatch in {split}")
        split_counts[split] = len(images)
        for image_path in images:
            digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
            if digest in hashes:
                issues.append(f"duplicate image: {image_path} == {hashes[digest]}")
            hashes[digest] = str(image_path)
            found_classes: set[int] = set()
            for line_number, line in enumerate((label_dir(split) / f"{image_path.stem}.txt").read_text().splitlines(), 1):
                values = line.split()
                if len(values) != 5:
                    issues.append(f"bad label width: {image_path.stem}:{line_number}")
                    continue
                class_id = int(values[0])
                coords = list(map(float, values[1:]))
                if not 0 <= class_id < len(CLASSES):
                    issues.append(f"bad class: {image_path.stem}:{line_number}")
                if not all(0 < value <= 1 for value in coords[2:]) or not all(0 <= value <= 1 for value in coords[:2]):
                    issues.append(f"bad box: {image_path.stem}:{line_number}")
                object_counts[class_id] += 1
                found_classes.add(class_id)
            for class_id in found_classes:
                image_counts[class_id] += 1
                split_image_counts[split][class_id] += 1
    for record in records:
        source_counts[record["source"]] += 1
    for class_id in range(len(CLASSES)):
        if image_counts[class_id] == 0:
            issues.append(f"class {class_id} {CLASSES[class_id]} has zero images")
        for required_split in ("train", "val"):
            if split_image_counts[required_split][class_id] == 0:
                issues.append(
                    f"class {class_id} {CLASSES[class_id]} has zero images in {required_split}"
                )
    return {
        "ok": not issues,
        "issues": issues,
        "images_total": sum(split_counts.values()),
        "objects_total": sum(object_counts.values()),
        "images_by_split": dict(split_counts),
        "images_by_source": dict(source_counts),
        "images_by_class_and_split": {
            split: {str(class_id): counts[class_id] for class_id in range(len(CLASSES))}
            for split, counts in split_image_counts.items()
        },
        "class_stats": {
            str(class_id): {
                "name": CLASSES[class_id],
                "images": image_counts[class_id],
                "objects": object_counts[class_id],
            }
            for class_id in range(len(CLASSES))
        },
    }


def write_metadata(records: list[dict], report: dict) -> None:
    (META_DIR / "images.jsonl").write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    (META_DIR / "sources.json").write_text(
        json.dumps(SOURCES, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (META_DIR / "validation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    yaml = [
        f"path: {OUT.as_posix()}",
        "train: images/train",
        "val: images/val",
        "test: images/test",
        "",
        "names:",
    ]
    yaml.extend(f"  {index}: {name}" for index, name in enumerate(CLASSES))
    (OUT / "data.yaml").write_text("\n".join(yaml) + "\n", encoding="utf-8")
    lines = [
        "# 12-class dataset validation",
        "",
        f"- status: {'PASS' if report['ok'] else 'FAIL'}",
        f"- images: {report['images_total']}",
        f"- objects: {report['objects_total']}",
        f"- split: {report['images_by_split']}",
        "",
        "| id | class | images | objects |",
        "|---:|---|---:|---:|",
    ]
    for class_id, item in report["class_stats"].items():
        lines.append(f"| {class_id} | {item['name']} | {item['images']} | {item['objects']} |")
    if report["issues"]:
        lines.extend(["", "## Issues", ""] + [f"- {issue}" for issue in report["issues"]])
    (META_DIR / "validation_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    ensure_empty_output()
    records: list[dict] = []
    stages = [
        ("original six classes", add_zenodo6),
        ("VSB holes/stains", add_vsb),
        ("spruce bark loss", add_spruce_bark),
        ("oak rot", add_oak_rot),
        ("MVTec hole proxy", add_mvtec_holes),
        ("reviewed tree cavities", add_tree_cavity),
        ("reviewed Wikimedia defects", add_wikimedia),
        ("reviewed Openverse weak labels", add_openverse),
    ]
    for label, function in stages:
        before = len(records)
        function(records)
        print(f"{label}: +{len(records) - before} images")
    removed = deduplicate(records)
    print(f"deduplication: -{removed} duplicate images")
    report = validate(records)
    write_metadata(records, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["ok"]:
        raise SystemExit("dataset validation failed")


if __name__ == "__main__":
    main()
