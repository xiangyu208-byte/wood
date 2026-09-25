# 木材缺陷模型流水线

本目录提供最终 6 类模型的训练、评估、ONNX 导出和性能测试入口。项目内嵌的 Ultralytics 版本为 8.4.21。

## 环境

```bash
pip install -e .
pip install -r requirements-model.txt
```

训练需要 PyTorch CUDA 环境；ONNX Runtime CPU 推理不需要 CUDA。仓库未包含训练数据集，请将数据放到 `datasets/wood_defect`，或通过 `--data` 指向自己的 YAML。目录结构和类别顺序见 `yolo-bvn.yaml`。

## 流程

```bash
# 训练；启动前会检查 6 类顺序和 train/val 路径
python train.py --config configs/train.yaml

# 评估；自动保存混淆矩阵、PR/F1 曲线和 evaluation.json
python evaluate.py --model runs/detect/best.pt --data yolo-bvn.yaml

# 导出并用 ONNX Runtime CPU 做前向烟雾测试
python export_onnx.py --model runs/detect/best.pt --imgsz 896 --opset 17

# 在同一批图片上比较 PT 与 ONNX
python benchmark.py --models runs/detect/best.pt runs/detect/best.onnx --source path/to/images --device cpu
```

训练和评估入口拒绝类别顺序不一致的数据集。评估产物默认写入 `runs/evaluate`，基准结果默认写入 `runs/benchmark/benchmark.json`。权重身份、历史指标、Wise-IoU 核实结果与当前限制见 `MODEL_REPORT.md`。
