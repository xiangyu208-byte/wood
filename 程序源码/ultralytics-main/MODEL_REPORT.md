# 木材缺陷检测模型报告

## 结论

当前 `best.pt` 是 Ultralytics 8.4.21 训练的 6 类 YOLOv8s-C2fPSA 检测模型。第五阶段将 ONNX 更新为动态输入尺寸、opset 17 的 `best.onnx`，并使用 ONNX Runtime `CPUExecutionProvider` 完成计算图校验以及 512×512、640×640、896×896 三种尺寸前向验证，以支持快速整图和高分辨率切片推理。

仓库不包含训练/验证数据集，因此本报告把权重内保存的历史指标与可独立复现的评估结果严格分开。Precision、Recall 和 mAP 是权重检查点携带的历史验证结果，目前不能通过 `evaluate.py` 独立复算；混淆矩阵、PR 曲线和 F1 曲线也必须在原验证集恢复后重新生成。

## 模型身份

| 项目 | 值 |
|---|---|
| PyTorch 权重 | `runs/detect/best.pt` |
| PyTorch SHA-256 | `c6b6ba26110d9257f5f3b9a0fa04800030a25a9ff2198b7b051a99597bfb0535` |
| ONNX 权重 | `runs/detect/best.onnx` |
| ONNX SHA-256 | `d5bd6032be1bb9f0be979e92b30718670c0b282bf701e21d0f58e50948678a17` |
| Ultralytics | `8.4.21` |
| 结构 | YOLOv8s，Backbone 含 2 个 C2fPSA 模块 |
| 参数量 | 9,915,906（融合后 9,904,226） |
| 输入尺寸 | 动态高度和宽度；当前使用 512、640、896 三档 |
| 类别数 | 6 |
| 数据版本 | 不可用，原始数据集未随仓库提供 |

类别顺序是模型接口的一部分，模型元数据、数据 YAML 和前端必须保持一致：

1. `dry_knot`（干节）
2. `sound_knot`（健全节）
3. `edge_knot`（边节）
4. `small_knot`（小节）
5. `split`（裂纹）
6. `wave`（波纹）

## 权重内保存的训练配置

权重记录的主要参数为：500 epochs、batch 32、imgsz 896、AdamW、lr0 0.001、lrf 0.01、weight decay 0.0005、warmup 5、cosine LR、patience 50、close mosaic 15、seed 0。统一配置见 `configs/train.yaml`，网络结构见 `configs/yolov8s-c2fpsa.yaml`。

训练历史共保存 431 个 epoch，说明训练在配置的 500 epoch 之前停止。检查点被剥离后 `epoch` 字段为 -1，不能据此判断最佳 epoch；完整逐轮序列仍在检查点的 `train_results` 字段中。

## 指标口径

| 指标 | 权重内历史值 | 独立复评状态 |
|---|---:|---|
| Precision | 0.95374 | 待原验证集恢复 |
| Recall | 0.89180 | 待原验证集恢复 |
| mAP50 | 0.95145 | 待原验证集恢复 |
| mAP50-95 | 0.75373 | 待原验证集恢复 |

这些值来自 `best.pt` 的 `train_metrics`，不是本次重新运行 `evaluate.py` 得到的结果。论文和演示材料在数据集恢复前应使用相同数值并明确标注“检查点记录值”，不能把不一致的 0.9425 或 0.955 当作 mAP50。

## Wise-IoU 核实结果

当前仓库没有 Wise-IoU/WIoU 源码、损失配置或训练参数，检查点模块和训练参数中也没有相应记录。现有 Ultralytics 检测损失使用 BCE 分类损失、CIoU 边框回归损失和 DFL。因而不能声称最终模型使用了 Wise-IoU，也不能声称它带来了指标提升。论文已改为只描述有代码和权重证据支持的 C2fPSA 改进。

## CPU 推理烟雾基准

2026-09-25 在 Docker Linux、Intel Core i9-14900HX、单张论文内嵌木材缺陷样本、896×896、1 次预热和 3 次计时条件下，对当前动态 ONNX 重新测试：

| 格式 | 平均延迟 | 中位延迟 | 吞吐量 |
|---|---:|---:|---:|
| PyTorch CPU | 151.98 ms/张 | 154.88 ms/张 | 6.58 张/秒 |
| ONNX Runtime CPU | 107.07 ms/张 | 99.69 ms/张 | 9.34 张/秒 |

样本从项目论文文档的历史识别原图区域裁取，是木材图片但没有独立 YOLO 标签。该测试只证明两种后端能够完成木材图片推理，不代表木材数据集上的精度，也不是正式性能结论。机器、线程、图片数量和输入尺寸变化都会改变结果；正式报告应对验证集多轮测试并记录硬件与线程配置。

## 可复现命令

在 `程序源码/ultralytics-main` 目录执行：

```bash
python train.py --config configs/train.yaml
python evaluate.py --model runs/detect/best.pt --data yolo-bvn.yaml
python export_onnx.py --model runs/detect/best.pt --imgsz 896 --opset 17
python benchmark.py --models runs/detect/best.pt runs/detect/best.onnx --source path/to/images --device cpu
```

GPU 推理保留 `best.pt`，设置 `MODEL_DEVICE=0`；默认 CPU Compose 使用 `best.onnx` 和 ONNX Runtime。

## 尚未完成的科学验收

恢复与原实验完全一致的数据集版本后，必须执行以下操作：

1. 在 `configs/dataset-version.yaml` 中登记不可变版本或归档哈希。
2. 运行 `evaluate.py` 生成 `evaluation.json`、混淆矩阵、PR 曲线和 F1 曲线。
3. 将重新计算的指标与检查点记录值核对；不一致时以可复评结果为准。
4. 更新论文和答辩材料中的表格、图和指标口径。
