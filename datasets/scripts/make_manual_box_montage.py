"""Render every manually boxed Openverse/Wikimedia sample for visual QA."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1] / "wood_defect_12class"
SOURCES = ("openverse_", "wikimedia_")
CLASS_NAMES = {8: "insect_damage", 9: "mold"}


def main() -> None:
    samples: list[tuple[str, Path, int, list[list[float]]]] = []
    for split in ("train", "val", "test"):
        for image_path in sorted((ROOT / "images" / split).glob("*.jpg")):
            if not image_path.name.startswith(SOURCES):
                continue
            label_path = ROOT / "labels" / split / f"{image_path.stem}.txt"
            boxes: list[list[float]] = []
            class_id = -1
            for line in label_path.read_text(encoding="utf-8").splitlines():
                values = line.split()
                candidate = int(values[0])
                if candidate in CLASS_NAMES:
                    class_id = candidate
                    boxes.append(list(map(float, values[1:])))
            if boxes:
                samples.append((split, image_path, class_id, boxes))

    columns = 5
    cell_w, cell_h, caption_h = 320, 220, 38
    rows = math.ceil(len(samples) / columns)
    sheet = Image.new("RGB", (columns * cell_w, rows * (cell_h + caption_h)), "#14171c")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()

    for index, (split, path, class_id, boxes) in enumerate(samples):
        row, col = divmod(index, columns)
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
        caption_y = row * (cell_h + caption_h) + cell_h + 3
        draw.text(
            (col * cell_w + 5, caption_y),
            f"{class_id} {CLASS_NAMES[class_id]} | {split}",
            fill="white",
            font=font,
        )
        draw.text(
            (col * cell_w + 5, caption_y + 14),
            path.name[:45],
            fill="#cfd5df",
            font=font,
        )

    output = ROOT / "metadata" / "qa_manual_boxes.jpg"
    sheet.save(output, quality=92)
    print(f"{output} ({len(samples)} images)")


if __name__ == "__main__":
    main()
