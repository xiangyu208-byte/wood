# 木材缺陷模型流水线

本目录提供正式十类木材缺陷模型的训练、评估、ONNX 导出和性能测试入口。项目内嵌的 Ultralytics 版本为 8.4.21。

## 环境

```bash
pip install -e .
pip install -r requirements-model.txt
```

GPU 训练需要支持 CUDA 的 PyTorch。默认配置读取仓库内的 [十类数据集](../../datasets/README.md)，图片通过 Git LFS 下载。类别顺序见 [yolo-bvn-10class.yaml](yolo-bvn-10class.yaml)。

## 流程

```bash
# 训练时检查十类顺序与数据路径
python train.py --config configs/train-10class.yaml

# 评估；自动保存混淆矩阵、PR/F1 曲线和 evaluation.json
python evaluate.py --model runs/detect/best.pt --data yolo-bvn-10class.yaml --split test

# 导出并用 ONNX Runtime CPU 做前向烟雾测试
python export_onnx.py --model runs/detect/best.pt --imgsz 896 --opset 17 --dynamic

# 在同一批图片上比较 PT 与 ONNX
python benchmark.py --models runs/detect/best.pt runs/detect/best.onnx --source path/to/images --device cpu
```

训练和评估入口检查类别顺序。评估产物默认写入 `runs/evaluate`，基准结果默认写入 `runs/benchmark/benchmark.json`。评估新权重时，使用实际训练输出目录中的 `weights/best.pt`。默认权重的版本和校验值见 [模型发布清单](../deploy/model-release-20260927.json)。
