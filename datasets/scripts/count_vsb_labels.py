"""统计并提取 VSB-TUO 所有 overgrown/Blue_Stain 标注"""
import pyarrow.parquet as pq
from pathlib import Path
from collections import Counter

cache = Path("E:/wood/datasets/datasets/raw/hf-vsb-tuo/_parquet_cache")
total = Counter()
for f in sorted(cache.glob("*.parquet")):
    t = pq.read_table(str(f), columns=["objects"])
    counts = Counter()
    for row in t["objects"]:
        for obj in (row.as_py() or []):
            counts[obj["label"]] += 1
    for label in ["overgrown", "Blue_Stain", "Knot_missing"]:
        total[label] += counts.get(label, 0)
    print(f"{f.name}: overgrown={counts.get('overgrown',0)}, Blue_Stain={counts.get('Blue_Stain',0)}, Knot_missing={counts.get('Knot_missing',0)}")

print()
for k, v in total.items():
    print(f"Total {k}: {v}")
