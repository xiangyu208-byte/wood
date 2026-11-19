# 10-class dataset audit

- status: **PASS**
- images: 6119
- objects: 17780
- split: {'train': 4847, 'val': 967, 'test': 305}

## Issues

- None

## Class distribution

| id | class | images | objects | train | val | test | placeholder boxes |
|---:|---|---:|---:|---:|---:|---:|---:|
| 0 | dry_knot | 1966 | 2562 | 1549 | 320 | 97 | 0 |
| 1 | sound_knot | 1807 | 2598 | 1433 | 278 | 96 | 0 |
| 2 | edge_knot | 453 | 497 | 363 | 90 | 0 | 0 |
| 3 | small_knot | 1181 | 1934 | 982 | 199 | 0 | 0 |
| 4 | split | 980 | 1594 | 792 | 163 | 25 | 0 |
| 5 | wave | 1584 | 2199 | 1292 | 292 | 0 | 0 |
| 6 | decay | 372 | 1110 | 292 | 49 | 31 | 0 |
| 7 | large_hole | 500 | 525 | 389 | 71 | 40 | 22 |
| 8 | bark_pocket | 578 | 3590 | 450 | 63 | 65 | 0 |
| 9 | stain | 923 | 1171 | 641 | 111 | 171 | 0 |

## Integrity summary

- exact duplicate groups: 0
- exact cross-split duplicate groups: 0
- leaking augmentation/source families: 0
- placeholder boxes in validation/test: 0
- weak images in validation/test: 0
