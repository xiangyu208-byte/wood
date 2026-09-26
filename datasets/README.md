# 木材缺陷 12 类数据集

本目录包含可复现的数据收集、筛选、转换和校验流程。最终 YOLO 数据位于
`wood_defect_12class/`，明确排除了 `marrow`（髓心/髓心破坏）。

## 类别与当前规模

| ID | 类别 | 中文 | 图片数 | 目标数 |
|---:|---|---|---:|---:|
| 0 | dry_knot | 干节 | 1966 | 2562 |
| 1 | sound_knot | 健全节 | 1807 | 2598 |
| 2 | edge_knot | 边节 | 453 | 497 |
| 3 | small_knot | 小节 | 1181 | 1934 |
| 4 | split | 裂纹 | 980 | 1594 |
| 5 | wave | 波纹 | 1584 | 2199 |
| 6 | decay | 腐朽/腐烂 | 82 | 226 |
| 7 | large_hole | 大型空洞/树洞 | 500 | 525 |
| 8 | insect_damage | 虫蛀/虫孔 | 20 | 42 |
| 9 | mold | 霉变 | 8 | 8 |
| 10 | bark_loss | 树皮脱落 | 578 | 3590 |
| 11 | stain | 颜色异常/污渍 | 923 | 1171 |

合计 5857 张图片、16946 个目标；train/val/test 为 4640/930/287。完整机器可读报告见
`wood_defect_12class/metadata/validation_report.json`。

## 标注质量

- `zenodo6`、`vsb`：原始目标框，强标注。
- `spruce_bark`、`oak_rot`：原始像素掩码转换出的目标框，强标注。
- `mvtec_hole`：木材孔洞掩码转换出的虫孔代理标注；应在实际虫蛀木材上复核。
- `openverse`：人工目视筛选后的整图弱标注；除 1 张霉变验证图和 1 张霉变测试图外均只进入训练集。弱标注指标只能用于冒烟检查，不能作为生产精度结论。

霉变和虫蛀仍属于小样本类别。当前数据足以打通 12 类训练流程，但不应据此宣称这两类已达到生产精度；上线前应优先补充同一相机、光照和木材品种下的人工框标注，并将新增强标注样本加入独立验证集。

## 数据来源与许可证

- Zenodo WoodDefect Detection：CC BY 4.0。
- VSB-TUO / `iluvvatar/wood_surface_defects`：CC BY 4.0。
- Spruce Log Bark Segmentation：CC BY 4.0。
- Oak Defect Detection：CC BY-NC 4.0。
- MVTec AD：CC BY-NC-SA 4.0。
- Tree-Cavity：Apache-2.0。
- Openverse 图片：逐图为 CC0、PDM 或 CC BY，归属和落地页记录在 `metadata/images.jsonl`。

注意：由于包含 Oak 与 MVTec 来源，当前组合数据集仅适合非商业研究用途。若需要商业使用，必须移除这两个来源并用具有商业许可的自采/授权数据替换，不能仅修改许可证文本。

## 复现

```powershell
python datasets/scripts/collect_openverse_candidates.py
python datasets/scripts/download_oak_rot_subset.py --images 80
python datasets/scripts/download_tree_cavity.py
python datasets/scripts/build_12class_dataset.py
```

构建器拒绝覆盖已有输出。重新构建时请先将当前 `wood_defect_12class` 目录移到备份位置，再运行脚本。原始大文件与生成图片已加入 `.gitignore`，Git 中只保存脚本、类别配置、来源清单和验证报告。
