# 见微知木 · 木材表面缺陷检测

见微知木面向木材表面质检。系统使用 **YOLOv8s-C2fPSA** 检测十类缺陷，支持图片批量检测、摄像头连续留档和人工复核。同一组板材的上传图片和摄像头照片可以归入同一批次，在历史记录中查看各图扣分、缺陷分布和批次报告。

## 主要功能

- **图片检测**　提供快速整图、自适应检测和精细补检。高分辨率图片可通过重叠切片检测，系统把检测框还原到原图坐标。
- **批次管理**　新建或选择板材编号，将多次上传和摄像头采集归在同一批次。历史记录支持跨页勾选照片归批，也可将多个完整批次并入指定批次。
- **摄像头采集**　支持手动拍照、连续识别和实时识别。连续识别按所选间隔保存图片，实时识别在选定批次后自动归档。浏览器摄像头需要 localhost 或 HTTPS。
- **质检与复核**　查看缺陷类别、检测框、置信度和项目内部质量评分。支持在原图上拖动绘框、移动、缩放和重分类，同时支持历史 CSV/Excel 导出和复核样本的 YOLO 格式导出。
- **大模型结果分析**　按批次或按所选图片查看缺陷类型和逐图扣分柱状图，按需生成文字报告。已复核图片采用最终标注重新评分。

当前支持干节、健全节、边节、小节、裂纹、波纹、腐朽、大型空洞、树皮脱落或夹皮、颜色异常或污渍。

## 快速启动

需要 Docker 和 Docker Compose v2。仓库内附应用推理所需的 PT 和 ONNX 权重。

```bash
git clone https://github.com/xiangyu208-byte/wood.git
cd wood
cd "Source code"
docker compose up -d --build
```

启动后打开 [检测系统](http://localhost:8088)。默认使用 CPU 和 ONNX Runtime。在具备 NVIDIA 容器运行环境的机器上可启用 PyTorch GPU 推理。

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```

启用报告服务时，将 `.env.example` 复制为 `.env`，设置 `DEEPSEEK_API_KEY` 后运行 `docker compose up -d backend`。默认模型为 `deepseek-flash`，可通过 `DEEPSEEK_MODEL` 调整。未配置密钥时，图片检测、摄像头、批次和统计图表仍可使用。更多环境变量、端口、本地开发与备份命令见 [运行文档](Source%20code/README.md)。

## 模型训练

训练和评估需要自行准备有使用权限的 YOLO 数据。以十类数据配置为模板，设置本地数据根目录和训练、验证、测试路径，保留缺陷类别顺序。数据可以存放在仓库根目录下的本地 `datasets/wood_defect_10class`，或通过 `--data` 使用其它位置的配置文件。见[十类数据配置模板](Source%20code/ultralytics-main/yolo-bvn-10class.yaml)。

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

仓库内的 Ultralytics 源码遵循其附带的 [AGPL-3.0 许可证](Source%20code/ultralytics-main/LICENSE)。

## 项目结构

| 目录 | 用途 |
| --- | --- |
| [`Source code/wood_detect_frontend`](Source%20code/wood_detect_frontend) | Vue 3、Element Plus 与 Nginx |
| [`Source code/wood_detect_backend/wood_backend`](Source%20code/wood_detect_backend/wood_backend) | Spring Boot、MariaDB 与 Flyway |
| [`Source code/wood_detect_python/wood_detect`](Source%20code/wood_detect_python/wood_detect) | FastAPI 图像推理服务 |
| [`Source code/ultralytics-main`](Source%20code/ultralytics-main) | 模型结构、训练、评估与导出脚本 |
