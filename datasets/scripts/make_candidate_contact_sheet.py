"""Create labelled contact sheets for manual dataset candidate review."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--thumb", type=int, default=320)
    args = parser.parse_args()

    paths = sorted(
        p for p in args.input_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
    )
    if not paths:
        raise SystemExit(f"No images found in {args.input_dir}")

    label_h = 42
    cell_w = args.thumb
    cell_h = args.thumb + label_h
    rows = (len(paths) + args.columns - 1) // args.columns
    canvas = Image.new("RGB", (args.columns * cell_w, rows * cell_h), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()

    for index, path in enumerate(paths):
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((cell_w - 8, args.thumb - 8), Image.Resampling.LANCZOS)
            x = (index % args.columns) * cell_w
            y = (index // args.columns) * cell_h
            px = x + (cell_w - image.width) // 2
            py = y + (args.thumb - image.height) // 2
            canvas.paste(image, (px, py))
            draw.rectangle((x, y, x + cell_w - 1, y + cell_h - 1), outline="#999999", width=1)
            draw.text((x + 6, y + args.thumb + 3), f"{index + 1:02d} {path.stem[:12]}", fill="black", font=font)
            draw.text((x + 6, y + args.thumb + 19), f"{source.width}x{source.height}", fill="#555555", font=font)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(args.output, quality=92)
    print(f"wrote {args.output} ({len(paths)} images)")


if __name__ == "__main__":
    main()
