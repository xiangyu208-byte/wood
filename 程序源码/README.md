# 木材表面缺陷检测系统

本项目由 Vue 3 前端、Spring Boot 后端、FastAPI/Ultralytics 推理服务和 MariaDB 组成。默认使用 CPU 推理，可在 Windows、Linux、macOS（Intel/Apple Silicon）的 Docker 环境中启动；NVIDIA Linux/Windows Docker 环境可选用 GPU 镜像。

## 目录结构

```text
程序源码/
├─ wood_detect_frontend/             Vue 3 前端与 Nginx 配置
├─ wood_detect_backend/wood_backend/ Spring Boot 后端
├─ wood_detect_python/wood_detect/   FastAPI 推理服务
├─ ultralytics-main/                 项目使用的 Ultralytics 源码与模型
├─ scripts/                          Windows、Linux、macOS 启停脚本
├─ docker-compose.yml                默认 CPU 编排
└─ docker-compose.gpu.yml            NVIDIA GPU 覆盖配置
```

## 运行要求

- Docker Desktop 4.x 或 Docker Engine + Docker Compose v2
- CPU 模式建议至少 8 GB 内存，首次构建需要联网下载基础镜像和依赖
- GPU 模式需要 NVIDIA GPU、合适的宿主机驱动和 NVIDIA Container Toolkit
- CPU 默认模型：`ultralytics-main/runs/detect/best.onnx`
- GPU 默认模型：`ultralytics-main/runs/detect/best.pt`

不需要在宿主机安装 Java、Node.js、Python、MariaDB 或 CUDA SDK。

## 一键启动（CPU）

在本目录执行：

```bash
docker compose up --build
```

首次启动后访问 <http://localhost:8088>。后台运行可加 `-d`：

```bash
docker compose up -d --build
```

也可以使用脚本：

```powershell
# Windows PowerShell
.\scripts\start.ps1
.\scripts\stop.ps1
```

```bash
# Linux / macOS
chmod +x scripts/*.sh
./scripts/start.sh
./scripts/stop.sh
```

脚本会在缺少 `.env` 时由 `.env.example` 创建一份。直接使用 `docker compose` 时，即使没有 `.env` 也会采用编排文件中的开发默认值。

## NVIDIA GPU 模式

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```

或使用脚本：

```powershell
.\scripts\start.ps1 -Gpu
.\scripts\stop.ps1 -Gpu
```

```bash
./scripts/start.sh --gpu
./scripts/stop.sh --gpu
```

GPU 模式仅面向具备 NVIDIA 容器运行环境的平台。macOS 使用默认 CPU 模式。

## 环境变量

复制 `.env.example` 为 `.env` 后可修改配置。主要变量如下：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `FRONTEND_PORT` | `8088` | 浏览器访问端口 |
| `BACKEND_PORT` | `8080` | 后端调试端口 |
| `PYTHON_PORT` | `8001` | 推理服务调试端口 |
| `DB_PORT` | `3306` | 数据库宿主机端口 |
| `FRONTEND_BIND_HOST` | `0.0.0.0` | 前端监听地址，允许局域网访问 |
| `BACKEND_BIND_HOST` / `PYTHON_BIND_HOST` / `DB_BIND_HOST` | `127.0.0.1` | 内部调试端口默认只监听本机 |
| `DB_NAME` | `wood_detect` | 数据库名 |
| `DB_USERNAME` | `wood` | 业务数据库用户 |
| `DB_PASSWORD` | `wood_change_me` | 业务数据库密码 |
| `DB_ROOT_PASSWORD` | `root_change_me` | 数据库 root 密码 |
| `ONNX_MODEL_PATH` | `./ultralytics-main/runs/detect/best.onnx` | CPU 模型文件路径 |
| `PYTORCH_MODEL_PATH` | `./ultralytics-main/runs/detect/best.pt` | GPU 模型文件路径 |
| `MODEL_DEVICE` | `0` | GPU 编号，仅 GPU 覆盖配置使用 |
| `CONFIDENCE_THRESHOLD` | `0.25` | 推理置信度阈值 |
| `IMAGE_SIZE` | `640` | 推理输入尺寸 |
| `MAX_CONCURRENT_INFERENCES` | `1` | 单进程并发推理上限 |
| `INFERENCE_ACQUIRE_TIMEOUT_SECONDS` | `5` | 等待推理槽超时，超时返回 503 |
| `TILE_IMAGE_SIZE` | `896` | 精细模式切片尺寸 |
| `TILE_OVERLAP` | `0.20` | 切片重叠比例 |
| `NMS_IOU_THRESHOLD` | `0.50` | 跨切片按类别 NMS 阈值 |
| `AUTO_MAX_DIMENSION` | `2560` | 自适应切片最长边阈值 |
| `AUTO_PIXEL_COUNT` | `4000000` | 自适应切片像素数阈值 |
| `MAX_FILE_SIZE` / `MAX_REQUEST_SIZE` | `20MB` / `100MB` | 上传大小限制 |
| `ALLOWED_IMAGE_EXTENSIONS` | `jpg,jpeg,png,bmp` | 允许的图片扩展名 |
| `MAX_IMAGE_WIDTH` / `MAX_IMAGE_HEIGHT` | `10000` | 最大图片宽高 |
| `MAX_IMAGE_PIXELS` | `40000000` | 最大像素数 |
| `MAX_BATCH_SIZE` | `50` | 批量上传上限 |
| `PYTHON_CONNECT_TIMEOUT` / `PYTHON_READ_TIMEOUT` | `3s` / `120s` | 推理调用超时 |
| `PYTHON_MAX_ATTEMPTS` | `2` | 推理最大尝试次数 |
| `QUALITY_WEIGHT_SPLIT` / `DRY_KNOT` / `EDGE_KNOT` | `8` / `6` / `5` | 裂纹、干节、边节单个缺陷扣分 |
| `QUALITY_WEIGHT_WAVE` / `SOUND_KNOT` / `SMALL_KNOT` | `3` / `2.5` / `2` | 波纹、健全节、小节单个缺陷扣分 |
| `QUALITY_AREA_PENALTY_PER_PERCENT` / `QUALITY_MAX_AREA_PENALTY_PER_PERCENT` | `0.35` / `0.25` | 覆盖率、最大单框面积率每 1% 扣分 |
| `QUALITY_GRADE_A_MIN` / `B_MIN` / `C_MIN` | `90` / `75` / `60` | 项目内部 A/B/C/D 等级阈值 |
| `MODEL_VERSION` | 自动生成 | 留空时使用模型文件名与 SHA-256 前 12 位 |
| `ACTIVE_LEARNING_LOW_CONFIDENCE_THRESHOLD` | `0.45` | 自动进入人工复核队列的置信度阈值 |

正式部署前必须修改数据库密码。若端口被占用，只需修改 `.env` 中相应端口。
推理接口仅允许读取 `UPLOAD_ROOT` 内的真实文件，并统一返回结构化错误；如无调试需要，请保持后端、推理和数据库端口绑定在 `127.0.0.1`。

## 服务入口与健康检查

| 服务 | 默认地址 | 健康检查 |
|---|---|---|
| 前端统一入口 | <http://localhost:8088> | <http://localhost:8088/health> |
| Spring Boot | <http://localhost:8080> | <http://localhost:8080/actuator/health> |
| FastAPI | <http://localhost:8001> | <http://localhost:8001/health> |
| MariaDB | `localhost:3306` | Compose 内置 `mariadb-admin ping` |

前端通过同源 `/api` 访问后端，通过 `/static` 访问原图和结果图。Nginx 统一代理这两个路径，因此浏览器端不再依赖写死的 `localhost:8080`。

Swagger 文档位于 <http://localhost:8080/swagger-ui.html>，OpenAPI JSON 位于 <http://localhost:8080/v3/api-docs>。

异步批量任务接口：

- `POST /api/detect/batch-upload-async`：创建任务并返回 HTTP 202。
- `GET /api/detect/batch-status/{batchNo}`：读取总体进度、成功/失败数量及逐项状态。
- `POST /api/detect/batch-cancel/{batchNo}`：取消等待处理的项目，并保留已完成结果。
- `POST /api/detect/batch-retry/{batchNo}`：重新执行失败或已取消的项目。

上传与摄像头接口还接受 `modelMode=FAST|STANDARD|ACCURATE`、`confidenceThreshold=0.05..0.95` 和 `precision=AUTO|FP32|FP16`。FP16 仅用于 CUDA 推理服务。

查看状态和日志：

```bash
docker compose ps
docker compose logs -f
docker compose logs -f inference
```

## 持久化与备份

Compose 使用两个命名卷：

- `wood-detect-db-data`：MariaDB 数据文件。
- `wood-detect-uploads`：上传原图与推理结果图，由后端和推理服务共享。

CPU 模式把 ONNX 模型只读挂载到 `/models/best.onnx`；GPU 覆盖配置把 PyTorch 权重挂载到 `/models/best.pt`。模型不复制到持久化卷。

## 模型训练、评估与导出

```bash
cd ultralytics-main
pip install -e .
pip install -r requirements-model.txt
python train.py --config configs/train.yaml
python evaluate.py --model runs/detect/best.pt --data yolo-bvn.yaml
python export_onnx.py --model runs/detect/best.pt --imgsz 896 --opset 17
python benchmark.py --models runs/detect/best.pt runs/detect/best.onnx --source path/to/images --device cpu
```

详细模型身份、历史指标和复现边界见 `ultralytics-main/MODEL_REPORT.md`。数据集不在仓库中，训练和评估会在路径检查阶段停止；恢复数据后再生成混淆矩阵、PR/F1 曲线及正式指标。

## 自适应高分辨率推理

- 快速整图：512px 单次推理。
- 自适应：先执行 640px 整图推理，根据分辨率、首轮置信度和目标尺寸决定是否升级。
- 精细切片：896px 切片、20% 重叠，坐标还原后使用按类别 NMS 合并重复框。

检测结果和历史记录会显示请求模式、实际策略、选择依据、推理耗时和区域数。恢复验证集后，可运行：

```bash
docker compose exec inference python compare_modes.py \
  --source /data/uploads/original \
  --labels /path/to/labels \
  --output /data/uploads/reports/phase5-mode-comparison.json
```

不提供 `--labels` 时只输出耗时和检测数，不会生成伪造的精度指标。

## 可解释质量评分

后端在识别成功时统计六类缺陷与疑似异常候选数量，计算检测框去重覆盖面积率和最大单框面积率，再按可配置权重从 100 分中逐项扣分。结果页显示质量分、A/B/C/D 等级、类别数量和每条扣分原因；历史页支持等级及分数区间筛选，CSV/Excel 会导出完整评价快照。升级前已有且具备图片尺寸的成功记录会在启动后自动补齐评分。

质量等级仅为本项目内部评价规则，用于结果比较和人工复核参考，不属于任何行业强制标准。

## 主动学习与人工复核

- 推理结果保存权重版本、最低置信度和自动复核原因；低置信度或疑似异常记录自动进入待复核队列。
- 记录详情支持确认正确、标记错误、修正类别和坐标、删除误检框及补充漏检框。人工标注单独保存，不覆盖原始模型明细。
- 历史页支持模型版本、复核状态和待复核队列筛选，并展示各版本的人工确认率、纠错率、平均质量分和平均耗时变化。
- “复核数据 YOLO”会导出已复核原图、YOLO 标签、`data.yaml`、说明和包含模型版本/复核状态的 `manifest.json`。未复核记录不会混入训练包。

推荐闭环为：检测 → 自动入队 → 人工复核 → YOLO 导出 → `train.py` 再训练 → `evaluate.py` 独立验证 → `export_onnx.py` 部署 → 版本指标对比。标记为错误且无人工框的记录以空标签负样本导出。

普通停止或重建容器不会删除数据：

```bash
docker compose down
```

`docker compose down -v` 会永久删除数据库和上传卷，请仅在确定需要清空全部业务数据时使用。数据库表由后端启动时通过 Flyway 自动创建和升级，迁移脚本位于 `wood_detect_backend/wood_backend/src/main/resources/db/migration`。

## 本地开发

后端默认启用 `dev` 配置，数据库用户名和密码必须通过环境变量提供。项目自带 Maven Wrapper：

```powershell
cd wood_detect_backend\wood_backend
$env:DB_USERNAME='wood'
$env:DB_PASSWORD='your_password'
$env:UPLOAD_PATH='..\..\data\uploads'
.\mvnw.cmd test
.\mvnw.cmd spring-boot:run
```

配置文件位于：

- `application.yml`：公共配置与环境变量入口。
- `application-dev.yml`：本机开发连接地址。
- `application-docker.yml`：Compose 服务名与容器路径。
- `application-prod.yml`：生产环境强制从环境变量读取敏感配置。

前端开发服务器会把 `/api` 和 `/static` 代理到 `VITE_DEV_BACKEND_URL`（默认 `http://127.0.0.1:8080`）。

```bash
cd wood_detect_frontend
npm ci
npm test
npm run dev
```

推理服务可通过以下变量本地运行：

```powershell
$env:MODEL_PATH='..\..\ultralytics-main\runs\detect\best.onnx'
$env:UPLOAD_ROOT='..\..\data\uploads'
python detect.py
```

从上述两个子项目目录启动时，`UPLOAD_PATH` 和 `UPLOAD_ROOT` 必须指向同一个共享目录；默认均为 `程序源码/data/uploads`。

运行全部 Python 单元测试与已启动 Compose 环境的冒烟测试：

```powershell
python -m unittest discover -s wood_detect_python\wood_detect -p "test_*.py" -v
python .\scripts\smoke_test.py
```

GitHub Actions 会在推送和拉取请求时运行后端测试、前端测试/构建、Python 测试、前端生产依赖漏洞检查以及 Compose 配置校验。

## 常见问题

- `inference` 长时间处于 `starting`：模型首次加载较慢，可运行 `docker compose logs inference` 查看详情。
- 模型挂载失败：确认 `.env` 中 `ONNX_MODEL_PATH` 或 `PYTORCH_MODEL_PATH` 指向存在的文件，而不是目录。
- 端口占用：修改 `.env` 中对应的 `*_PORT`，然后重新启动。
- Apple Silicon 构建较慢：首次安装 ARM64 PyTorch/Ultralytics 依赖需要较长时间，后续会使用 Docker 缓存。
- GPU 容器无法启动：先通过 `docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi` 验证宿主机 GPU 容器环境。

## 当前完成范围与边界

前七阶段已完成工程标准化、跨平台容器、后端可靠性、前端体验、统一模型流水线、自适应高分辨率推理、可解释质量评分，以及主动学习与人工复核闭环。

第五阶段已提供快速整图、自适应和精细切片推理，贯通实际策略、耗时与切片元数据；仍需恢复原数据集以独立复算模式精度，并补充更完整的集成、端到端测试和跨平台验收矩阵。
