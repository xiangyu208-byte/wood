"""Audit a 10- or 12-class YOLO wood-defect dataset without modifying it.

The audit checks the class contract, image/label pairing, image integrity,
YOLO syntax and box geometry, exact duplicates, augmentation-family leakage,
weak/placeholder annotations in evaluation splits, and known semantic mapping
mistakes from source datasets.  Results are written as JSON and Markdown so
the review is reproducible and easy to inspect.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image


CLASSES_12 = [
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
CLASSES_10 = [
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
]
SPLITS = ("train", "val", "test")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
AUGMENT_RE = re.compile(r"_aug_(?:hflip|vflip|rot180|bright_contrast)_\d+$")
YAML_CLASS_RE = re.compile(r"^\s*(\d+)\s*:\s*([A-Za-z0-9_-]+)\s*$")


def source_name(stem: str) -> str:
    rules = (
        ("zenodo", "zenodo"),
        ("vsb_", "vsb"),
        ("spruce_", "spruce_bark"),
        ("oak_", "oak_rot"),
        ("wsad_", "wsad"),
        ("tree_cavity_", "tree_cavity"),
        ("mvtec_", "mvtec"),
        ("insect_", "unreviewed_insect"),
        ("open_mold_", "openverse_mold"),
        ("open_decay_", "openverse_decay"),
        ("openverse_", "openverse"),
        ("wikimedia_", "wikimedia"),
    )
    for prefix, name in rules:
        if stem.startswith(prefix):
            return name
    return "unknown"


def family_name(stem: str) -> str:
    """Return a conservative source-family key for leakage checks."""
    base = AUGMENT_RE.sub("", stem)
    if base.startswith("oak_"):
        base = re.sub(r"_crop_\d+$", "", base)
        base = re.sub(r"_(?:Top|Bot)_Col$", "_Col", base)
    return base


def add_issue(issues: list[dict], severity: str, code: str, message: str, count: int = 1) -> None:
    issues.append({"severity": severity, "code": code, "count": count, "message": message})


def parse_yaml_classes(path: Path) -> dict[int, str]:
    if not path.exists():
        return {}
    result: dict[int, str] = {}
    in_names = False
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.strip() == "names:":
            in_names = True
            continue
        if in_names:
            match = YAML_CLASS_RE.match(line)
            if match:
                result[int(match.group(1))] = match.group(2)
            elif line.strip() and not line.startswith((" ", "\t")):
                break
    return result


def audit(root: Path, classes: list[str] | None = None) -> dict:
    issues: list[dict] = []
    split_images: Counter[str] = Counter()
    split_objects: Counter[str] = Counter()
    class_objects: Counter[int] = Counter()
    class_images: Counter[int] = Counter()
    class_objects_by_split: dict[str, Counter[int]] = {split: Counter() for split in SPLITS}
    class_images_by_split: dict[str, Counter[int]] = {split: Counter() for split in SPLITS}
    source_images_by_split: dict[str, Counter[str]] = {split: Counter() for split in SPLITS}
    placeholder_by_class: Counter[int] = Counter()
    placeholder_eval = 0
    reviewed_full_image_eval = 0
    invalid_lines = 0
    invalid_boxes = 0
    invalid_classes = 0
    corrupt_images = 0
    missing_labels = 0
    orphan_labels = 0
    exact_hashes: dict[str, list[tuple[str, str]]] = defaultdict(list)
    families: dict[str, set[str]] = defaultdict(set)
    blue_stain_as_mold = 0
    overgrown_as_bark_loss = 0
    weak_eval_images = 0
    all_image_paths: list[Path] = []

    yaml_classes = parse_yaml_classes(root / "data.yaml")
    if classes is None:
        classes = CLASSES_10 if len(yaml_classes) == 10 else CLASSES_12
    expected_map = dict(enumerate(classes))
    name_to_id = {name: class_id for class_id, name in expected_map.items()}
    if yaml_classes != expected_map:
        add_issue(
            issues,
            "error",
            "class_contract_mismatch",
            f"data.yaml names are {yaml_classes!r}; expected {expected_map!r}",
        )

    for split in SPLITS:
        image_dir = root / "images" / split
        label_dir = root / "labels" / split
        images = sorted(
            path for path in image_dir.glob("*") if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        ) if image_dir.exists() else []
        labels = sorted(label_dir.glob("*.txt")) if label_dir.exists() else []
        image_by_stem = {path.stem: path for path in images}
        label_by_stem = {path.stem: path for path in labels}
        missing = sorted(set(image_by_stem) - set(label_by_stem))
        orphaned = sorted(set(label_by_stem) - set(image_by_stem))
        missing_labels += len(missing)
        orphan_labels += len(orphaned)
        split_images[split] = len(images)
        all_image_paths.extend(images)

        for image_path in images:
            stem = image_path.stem
            source = source_name(stem)
            source_images_by_split[split][source] += 1
            families[family_name(stem)].add(split)
            if split != "train" and source in {
                "tree_cavity",
                "unreviewed_insect",
                "openverse_mold",
                "openverse_decay",
            }:
                weak_eval_images += 1
            try:
                with Image.open(image_path) as image:
                    image.verify()
                with Image.open(image_path) as image:
                    image.load()
                    if image.width <= 0 or image.height <= 0:
                        raise ValueError(f"invalid dimensions {image.size}")
            except Exception:
                corrupt_images += 1

            digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
            exact_hashes[digest].append((split, image_path.name))
            label_path = label_by_stem.get(stem)
            if label_path is None:
                continue

            found_classes: set[int] = set()
            for line_number, raw_line in enumerate(
                label_path.read_text(encoding="utf-8-sig").splitlines(), start=1
            ):
                parts = raw_line.split()
                if len(parts) != 5:
                    invalid_lines += 1
                    continue
                try:
                    class_id = int(parts[0])
                    cx, cy, width, height = map(float, parts[1:])
                except ValueError:
                    invalid_lines += 1
                    continue
                if class_id not in expected_map:
                    invalid_classes += 1
                    continue
                values = (cx, cy, width, height)
                finite = all(math.isfinite(value) for value in values)
                edges_valid = (
                    finite
                    and width > 0
                    and height > 0
                    and cx - width / 2 >= -1e-6
                    and cy - height / 2 >= -1e-6
                    and cx + width / 2 <= 1 + 1e-6
                    and cy + height / 2 <= 1 + 1e-6
                )
                if not edges_valid:
                    invalid_boxes += 1
                    continue
                found_classes.add(class_id)
                class_objects[class_id] += 1
                class_objects_by_split[split][class_id] += 1
                split_objects[split] += 1

                rounded = tuple(round(value, 6) for value in values)
                if rounded in {
                    (0.5, 0.5, 0.65, 0.65),
                    (0.5, 0.5, 0.75, 0.75),
                    (0.5, 0.5, 0.8, 0.8),
                    (0.5, 0.5, 0.5, 0.5),
                    (0.5, 0.5, 0.98, 0.98),
                }:
                    placeholder_by_class[class_id] += 1
                    if split != "train":
                        if rounded == (0.5, 0.5, 0.98, 0.98):
                            reviewed_full_image_eval += 1
                        else:
                            placeholder_eval += 1

                if "Blue_Stain" in stem and class_id == name_to_id.get("mold", -1):
                    blue_stain_as_mold += 1
                if "overgrown" in stem and class_id in {
                    name_to_id.get("bark_loss", -1),
                    name_to_id.get("bark_pocket", -1),
                }:
                    overgrown_as_bark_loss += 1

            for class_id in found_classes:
                class_images[class_id] += 1
                class_images_by_split[split][class_id] += 1

    duplicate_groups = [entries for entries in exact_hashes.values() if len(entries) > 1]
    cross_split_duplicates = [
        entries for entries in duplicate_groups if len({split for split, _ in entries}) > 1
    ]
    leaking_families = {
        family: sorted(splits) for family, splits in families.items() if len(splits) > 1
    }

    if missing_labels:
        add_issue(issues, "error", "missing_labels", "images are missing YOLO label files", missing_labels)
    if orphan_labels:
        add_issue(issues, "error", "orphan_labels", "YOLO label files have no matching image", orphan_labels)
    if corrupt_images:
        add_issue(issues, "error", "corrupt_images", "images cannot be fully decoded", corrupt_images)
    if invalid_lines:
        add_issue(issues, "error", "invalid_label_lines", "label rows are not valid five-field YOLO rows", invalid_lines)
    if invalid_classes:
        add_issue(
            issues,
            "error",
            "invalid_class_ids",
            f"label rows use class ids outside 0..{len(expected_map) - 1}",
            invalid_classes,
        )
    if invalid_boxes:
        add_issue(issues, "error", "invalid_box_geometry", "boxes have non-finite, empty, or out-of-frame geometry", invalid_boxes)
    if cross_split_duplicates:
        add_issue(
            issues,
            "error",
            "exact_cross_split_duplicates",
            "byte-identical images occur in more than one split",
            len(cross_split_duplicates),
        )
    if leaking_families:
        add_issue(
            issues,
            "error",
            "augmentation_family_leakage",
            "original/augmented or crop-related image families occur in multiple splits",
            len(leaking_families),
        )
    if blue_stain_as_mold:
        add_issue(
            issues,
            "error",
            "blue_stain_mapped_to_mold",
            "VSB Blue_Stain belongs to stain (11), not mold (9)",
            blue_stain_as_mold,
        )
    if overgrown_as_bark_loss:
        add_issue(
            issues,
            "error",
            "overgrown_mapped_to_bark_loss",
            "VSB overgrown-knot annotations do not establish bark loss",
            overgrown_as_bark_loss,
        )
    if placeholder_eval:
        add_issue(
            issues,
            "error",
            "placeholder_boxes_in_evaluation",
            "fixed guessed boxes occur in validation/test and invalidate detection metrics",
            placeholder_eval,
        )
    if reviewed_full_image_eval:
        add_issue(
            issues,
            "warning",
            "reviewed_full_image_boxes_in_evaluation",
            "reviewed full-image weak boxes occur in validation/test; use only for smoke checks",
            reviewed_full_image_eval,
        )
    if weak_eval_images:
        add_issue(
            issues,
            "warning",
            "weak_sources_in_evaluation",
            "weak/full-image annotations occur in validation/test",
            weak_eval_images,
        )
    for class_id, name in expected_map.items():
        if class_images[class_id] == 0:
            add_issue(issues, "error", "empty_class", f"class {class_id} {name} has no images")
        if class_images_by_split["train"][class_id] == 0:
            add_issue(issues, "error", "class_missing_from_train", f"class {class_id} {name} has no training images")

    newest_data_mtime = max((path.stat().st_mtime for path in all_image_paths), default=0)
    stale_metadata = []
    for name in ("images.jsonl", "validation_report.json", "validation_report.md", "sources.json"):
        path = root / "metadata" / name
        if path.exists() and path.stat().st_mtime + 1 < newest_data_mtime:
            stale_metadata.append(name)
    if stale_metadata:
        add_issue(
            issues,
            "warning",
            "stale_metadata",
            "metadata predates the current images: " + ", ".join(stale_metadata),
            len(stale_metadata),
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_root": str(root.resolve()),
        "ok": not any(issue["severity"] == "error" for issue in issues),
        "issues": issues,
        "summary": {
            "images": sum(split_images.values()),
            "objects": sum(split_objects.values()),
            "images_by_split": dict(split_images),
            "objects_by_split": dict(split_objects),
            "missing_labels": missing_labels,
            "orphan_labels": orphan_labels,
            "corrupt_images": corrupt_images,
            "invalid_label_lines": invalid_lines,
            "invalid_class_ids": invalid_classes,
            "invalid_boxes": invalid_boxes,
            "exact_duplicate_groups": len(duplicate_groups),
            "exact_cross_split_duplicate_groups": len(cross_split_duplicates),
            "leaking_families": len(leaking_families),
            "placeholder_boxes": sum(placeholder_by_class.values()),
            "placeholder_boxes_in_evaluation": placeholder_eval,
            "reviewed_full_image_boxes_in_evaluation": reviewed_full_image_eval,
            "weak_images_in_evaluation": weak_eval_images,
        },
        "class_stats": {
            str(class_id): {
                "name": name,
                "images": class_images[class_id],
                "objects": class_objects[class_id],
                "images_by_split": {
                    split: class_images_by_split[split][class_id] for split in SPLITS
                },
                "objects_by_split": {
                    split: class_objects_by_split[split][class_id] for split in SPLITS
                },
                "placeholder_boxes": placeholder_by_class[class_id],
            }
            for class_id, name in expected_map.items()
        },
        "source_images_by_split": {
            split: dict(counts) for split, counts in source_images_by_split.items()
        },
        "examples": {
            "cross_split_duplicates": cross_split_duplicates[:25],
            "leaking_families": dict(list(sorted(leaking_families.items()))[:50]),
        },
    }


def markdown(report: dict) -> str:
    status = "PASS" if report["ok"] else "FAIL"
    summary = report["summary"]
    lines = [
        f"# {len(report['class_stats'])}-class dataset audit",
        "",
        f"- status: **{status}**",
        f"- images: {summary['images']}",
        f"- objects: {summary['objects']}",
        f"- split: {summary['images_by_split']}",
        "",
        "## Issues",
        "",
    ]
    if report["issues"]:
        for issue in report["issues"]:
            lines.append(
                f"- **{issue['severity'].upper()} / {issue['code']}** "
                f"({issue['count']}): {issue['message']}"
            )
    else:
        lines.append("- None")
    lines.extend([
        "",
        "## Class distribution",
        "",
        "| id | class | images | objects | train | val | test | placeholder boxes |",
        "|---:|---|---:|---:|---:|---:|---:|---:|",
    ])
    for class_id, item in report["class_stats"].items():
        splits = item["images_by_split"]
        lines.append(
            f"| {class_id} | {item['name']} | {item['images']} | {item['objects']} | "
            f"{splits['train']} | {splits['val']} | {splits['test']} | {item['placeholder_boxes']} |"
        )
    lines.extend([
        "",
        "## Integrity summary",
        "",
        f"- exact duplicate groups: {summary['exact_duplicate_groups']}",
        f"- exact cross-split duplicate groups: {summary['exact_cross_split_duplicate_groups']}",
        f"- leaking augmentation/source families: {summary['leaking_families']}",
        f"- placeholder boxes in validation/test: {summary['placeholder_boxes_in_evaluation']}",
        f"- weak images in validation/test: {summary['weak_images_in_evaluation']}",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
    )
    parser.add_argument("--contract", type=int, choices=(10, 12), default=12)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()
    classes = CLASSES_10 if args.contract == 10 else CLASSES_12
    root = args.root or Path(__file__).resolve().parents[1] / f"wood_defect_{args.contract}class"
    report = audit(root, classes)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(markdown(report), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
