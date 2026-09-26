"""Collect traceable, openly licensed candidate images for scarce wood defects.

The result is a *staging area*, not training data.  Review the generated contact
sheets and list accepted Openverse ids in ``metadata/openverse_accept.json``
before running ``build_12class_dataset.py``.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "raw" / "openverse-candidates"
META = ROOT / "metadata"
API = "https://api.openverse.org/v1/images/"

QUERIES = {
    "decay": [
        "brown rotted wood",
        "wood dry rot damage",
        "decayed timber surface",
        "wood decay close up",
        "rotted wooden beam",
    ],
    "insect_damage": [
        "woodworm holes wood",
        "wood borer damage",
        "termite damage wood",
        "bark beetle galleries wood",
        "insect damaged timber",
    ],
    "mold": [
        "moldy wood grain",
        "mold growth on wood",
        "mildew wooden surface",
        "black mold wood",
        "fungal mold timber surface",
        "mold on a cedar stump",
        "white mold on wood",
        "mildew wood texture",
        "moldy lumber",
    ],
}

POSITIVE = {
    "decay": ("rot", "rotten", "rotted", "decay", "decayed", "dry rot", "brown rot"),
    "insect_damage": (
        "woodworm",
        "borer",
        "termite",
        "beetle",
        "wormhole",
        "worm hole",
        "gallery",
        "galleries",
    ),
    "mold": ("mold", "mould", "mildew", "fungal", "fungus"),
}
WOOD = ("wood", "wooden", "timber", "lumber", "beam", "log", "bark", "tree", "trunk")
NEGATIVE = (
    "cheese",
    "bread",
    "fruit",
    "pumpkin",
    "leaf",
    "leaves",
    "molding",
    "moulding",
    "portrait",
    "manuscript",
    "painting",
    "insect specimen",
)


def fetch_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": "wood-dataset-builder/1.0"})
    with urlopen(request, timeout=45) as response:
        return json.load(response)


def text_for(item: dict) -> str:
    tags = item.get("tags") or []
    tag_text = " ".join(str(tag.get("name", "")) for tag in tags if isinstance(tag, dict))
    return " ".join(
        str(item.get(field) or "") for field in ("title", "description")
    ).lower() + " " + tag_text.lower()


def relevance(class_name: str, item: dict) -> int:
    text = text_for(item)
    score = 5 * sum(term in text for term in POSITIVE[class_name])
    score += 2 * sum(term in text for term in WOOD)
    score -= 8 * sum(term in text for term in NEGATIVE)
    if item.get("source") == "wikimedia":
        score += 1
    if item.get("license") in {"cc0", "pdm"}:
        score += 1
    return score


def download_image(url: str) -> tuple[bytes, str]:
    request = Request(url, headers={"User-Agent": "wood-dataset-builder/1.0"})
    with urlopen(request, timeout=60) as response:
        data = response.read(25 * 1024 * 1024)
    image = Image.open(io.BytesIO(data)).convert("RGB")
    image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    output = io.BytesIO()
    image.save(output, "JPEG", quality=92, optimize=True)
    return output.getvalue(), hashlib.sha256(output.getvalue()).hexdigest()


def make_sheet(class_name: str, records: list[dict]) -> None:
    thumb_w, thumb_h, caption_h, cols = 240, 180, 54, 4
    rows = (len(records) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb_w, rows * (thumb_h + caption_h)), "#16181d")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, record in enumerate(records):
        image = Image.open(record["local_path"]).convert("RGB")
        image.thumbnail((thumb_w - 8, thumb_h - 8), Image.Resampling.LANCZOS)
        x = (index % cols) * thumb_w
        y = (index // cols) * (thumb_h + caption_h)
        sheet.paste(image, (x + (thumb_w - image.width) // 2, y + (thumb_h - image.height) // 2))
        title = str(record.get("title") or "")[:34]
        caption = f"{index:02d} {record['id'][:8]} s={record['score']}\n{title}"
        draw.multiline_text((x + 5, y + thumb_h + 2), caption, fill="white", font=font, spacing=2)
    path = OUT / f"contact-sheet-{class_name}.jpg"
    sheet.save(path, quality=90)
    print(f"[{class_name}] contact sheet: {path}")


def collect(class_name: str, limit: int) -> list[dict]:
    by_id: dict[str, dict] = {}
    for query in QUERIES[class_name]:
        # Anonymous Openverse clients are limited to 20 records per request.
        params = urlencode({"q": query, "page_size": 20, "license": "cc0,by,pdm"})
        payload = fetch_json(f"{API}?{params}")
        for item in payload.get("results", []):
            item["query"] = query
            item["score"] = relevance(class_name, item)
            if item["score"] >= 7 and item.get("url"):
                current = by_id.get(item["id"])
                if current is None or item["score"] > current["score"]:
                    by_id[item["id"]] = item
        time.sleep(0.15)

    ranked = sorted(by_id.values(), key=lambda item: (-item["score"], item["id"]))
    target_dir = OUT / class_name
    target_dir.mkdir(parents=True, exist_ok=True)
    accepted: list[dict] = []
    hashes: set[str] = set()
    for item in ranked:
        if len(accepted) >= limit:
            break
        try:
            data, digest = download_image(item["url"])
            if digest in hashes:
                continue
            hashes.add(digest)
            local_path = target_dir / f"{item['id']}.jpg"
            local_path.write_bytes(data)
            record = {
                "class": class_name,
                "id": item["id"],
                "title": item.get("title"),
                "creator": item.get("creator"),
                "creator_url": item.get("creator_url"),
                "license": item.get("license"),
                "license_version": item.get("license_version"),
                "license_url": item.get("license_url"),
                "source": item.get("source"),
                "foreign_landing_url": item.get("foreign_landing_url"),
                "original_url": item.get("url"),
                "query": item.get("query"),
                "score": item["score"],
                "sha256": digest,
                "local_path": str(local_path),
            }
            accepted.append(record)
            print(f"[{class_name}] {len(accepted):02d}/{limit}: {record['title']}")
        except Exception as exc:
            print(f"[{class_name}] skip {item.get('url')}: {exc}")
    return accepted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=32, help="maximum staged candidates per class")
    parser.add_argument(
        "--classes",
        nargs="+",
        choices=sorted(QUERIES),
        default=list(QUERIES),
        help="only refresh the selected candidate classes",
    )
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    META.mkdir(parents=True, exist_ok=True)
    manifest_path = META / "openverse_candidates.json"
    existing = []
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest: list[dict] = [row for row in existing if row.get("class") not in args.classes]
    for class_name in args.classes:
        records = collect(class_name, args.limit)
        manifest.extend(records)
        make_sheet(class_name, records)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    accept_path = META / "openverse_accept.json"
    if not accept_path.exists():
        accept_path.write_text(
            json.dumps({name: [] for name in QUERIES}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    print(f"manifest: {manifest_path}")
    print(f"review file: {accept_path}")


if __name__ == "__main__":
    main()
