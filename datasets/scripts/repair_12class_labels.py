"""Repair normalized YOLO boxes that extend beyond the image boundary.

Only label coordinates are changed.  Class ids and the number of objects are
preserved whenever a box intersects the image.  Use ``--apply`` to write the
repairs; without it the command is a dry run.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def clip_box(cx: float, cy: float, width: float, height: float) -> tuple[float, ...] | None:
    if not all(math.isfinite(value) for value in (cx, cy, width, height)):
        return None
    x1 = max(0.0, cx - width / 2)
    y1 = max(0.0, cy - height / 2)
    x2 = min(1.0, cx + width / 2)
    y2 = min(1.0, cy + height / 2)
    if x2 <= x1 or y2 <= y1:
        return None
    return ((x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1)


def repair(root: Path, apply: bool) -> dict:
    changed_files = 0
    changed_boxes = 0
    dropped_boxes = 0
    malformed_rows = []
    for label_path in sorted((root / "labels").glob("*/*.txt")):
        original = label_path.read_text(encoding="utf-8-sig").splitlines()
        repaired = []
        file_changed = False
        for line_number, line in enumerate(original, start=1):
            parts = line.split()
            if len(parts) != 5:
                malformed_rows.append(f"{label_path}:{line_number}")
                repaired.append(line)
                continue
            try:
                class_id = int(parts[0])
                box = tuple(map(float, parts[1:]))
            except ValueError:
                malformed_rows.append(f"{label_path}:{line_number}")
                repaired.append(line)
                continue
            clipped = clip_box(*box)
            if clipped is None:
                dropped_boxes += 1
                file_changed = True
                continue
            new_line = f"{class_id} " + " ".join(f"{value:.6f}" for value in clipped)
            if new_line != line.strip():
                changed_boxes += 1
                file_changed = True
            repaired.append(new_line)
        if file_changed:
            changed_files += 1
            if apply:
                label_path.write_text("\n".join(repaired) + ("\n" if repaired else ""), encoding="utf-8")
    return {
        "dataset_root": str(root.resolve()),
        "mode": "apply" if apply else "dry-run",
        "changed_files": changed_files,
        "changed_boxes": changed_boxes,
        "dropped_boxes": dropped_boxes,
        "malformed_rows": malformed_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "wood_defect_12class",
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = repair(args.root, args.apply)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["malformed_rows"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
