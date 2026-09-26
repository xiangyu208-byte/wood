"""Download a deterministic, size-bounded subset of Oak rot masks.

Source: https://huggingface.co/datasets/nrodgers98/Oak-Defect-Detection
License: CC BY-NC 4.0.  This source therefore makes the assembled dataset
non-commercial unless it is omitted and replaced with independently licensed
decay imagery.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote

import requests


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "raw" / "hf-oak-rot"
REPO = "nrodgers98/Oak-Defect-Detection"
API = f"https://huggingface.co/api/datasets/{REPO}?blobs=true"
ROT_SUFFIXES = ("BlackRot", "Black_Rot", "YellowRot", "Yellow_Rot")


def remote_size(entry: dict) -> int:
    return int((entry.get("lfs") or {}).get("size") or entry.get("size") or 0)


def local_path(remote_path: str) -> Path:
    kind = "masks" if "_Bin_" in remote_path else "images"
    return OUT / kind / Path(remote_path).name


def download(remote_path: str, expected_size: int) -> tuple[str, str]:
    destination = local_path(remote_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and (not expected_size or destination.stat().st_size == expected_size):
        return remote_path, "cached"
    url = f"https://huggingface.co/datasets/{REPO}/resolve/main/{quote(remote_path)}"
    for attempt in range(4):
        try:
            with requests.get(url, stream=True, timeout=120) as response:
                response.raise_for_status()
                with destination.open("wb") as handle:
                    for chunk in response.iter_content(1024 * 1024):
                        if chunk:
                            handle.write(chunk)
            if expected_size and destination.stat().st_size != expected_size:
                raise IOError(f"size mismatch {destination.stat().st_size} != {expected_size}")
            return remote_path, "downloaded"
        except Exception as exc:
            if attempt == 3:
                return remote_path, f"failed: {exc}"
            time.sleep(2 ** attempt)
    return remote_path, "failed"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", type=int, default=80, help="number of unique source boards")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()

    response = requests.get(API, timeout=60)
    response.raise_for_status()
    siblings = response.json()["siblings"]
    by_path = {entry["rfilename"]: entry for entry in siblings}
    masks_by_image: dict[str, list[str]] = {}
    for path in by_path:
        if not path.lower().endswith(".tif") or "_Col_Bin_" not in path:
            continue
        if not any(path.endswith(f"_Col_Bin_{suffix}.tif") for suffix in ROT_SUFFIXES):
            continue
        image_path = path
        for suffix in ROT_SUFFIXES:
            image_path = image_path.replace(f"_Bin_{suffix}.tif", ".tif")
        if image_path in by_path:
            masks_by_image.setdefault(image_path, []).append(path)

    selected_images = sorted(
        masks_by_image,
        key=lambda value: hashlib.sha256(value.encode("utf-8")).hexdigest(),
    )[: args.images]
    selected_paths: list[str] = []
    for image_path in selected_images:
        selected_paths.append(image_path)
        selected_paths.extend(sorted(masks_by_image[image_path]))

    OUT.mkdir(parents=True, exist_ok=True)
    print(f"selected {len(selected_images)} images and {len(selected_paths) - len(selected_images)} masks")
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(download, path, remote_size(by_path[path])): path for path in selected_paths
        }
        completed = 0
        for future in as_completed(futures):
            path, status = future.result()
            completed += 1
            if status.startswith("failed"):
                failures.append(path)
            print(f"[{completed:03d}/{len(selected_paths):03d}] {status}: {Path(path).name}")

    manifest = {
        "source": f"https://huggingface.co/datasets/{REPO}",
        "license": "CC BY-NC 4.0",
        "selection": "first N source image paths sorted by SHA-256(path)",
        "requested_images": args.images,
        "images": [
            {
                "remote_image": image_path,
                "local_image": str(local_path(image_path)),
                "masks": [
                    {"remote": mask, "local": str(local_path(mask))}
                    for mask in sorted(masks_by_image[image_path])
                ],
            }
            for image_path in selected_images
        ],
        "failures": failures,
    }
    path = OUT / "selection_manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"manifest: {path}")
    if failures:
        raise SystemExit(f"{len(failures)} downloads failed")


if __name__ == "__main__":
    main()
