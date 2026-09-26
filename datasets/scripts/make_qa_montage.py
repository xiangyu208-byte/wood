"""Render a deterministic visual QA montage for the six added classes."""

from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1] / "wood_defect_12class"
CLASSES = {
    6: "decay",
    7: "large_hole",
    8: "insect_damage",
    9: "mold",
    10: "bark_loss",
    11: "stain",
}


def main() -> None:
    samples: dict[int, list[tuple[Path, list[list[float]]]]] = {key: [] for key in CLASSES}
    candidates: dict[int, list[tuple[str, Path, list[list[float]]]]] = {key: [] for key in CLASSES}
    for split in ("train", "val", "test"):
        for image_path in (ROOT / "images" / split).glob("*.jpg"):
            label_path = ROOT / "labels" / split / f"{image_path.stem}.txt"
            boxes_by_class: dict[int, list[list[float]]] = {}
            for line in label_path.read_text(encoding="utf-8").splitlines():
                values = line.split()
                class_id = int(values[0])
                if class_id in CLASSES:
                    boxes_by_class.setdefault(class_id, []).append(list(map(float, values[1:])))
            for class_id, boxes in boxes_by_class.items():
                rank = hashlib.sha256(f"{class_id}:{split}:{image_path.name}".encode()).hexdigest()
                candidates[class_id].append((rank, image_path, boxes))
    for class_id in CLASSES:
        samples[class_id] = [(path, boxes) for _, path, boxes in sorted(candidates[class_id])[:4]]

    cell_w, cell_h, caption_h = 360, 220, 28
    sheet = Image.new("RGB", (4 * cell_w, len(CLASSES) * (cell_h + caption_h)), "#14171c")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for row, (class_id, class_name) in enumerate(CLASSES.items()):
        for col, (path, boxes) in enumerate(samples[class_id]):
            original = Image.open(path).convert("RGB")
            ow, oh = original.size
            original.thumbnail((cell_w - 8, cell_h - 8), Image.Resampling.LANCZOS)
            x0 = col * cell_w + (cell_w - original.width) // 2
            y0 = row * (cell_h + caption_h) + (cell_h - original.height) // 2
            sheet.paste(original, (x0, y0))
            sx, sy = original.width / ow, original.height / oh
            for cx, cy, bw, bh in boxes:
                left = x0 + (cx - bw / 2) * ow * sx
                top = y0 + (cy - bh / 2) * oh * sy
                right = x0 + (cx + bw / 2) * ow * sx
                bottom = y0 + (cy + bh / 2) * oh * sy
                draw.rectangle((left, top, right, bottom), outline="#ff4d5a", width=3)
            draw.text(
                (col * cell_w + 5, row * (cell_h + caption_h) + cell_h + 5),
                f"{class_id} {class_name} | {path.name[:32]}",
                fill="white",
                font=font,
            )
    output = ROOT / "metadata" / "qa_new_classes.jpg"
    sheet.save(output, quality=92)
    print(output)


if __name__ == "__main__":
    main()
