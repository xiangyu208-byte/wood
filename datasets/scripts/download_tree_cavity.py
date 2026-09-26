"""Download the Apache-2.0 Tree-Cavity image set referenced by its HF parquet."""

from __future__ import annotations

import io
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote

import pyarrow.parquet as pq
import requests
from PIL import Image


ROOT = Path(__file__).resolve().parents[1] / "raw" / "hf-tree-cavity"
BASE = "https://huggingface.co/datasets/neolam2024/Tree-Cavity/resolve/main/"


def fetch(path: str) -> str:
    remote = path.split("/images/", 1)[1]
    destination = ROOT / "images" / remote
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return f"cached {remote}"
    response = requests.get(BASE + quote(f"images/{remote}"), timeout=90)
    response.raise_for_status()
    image = Image.open(io.BytesIO(response.content)).convert("RGB")
    image.thumbnail((2000, 2000), Image.Resampling.LANCZOS)
    image.save(destination, "JPEG", quality=92, optimize=True)
    return f"downloaded {remote}"


def main() -> None:
    rows = pq.read_table(ROOT / "train.parquet").column("image").to_pylist()
    paths = [row["path"] for row in rows]
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(fetch, path) for path in paths]
        for index, future in enumerate(as_completed(futures), 1):
            print(f"[{index:02d}/{len(paths):02d}] {future.result()}")


if __name__ == "__main__":
    main()
