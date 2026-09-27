# 木材缺陷检测模型报告

## 结论

2026-09-27 默认 `best.pt` 已替换为 Ultralytics 8.4.21 新训练的 10 类 YOLOv8s-C2fPSA 检测模型。训练记录共 162 轮，按 mAP50–95 最优选择第 161 轮 `weights/best.pt`，不是最后一轮 `last.pt`。同步导出动态尺寸、opset 17 的 `best.onnx`，通过 ONNX 计算图校验与 CPU 512×512、640×640、896×896 三档前向检查。

本次完成部署、导出和少量真实图片接口冒烟，未开启新训练，也未运行完整独立复评。下方 Precision、Recall 和 mAP 来自最佳检查点与同轮 `results.csv`，不是接口冒烟的精度。训练目录自带曲线；独立验证/测试指标应通过 `evaluate.py` 另行生成。

## 模型身份

| 项目 | 值 |
|---|---|
| PyTorch 权重 | `runs/detect/best.pt` |
| PyTorch SHA-256 | `23c55915874f10d9ba462cf030fc97f4495daf5e43e438a1e1a5f47dde531099` |
| ONNX 权重 | `runs/detect/best.onnx` |
| ONNX SHA-256 | `33938785862176b20ef6a0e5737cf1e62972d4c8582990f12f4b8a6f615349d0` |
| Ultralytics | `8.4.21` |
| 结构 | YOLOv8s，Backbone 含 2 个 C2fPSA 模块 |
| 参数量 | 9,917,454（融合后 9,905,774） |
| 输入尺寸 | 动态高度和宽度；当前使用 512、640、896 三档 |
| 类别数 | 10；ONNX 输出通道 14=4 框坐标+10 类分数 |
| 数据版本 | `wood-defect-10class` / `2026-09-27-v1`（6119 张/17780 框） |
| 训练源 | `runs/detect/wood-yolov8s-c2fpsa-10class/weights/best.pt` |
| 发布快照 | `runs/deploy/wood10-e161-20260927` |
| 旧版备份 | `runs/deploy/legacy6-before-wood10-20260927`（本地备份，保留 PT/ONNX/清单） |

类别顺序是模型接口的一部分，模型元数据、数据 YAML 和前端必须保持一致：

1. `dry_knot`（干节）
2. `sound_knot`（健全节）
3. `edge_knot`（边节）
4. `small_knot`（小节）
5. `split`（裂纹）
6. `wave`（波纹）
7. `decay`（腐朽/腐烂）
8. `large_hole`（大型空洞/树洞）
9. `bark_pocket`（树皮脱落/夹皮）
10. `stain`（颜色异常/污渍）

新推理不再返回 `suspected_anomaly`。在自适应/精细模式整图或切片结果为空、或仅命中边缘时，暗部规则只定位内部复查区域；模型对带上下文的区域裁剪重新推理，按最高概率类别输出，使用原始模型置信度而非暗部强度。普通检测仍按用户阈值过滤，兜底复查不受该阈值限制；区域框来自规则，类别和置信度来自模型。非木色图、无合格区域或无有效模型输出时不强行生成缺陷；快速模式不启用此兜底。低置信结果继续入人工复核队列，误报可能增多，不能把强制归类解释为精度提升。历史异常记录保留，需要重新识别才会更新。

服务启动时检查类别数量和顺序，误挂旧 6 类权重会明确报错；读取 ONNX 类别前也遵守配置设备，避免 CPU 配置误初始化 GPU 后端。默认模型路径不再依赖启动目录。GPU 容器基础镜像升级为 PyTorch 2.9.1/CUDA 13，以适配 RTX 50 系列；本机实测环境为 PyTorch 2.13.0+cu130 与 RTX 5070 Laptop GPU。

## 权重内保存的训练配置

本次训练 `args.yaml` 记录：最多 300 epochs、自动 batch（-1）、imgsz 896、AdamW、patience 30、cosine LR、close mosaic 15、seed 0、AMP、device 0、workers 4、pretrained false。网络结构见 `configs/yolov8s-c2fpsa-10class.yaml`；实际运行参数以训练目录的 `args.yaml` 为准。

逐轮 CSV 共 162 轮，最佳检查点内部 `epoch=160`（零起点，即第 161 轮），验证 mAP50–95=0.51083；第 162 轮为 0.50974。原训练目录和 `last.pt` 未修改，可继续用于恢复训练。

## 指标口径

| 指标 | 权重内历史值 | 独立复评状态 |
|---|---:|---|
| Precision | 0.81052 | 待完整独立复评 |
| Recall | 0.68211 | 待完整独立复评 |
| mAP50 | 0.72899 | 待完整独立复评 |
| mAP50-95 | 0.51083 | 待完整独立复评 |

这些值来自新 `best.pt` 的 `train_metrics`，并与 CSV 第 161 轮一致。原 6 类模型历史 mAP50=0.95145、mAP50–95=0.75373 只适用于旧模型与旧评估范围，不能用来宣称新 10 类模型的指标，也不能直接比较两套不同类别/数据集的精度。

## Wise-IoU 核实结果

当前仓库没有 Wise-IoU/WIoU 源码、损失配置或训练参数，检查点模块和训练参数中也没有相应记录。现有 Ultralytics 检测损失使用 BCE 分类损失、CIoU 边框回归损失和 DFL。因而不能声称最终模型使用了 Wise-IoU，也不能声称它带来了指标提升。论文已改为只描述有代码和权重证据支持的 C2fPSA 改进。

## 旧版 6 类 CPU 推理烟雾基准（仅保留历史）

2026-09-25 在 Docker Linux、Intel Core i9-14900HX、单张论文内嵌木材缺陷样本、896×896、1 次预热和 3 次计时条件下，对旧 6 类动态 ONNX 测试（不是新版性能）：

| 格式 | 平均延迟 | 中位延迟 | 吞吐量 |
|---|---:|---:|---:|
| PyTorch CPU | 151.98 ms/张 | 154.88 ms/张 | 6.58 张/秒 |
| ONNX Runtime CPU | 107.07 ms/张 | 99.69 ms/张 | 9.34 张/秒 |

样本从项目论文文档的历史识别原图区域裁取，是木材图片但没有独立 YOLO 标签。该测试只证明两种后端能够完成木材图片推理，不代表木材数据集上的精度，也不是正式性能结论。机器、线程、图片数量和输入尺寸变化都会改变结果；正式报告应对验证集多轮测试并记录硬件与线程配置。

## 可复现命令

### 本次部署验证

Python 单测 15/15、后端单测 15/15、前端单测 6/6、前端生产构建及 CPU/GPU Compose 配置检查通过。在本机 RTX 5070 Laptop GPU 上用 PyTorch FP16、在 CPU 上用 ONNX FP32，分别通过 `/health` 和 `/predict` 的 FastAPI 测试客户端完成四个新增类别的真实标注验证图片、三种推理模式、暗部兜底及错误参数检查。某些真实样本快速模式没有检出；冒烟只证明推理链路与类别契约可用，不是逐类召回率验收。

部署记录见 `../deploy/model-release-20260927.json`（相对本目录）。初次替换后完成 PyTorch GPU 与 ONNX CPU 接口冒烟；随后推理优化完成 CPU Compose 四服务、网页上传、批次、详情、历史结果及九组模式/阈值请求验收，详见 `../deploy/inference-final-optimization-20260927.md`。本次 GitHub 运行版不提交验证用图片、数据集及本地原始实验输出。

### 训练、评估与导出

在 `程序源码/ultralytics-main` 目录执行：

```bash
python train.py --config configs/train-10class.yaml
python evaluate.py --model runs/detect/wood-yolov8s-c2fpsa-10class/weights/best.pt --data yolo-bvn-10class.yaml
python export_onnx.py --model runs/detect/wood-yolov8s-c2fpsa-10class/weights/best.pt --imgsz 896 --opset 17 --dynamic
python benchmark.py --models runs/detect/wood-yolov8s-c2fpsa-10class/weights/best.pt runs/detect/wood-yolov8s-c2fpsa-10class/weights/best.onnx --source path/to/images --device cpu
```

GPU 推理保留 `best.pt`，设置 `MODEL_DEVICE=0`；默认 CPU Compose 使用 `best.onnx` 和 ONNX Runtime。

## 尚未完成的科学验收

原 6 类数据和正式 10 类扩展数据已就绪，仍必须执行以下科学验收：

1. 固化本地数据版本与来源标识；当前信息已登记在 `configs/dataset-version.yaml`，训练图片和标注不随 GitHub 运行版发布。
2. 新 10 类训练和默认模型替换已完成；仍需运行 `evaluate.py` 生成完整独立评估的 `evaluation.json`、混淆矩阵、PR 曲线和 F1 曲线。
3. 将重新计算的 10 类指标与新检查点记录值核对；不一致时以可复评结果为准。
4. 虫蛀和霉变已从正式类别中移除；只有补足同域强标注和独立评估集后，才能另行恢复并发布相关精度结论。
5. 更新论文和答辩材料中的表格、图和指标口径。
