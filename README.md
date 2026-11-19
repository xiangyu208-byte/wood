# 见微知木 · 木材表面缺陷检测

见微知木面向木材表面质检。系统使用 **YOLOv8s-C2fPSA** 检测十类缺陷，支持图片批量检测、摄像头连续留档和人工复核。局部检测照片可关联到同一板面，查看缺陷在整板上的相对位置和拍摄覆盖情况。

## 主要功能

- **图片检测**　提供快速整图、自适应检测和精细补检。高分辨率图片可通过重叠切片检测，系统把检测框还原到原图坐标。
- **板材地图**　按板号和 A/B 面归档局部照片。可指定已知格位，或通过与格位基准照片重叠的木纹估计位置。坐标以板面左上角为原点，用板长和板宽的百分比表示。位置依据不足的照片显示为「待定位」，整板参考图可选。
- **摄像头采集**　实时抽帧预览把检测框显示在对应帧上。定点连续留档按设定间隔采集，并可将结果关联到指定板面。浏览器摄像头需要 localhost 或 HTTPS。
- **质检与复核**　查看缺陷类别、检测框、置信度和项目内部质量评分。支持人工修正、历史 CSV/Excel 导出和复核样本的 YOLO 格式导出。
- **DeepSeek 辅助质检**　按需发送缩放后的原图和 YOLO 框，获取漏检或错标复核意见。板材地图可根据板面统计生成质检摘要。模型意见供人工核实，原始检测结果保留。

当前支持干节、健全节、边节、小节、裂纹、波纹、腐朽、大型空洞、树皮脱落或夹皮、颜色异常或污渍。

## 快速启动

需要 Docker 和 Docker Compose v2。复现训练前还需安装 Git LFS，以获取数据集图片。

```bash
git clone https://github.com/xiangyu208-byte/wood.git
cd wood
git lfs install
git lfs pull
cd "Source code"
docker compose up -d --build
```

启动后打开 [检测系统](http://localhost:8088)。默认使用 CPU 和 ONNX Runtime。在具备 NVIDIA 容器运行环境的机器上可启用 PyTorch GPU 推理。

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```

需要 DeepSeek 时，将 `.env.example` 复制为 `.env`，设置 `DEEPSEEK_API_KEY` 后运行 `docker compose up -d backend`。默认模型为 `deepseek-flash`，可通过 `DEEPSEEK_MODEL` 调整。未配置密钥时，图片检测、摄像头和板材地图仍可使用。更多环境变量、端口、本地开发与备份命令见 [运行文档](Source%20code/README.md)。

## 数据集和训练

[正式十类数据集](datasets/wood_defect_10class)使用 YOLO 检测格式，含 **6,119 张图片、17,780 个标注框**。训练、验证和测试集分别有 4,847、967 和 305 张图片。测试集当前缺少边节、小节和波纹样本，评估时可查看[类别分布和标注审计](datasets/wood_defect_10class/metadata/validation_report.md)。

在 Python 环境中，从仓库根目录进入模型目录，安装依赖并训练。将下方权重路径替换为实际训练输出路径即可评估新权重和导出 ONNX。

```bash
cd "Source code/ultralytics-main"
pip install -e .
pip install -r requirements-model.txt
python train.py --config configs/train-10class.yaml
python evaluate.py --model runs/detect/best.pt --data yolo-bvn-10class.yaml --split test
python export_onnx.py --model runs/detect/best.pt --imgsz 896 --opset 17 --dynamic
```

Compose 默认加载 `Source code/ultralytics-main/runs/detect/best.onnx` 或 `best.pt`。部署自行训练的模型时，在 `.env` 设置 `ONNX_MODEL_PATH` 或 `PYTORCH_MODEL_PATH`，并保持正式十类的类别顺序。

数据包含 CC BY 4.0、CC BY-NC 4.0 和 Apache-2.0 来源。当前组合数据适用于非商业研究。商用前应确认各来源授权。见[数据说明](datasets/README.md)和[来源清单](datasets/wood_defect_10class/metadata/sources.json)。仓库内的 Ultralytics 源码遵循其附带的 [AGPL-3.0 许可证](Source%20code/ultralytics-main/LICENSE)。

## 项目结构

| 目录 | 用途 |
| --- | --- |
| [`Source code/wood_detect_frontend`](Source%20code/wood_detect_frontend) | Vue 3、Element Plus 与 Nginx |
| [`Source code/wood_detect_backend/wood_backend`](Source%20code/wood_detect_backend/wood_backend) | Spring Boot、MariaDB 与 Flyway |
| [`Source code/wood_detect_python/wood_detect`](Source%20code/wood_detect_python/wood_detect) | FastAPI 推理服务与板面配准 |
| [`Source code/ultralytics-main`](Source%20code/ultralytics-main) | 模型结构、训练、评估与导出脚本 |
| [`datasets`](datasets) | 数据集、来源记录和构建审计脚本 |
