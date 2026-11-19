# 木材缺陷正式 10 类数据集

正式 YOLO 数据位于 `wood_defect_10class/`。数据集明确排除了髓心破坏；由于有效标注和独立评估样本不足，也暂时排除了虫蛀/虫孔与霉变。原 12 类结果只作为可追溯的转换来源保留，不再作为训练类别契约。

## 类别与规模

| ID | 类别 | 中文 | 图片数 | 目标数 |
|---:|---|---|---:|---:|
| 0 | dry_knot | 干节 | 1966 | 2562 |
| 1 | sound_knot | 健全节 | 1807 | 2598 |
| 2 | edge_knot | 边节 | 453 | 497 |
| 3 | small_knot | 小节 | 1181 | 1934 |
| 4 | split | 裂纹 | 980 | 1594 |
| 5 | wave | 波纹 | 1584 | 2199 |
| 6 | decay | 腐朽/腐烂 | 372 | 1110 |
| 7 | large_hole | 大型空洞/树洞 | 500 | 525 |
| 8 | bark_pocket | 树皮脱落/夹皮 | 578 | 3590 |
| 9 | stain | 颜色异常/污渍 | 923 | 1171 |

合计 6119 张图片、17780 个目标；train/val/test 为 4847/967/305。完整机器可读报告见 `wood_defect_10class/metadata/validation_report.json`。

## 为什么从 12 类调整为 10 类

严格复核后，虫蛀只有 45 张图片、70 个框，霉变只有 7 张图片、7 个框；两类在验证集和测试集中都各只有 1 张图片。这只能用于流程冒烟，无法支持稳定训练、泛化判断或可信的逐类指标。因此正式模型移除这两类：原类别 10、11 分别重编号为新的 8、9，且仅含已移除类别的图片不会进入 10 类数据集。

未来只有在同一生产相机域下补足人工强框标注，并建立规模足够且与训练集独立的验证/测试集后，才应恢复虫蛀或霉变类别。

## 标注质量与审计

- `zenodo6`、`vsb`：原始目标框，强标注。
- `spruce_bark`、`oak_rot`：原始像素掩码转换出的目标框，强标注。
- `wsad`：专家修正的腐朽异常掩码转换出的目标框，强标注。
- `tree_cavity`：人工复核的全图弱框，只在训练集使用。

严格审计结果为 `PASS`：缺失/孤立标签、损坏图片、非法类别、非法框、完全重复、跨集合重复、增强家族泄漏以及验证/测试弱标注均为 0。

## 数据来源与许可证

| 原始来源 | 许可 | 本项目处理 |
| --- | --- | --- |
| Golden Y.，[WoodDefect Detection](https://doi.org/10.5281/zenodo.18205890) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | 保留原框，统一类别和数据划分 |
| VSB-TUO，[Wood Surface Defects](https://huggingface.co/datasets/iluvvatar/wood_surface_defects) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | 将原框转成 YOLO 格式，筛选并映射类别 |
| Jakob Kreft，[Spruce Log Bark Segmentation](https://huggingface.co/datasets/jakobkreft/spruce-log-bark-segmentation) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | 将缺陷掩码转为检测框 |
| nrodgers98，[Oak Defect Detection](https://huggingface.co/datasets/nrodgers98/Oak-Defect-Detection) | [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) | 将腐朽掩码转为检测框 |
| bangling-v50，[WSAD](https://github.com/bangling-v50/WSAD) | [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) | 将腐朽掩码转为检测框 |
| neolam2024，[Tree-Cavity](https://huggingface.co/datasets/neolam2024/Tree-Cavity) | [Apache-2.0](wood_defect_10class/metadata/LICENSE-Tree-Cavity.txt) | 添加人工复核的弱框，仅用于训练 |

逐图出处和标注质量见 [images.jsonl](wood_defect_10class/metadata/images.jsonl)，来源索引见 [sources.json](wood_defect_10class/metadata/sources.json)。

当前正式数据仍含 Oak 与 WSAD 的 CC BY-NC 4.0 来源，仅适合非商业研究。商业使用前必须用具有商业许可的自采或授权数据替换，不能只修改许可证文本。

## 复现

旧的 12 类构建器仅用于生成转换来源；正式输出必须再执行 10 类转换和审计：

```powershell
python datasets/scripts/build_12class_dataset.py
python datasets/scripts/convert_12class_to_10class.py
python datasets/scripts/audit_10class_dataset.py `
  --root datasets/wood_defect_10class `
  --json datasets/wood_defect_10class/metadata/validation_report.json `
  --markdown datasets/wood_defect_10class/metadata/validation_report.md
```

脚本拒绝覆盖非空输出。原始下载缓存已加入 `.gitignore`；正式 10 类图片由 Git LFS 管理，标签、脚本、类别配置、来源清单和验证报告由普通 Git 管理。克隆后请先运行 `git lfs install` 与 `git lfs pull`。

`build_full_12class_dataset.py` 是已停用的旧脚本，存在切分前增强和评估集占位框问题，不要再使用。
