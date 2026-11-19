"""Smoke-test the deployed model and actual FastAPI handlers, without training.

Requires the inference dependencies plus httpx. Uses an isolated upload directory
and a few labelled validation images; this is not a full accuracy evaluation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

import cv2
import numpy as np
from fastapi.testclient import TestClient


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("pt", "onnx"), required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    source_root = Path(__file__).resolve().parents[1]
    repository_root = source_root.parent
    deploy_root = source_root / "ultralytics-main/runs/detect"
    model_path = deploy_root / f"best.{args.backend}"
    manifest = json.loads((deploy_root / "best.manifest.json").read_text(encoding="utf-8"))
    expected_sha = manifest["source_sha256" if args.backend == "pt" else "onnx_sha256"]
    actual_sha = hashlib.sha256(model_path.read_bytes()).hexdigest()
    assert actual_sha == expected_sha, "Model file differs from verified export"
    dataset = repository_root / "datasets/wood_defect_10class"
    samples = {}
    for label in sorted((dataset / "labels/val").glob("*.txt")):
        classes = {int(line.split()[0]) for line in label.read_text(encoding="utf-8").splitlines() if line.strip()}
        for class_id in classes & {6, 7, 8, 9}:
            samples.setdefault(class_id, dataset / "images/val" / f"{label.stem}.jpg")
        if len(samples) == 4:
            break
    assert len(samples) == 4 and all(path.is_file() for path in samples.values())
    report = {"backend": args.backend, "device": args.device, "sha256": actual_sha, "requests": []}
    with tempfile.TemporaryDirectory(prefix="wood10-smoke-") as temporary:
        upload_root = Path(temporary)
        os.environ.update(MODEL_PATH=str(model_path), UPLOAD_ROOT=str(upload_root), MODEL_DEVICE=args.device)
        sys.path.insert(0, str(source_root / "wood_detect_python/wood_detect"))
        import detect
        with TestClient(detect.app) as client:
            health = client.get("/health")
            assert health.status_code == 200
            report["health"] = health.json()
            assert report["health"]["classCount"] == 10
            assert list(report["health"]["classNames"].values()) == manifest["class_names"]

            def request(path, mode, threshold=0.25):
                response = client.post("/predict", json={
                    "imagePath": str(path), "modelMode": mode,
                    "confidenceThreshold": threshold, "precision": "AUTO",
                })
                assert response.status_code == 200, response.text
                result = response.json()
                assert result["success"]
                assert result["totalCount"] == len(result["details"])
                assert all(item["className"] in manifest["class_names"] for item in result["details"])
                assert all(threshold <= item["confidence"] <= 1 for item in result["details"])
                assert Path(result["resultImagePath"]).is_file()
                report["requests"].append({
                    "image": path.name, "mode": mode, "threshold": threshold,
                    "totalCount": result["totalCount"], "details": result["details"],
                    "actualMode": result["actualMode"], "tileCount": result["tileCount"],
                })
                print(f"PASS {args.backend}/{args.device} {path.name} {mode}: {result['totalCount']} boxes", flush=True)
                return result

            for class_id, sample in sorted(samples.items()):
                local_image = upload_root / f"class-{class_id}.jpg"
                shutil.copyfile(sample, local_image)
                request(local_image, "FAST")
            request(upload_root / "class-6.jpg", "STANDARD")
            request(upload_root / "class-6.jpg", "ACCURATE")

            # Local review must respect the threshold, even if a dark region
            # exists. Geometric proposals must never become public detections.
            candidate_image = np.full((600, 800, 3), (80, 140, 190), dtype=np.uint8)
            candidate_image[180:360, 260:520] = (20, 25, 30)
            candidate_path = upload_root / "candidate.jpg"
            assert cv2.imwrite(str(candidate_path), candidate_image)
            fallback = request(candidate_path, "STANDARD", 0.95)
            assert fallback["tileCount"] >= 3
            assert all(item["confidence"] >= 0.95 for item in fallback["details"])
            assert client.post("/predict", json={"imagePath": str(candidate_path), "modelMode": "INVALID"}).status_code == 422
            assert client.post("/predict", json={"imagePath": str(upload_root / "missing.jpg")}).status_code == 400
    report["status"] = "PASS"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Deployment smoke test PASS (not an accuracy evaluation)")


if __name__ == "__main__":
    main()
