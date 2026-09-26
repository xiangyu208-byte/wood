"""Stage CC-licensed termite-damage and brown-rot images from Commons."""

from __future__ import annotations

import argparse
import html
import io
import json
import sys
import time
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "raw" / "wikimedia-candidates"
MANIFEST = ROOT / "metadata" / "wikimedia_candidates.json"
API = "https://commons.wikimedia.org/w/api.php"
HEADERS = {"User-Agent": "wood-dataset-builder/1.0 (research dataset; local curation)"}
CATEGORIES = {
    "insect_damage": "Category:Wood damaged by termites",
    "decay": "Category:Brown rot",
}


def clean(value: object) -> str:
    if isinstance(value, dict):
        value = value.get("value", "")
    return html.unescape(str(value or ""))


def fetch_category(class_name: str, category: str, *, cached_only: bool = False) -> list[dict]:
    params = {
        "action": "query",
        "generator": "categorymembers",
        "gcmtitle": category,
        "gcmtype": "file",
        "gcmlimit": 100,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": 1600,
        "format": "json",
        "maxlag": 5,
    }
    for attempt in range(5):
        response = requests.get(API, params=params, headers=HEADERS, timeout=60)
        if response.status_code == 429:
            time.sleep(5 * (attempt + 1))
            continue
        response.raise_for_status()
        break
    else:
        raise RuntimeError(f"Commons rate limit did not clear for {category}")

    pages = response.json().get("query", {}).get("pages", {})
    records: list[dict] = []
    target = OUT / class_name
    target.mkdir(parents=True, exist_ok=True)
    for page in sorted(pages.values(), key=lambda item: item.get("title", "")):
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        license_name = clean(meta.get("LicenseShortName"))
        if not any(token in license_name.lower() for token in ("cc", "public domain", "pdm")):
            continue
        url = info.get("thumburl") or info.get("url")
        if not url:
            continue
        filename = f"commons_{page['pageid']}.jpg"
        local = target / filename
        if cached_only and not local.exists():
            continue
        if not local.exists():
            error: Exception | None = None
            for attempt in range(5):
                try:
                    image_response = requests.get(url, headers=HEADERS, timeout=90)
                    if image_response.status_code == 429:
                        time.sleep(4 * (attempt + 1))
                        continue
                    image_response.raise_for_status()
                    image = Image.open(io.BytesIO(image_response.content)).convert("RGB")
                    image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
                    image.save(local, "JPEG", quality=92, optimize=True)
                    error = None
                    break
                except Exception as exc:
                    error = exc
                    time.sleep(2 * (attempt + 1))
            if error is not None or not local.exists():
                print(f"skip page_id={page.get('pageid')}: {error}")
                continue
            time.sleep(0.75)
        records.append(
            {
                "class": class_name,
                "page_id": page["pageid"],
                "title": page.get("title"),
                "description_url": info.get("descriptionurl"),
                "source_url": info.get("url"),
                "artist": clean(meta.get("Artist")),
                "credit": clean(meta.get("Credit")),
                "license": license_name,
                "license_url": clean(meta.get("LicenseUrl")),
                "category": category,
                "local_path": str(local),
            }
        )
    return records


def contact_sheet(class_name: str, records: list[dict]) -> None:
    width, height, caption, columns = 260, 190, 42, 4
    rows = (len(records) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * width, rows * (height + caption)), "#15181d")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, record in enumerate(records):
        image = Image.open(record["local_path"]).convert("RGB")
        image.thumbnail((width - 8, height - 8), Image.Resampling.LANCZOS)
        x = index % columns * width
        y = index // columns * (height + caption)
        sheet.paste(image, (x + (width - image.width) // 2, y + (height - image.height) // 2))
        draw.multiline_text(
            (x + 4, y + height + 2),
            f"{index:02d} id={record['page_id']}\n{record['title'][5:35]}",
            fill="white",
            font=font,
            spacing=2,
        )
    sheet.save(OUT / f"contact-sheet-{class_name}.jpg", quality=90)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--classes", nargs="+", choices=sorted(CATEGORIES), default=list(CATEGORIES))
    parser.add_argument("--cached-only", action="store_true")
    args = parser.parse_args()
    records: list[dict] = []
    if MANIFEST.exists():
        records = [
            row
            for row in json.loads(MANIFEST.read_text(encoding="utf-8"))
            if row.get("class") not in args.classes
        ]
    for class_name in args.classes:
        category = CATEGORIES[class_name]
        subset = fetch_category(class_name, category, cached_only=args.cached_only)
        records.extend(subset)
        contact_sheet(class_name, subset)
        print(f"{class_name}: {len(subset)} candidates")
        time.sleep(2)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(MANIFEST)


if __name__ == "__main__":
    main()
