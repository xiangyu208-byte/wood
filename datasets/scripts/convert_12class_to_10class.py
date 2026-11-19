"""Convert the reviewed 12-class dataset into the official 10-class dataset.

The low-resource ``insect_damage`` and ``mold`` classes are removed.  Old
class ids 10 and 11 are remapped to 8 and 9.  Images that contain no retained
objects are omitted, so every copied image has a useful YOLO label.
"""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


SOURCE_NAMES = (
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
)
TARGET_NAMES = (
    "dry_knot",
    "sound_knot",
    "edge_knot",
    "small_knot",
    "split",
    "wave",
    "decay",
    "large_hole",
    "bark_pocket",
    "stain",
)
CLASS_REMAP = {**{class_id: class_id for class_id in range(8)}, 10: 8, 11: 9}
DROPPED_NAMES = {8: "insect_damage", 9: "mold"}
SPLITS = ("train", "val", "test")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def parse_names(data_yaml: Path) -> tuple[str, ...]:
    names: dict[int, str] = {}
    in_names = False
    for line in data_yaml.read_text(encoding="utf-8-sig").splitlines():
        if line.strip() == "names:":
            in_names = True
            continue
        if not in_names or not line.strip():
            continue
        if not line.startswith((" ", "\t")):
            break
        key, value = line.strip().split(":", 1)
        names[int(key)] = value.strip().split("#", 1)[0].strip()
    return tuple(names[index] for index in sorted(names))


def convert_label(label_path: Path) -> tuple[list[str], list[int], Counter[int]]:
    rows: list[str] = []
    classes: set[int] = set()
    dropped: Counter[int] = Counter()
    for line_number, raw_line in enumerate(
        label_path.read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        parts = raw_line.split()
        if len(parts) != 5:
            raise ValueError(f"{label_path}:{line_number}: invalid YOLO row")
        old_id = int(parts[0])
        if old_id in DROPPED_NAMES:
            dropped[old_id] += 1
            continue
        if old_id not in CLASS_REMAP:
            raise ValueError(f"{label_path}:{line_number}: unexpected class id {old_id}")
        new_id = CLASS_REMAP[old_id]
        rows.append(" ".join((str(new_id), *parts[1:])))
        classes.add(new_id)
    return rows, sorted(classes), dropped


def load_manifest(path: Path) -> dict[tuple[str, str], dict]:
    if not path.exists():
        return {}
    result: dict[tuple[str, str], dict] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        result[(item["split"], item["file"])] = item
    return result


def write_data_yaml(target: Path) -> None:
    lines = [
        "path: .",
        "train: images/train",
        "val: images/val",
        "test: images/test",
        "",
        "names:",
    ]
    lines.extend(f"  {index}: {name}" for index, name in enumerate(TARGET_NAMES))
    (target / "data.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def convert(source: Path, target: Path) -> dict:
    source = source.resolve()
    target = target.resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"source dataset does not exist: {source}")
    if target.exists() and any(target.iterdir()):
        raise FileExistsError(f"target must not exist or must be empty: {target}")

    actual_names = parse_names(source / "data.yaml")
    accepted_names = {SOURCE_NAMES, (*SOURCE_NAMES[:10], "bark_pocket", "stain")}
    if actual_names not in accepted_names:
        raise ValueError(f"unexpected source class contract: {actual_names!r}")

    manifest = load_manifest(source / "metadata" / "images.jsonl")
    target.mkdir(parents=True, exist_ok=True)
    (target / "metadata").mkdir(parents=True, exist_ok=True)

    split_images: Counter[str] = Counter()
    split_objects: Counter[str] = Counter()
    class_images: Counter[int] = Counter()
    class_objects: Counter[int] = Counter()
    dropped_objects: Counter[int] = Counter()
    dropped_images: Counter[int] = Counter()
    kept_manifest: list[dict] = []
    kept_sources: set[str] = set()

    for split in SPLITS:
        image_dir = source / "images" / split
        label_dir = source / "labels" / split
        target_images = target / "images" / split
        target_labels = target / "labels" / split
        target_images.mkdir(parents=True, exist_ok=True)
        target_labels.mkdir(parents=True, exist_ok=True)

        images = sorted(
            path
            for path in image_dir.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        )
        for image_path in images:
            label_path = label_dir / f"{image_path.stem}.txt"
            if not label_path.exists():
                raise FileNotFoundError(f"missing label for {image_path}")
            rows, classes, dropped = convert_label(label_path)
            for class_id, count in dropped.items():
                dropped_objects[class_id] += count
                dropped_images[class_id] += 1
            if not rows:
                continue

            shutil.copy2(image_path, target_images / image_path.name)
            (target_labels / label_path.name).write_text("\n".join(rows) + "\n", encoding="utf-8")
            split_images[split] += 1
            split_objects[split] += len(rows)
            for class_id in classes:
                class_images[class_id] += 1
            for row in rows:
                class_objects[int(row.split()[0])] += 1

            item = dict(manifest.get((split, image_path.name), {}))
            item.update(
                {
                    "file": image_path.name,
                    "split": split,
                    "classes": classes,
                    "objects": len(rows),
                }
            )
            item.setdefault("source", "unknown")
            item.setdefault("source_ref", image_path.name)
            item.setdefault("annotation_quality", "unknown")
            kept_sources.add(item["source"])
            kept_manifest.append(item)

    with (target / "metadata" / "images.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for item in kept_manifest:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")

    source_manifest_path = source / "metadata" / "sources.json"
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8-sig"))
    filtered_sources = {
        name: details for name, details in source_manifest.items() if name in kept_sources
    }
    (target / "metadata" / "sources.json").write_text(
        json.dumps(filtered_sources, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_data_yaml(target)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(source),
        "target": str(target),
        "decision": "remove insect_damage and mold because the reviewed data cannot support stable training or evaluation",
        "source_class_count": 12,
        "target_class_count": 10,
        "class_remap": {str(old): new for old, new in CLASS_REMAP.items()},
        "dropped_classes": {str(key): value for key, value in DROPPED_NAMES.items()},
        "images": sum(split_images.values()),
        "objects": sum(split_objects.values()),
        "images_by_split": dict(split_images),
        "objects_by_split": dict(split_objects),
        "class_images": {
            TARGET_NAMES[index]: class_images[index] for index in range(len(TARGET_NAMES))
        },
        "class_objects": {
            TARGET_NAMES[index]: class_objects[index] for index in range(len(TARGET_NAMES))
        },
        "dropped_image_occurrences": {
            DROPPED_NAMES[index]: dropped_images[index] for index in DROPPED_NAMES
        },
        "dropped_objects": {
            DROPPED_NAMES[index]: dropped_objects[index] for index in DROPPED_NAMES
        },
    }
    (target / "metadata" / "conversion_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    datasets_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=datasets_dir / "wood_defect_12class")
    parser.add_argument("--target", type=Path, default=datasets_dir / "wood_defect_10class")
    args = parser.parse_args()
    print(json.dumps(convert(args.source, args.target), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
