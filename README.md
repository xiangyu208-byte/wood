# Wood — 木材表面缺陷检测系统

Wood 是一个面向木材表面质量检查场景的全栈缺陷检测系统。用户可以通过浏览器上传单张或多张木材图片，也可以调用摄像头拍照识别；系统使用 YOLO 模型完成推理，保存原图、检测结果图与缺陷框明细，并提供历史查询、筛选、删除和报表导出功能。

项目采用前后端分离架构，默认提供无需 CUDA 的 CPU 容器方案，同时保留 NVIDIA GPU 推理方案。Windows、Linux 和 macOS 可使用 Docker Compose 部署，手机和平板可作为浏览器客户端访问。

> 当前仓库仍处于持续开发阶段。前六阶段工程内容已完成，包括容器化、后端可靠性、响应式前端、统一模型流水线、自适应高分辨率切片推理和可解释质量评分。原验证集缺失导致的精度复评项仍明确保留为阻塞。完整进度见[项目实现计划与进度](项目实现计划与进度.md)。

## 主要功能

- 单张图片上传识别，并展示带检测框的结果图。
- 多张图片同步识别，以及带总进度和逐项状态的异步批量任务。
- 支持取消异步批次、重试失败/取消项目，以及单张重新识别。
- 支持快速整图、自适应和精细切片三种模式；自适应模式会根据图片尺寸与首轮结果决定是否执行重叠切片，首轮结果仅位于图片边缘时也会复查整幅图片。
- 基于缺陷类别数量、去重覆盖面积和最大缺陷面积生成 0–100 分与 A/B/C/D 级评价，并逐项展示扣分原因；该等级是可配置的项目内部规则，不是行业强制标准。
- 对木材图片中模型未覆盖的明显暗部、空洞提供“疑似异常（需复核）”补充候选，并与模型六类结果分开标识。
- 浏览器摄像头拍照识别。
- 展示缺陷类别、置信度和边界框坐标。
- 保存检测记录、原图、结果图和缺陷明细。
- 按图片名称、任务状态、批次、来源、缺陷情况和时间范围筛选历史记录。
- 支持单条删除、勾选批量删除和按条件删除。
- 支持 CSV、Excel、原图及结果图 ZIP 导出。
- 上传图片使用 UUID 保存；校验扩展名、真实格式、MIME、宽高和像素数，避免同名覆盖及伪装文件。
- 推理调用支持连接/读取超时和有限重试，服务异常时记录会落为 `FAIL` 并保留失败原因。
- 使用 Flyway 自动创建及升级数据库，历史列表由数据库原生分页。
- 提供统一错误响应、正确 HTTP 状态码和 OpenAPI/Swagger 文档。
- 提供 CPU 和 NVIDIA GPU 两种推理容器。
- CPU 默认使用 ONNX Runtime，GPU 保留 PyTorch CUDA 权重；推理类别直接读取模型元数据。
- 提供服务健康检查、数据库自动建表和持久化数据卷。
- 前端统一处理业务错误、超时、断网和服务不可用，并提供桌面、平板和手机响应式布局。

当前模型识别以下 6 类木材表面缺陷：

| 类别标识 | 中文含义 |
|---|---|
| `dry_knot` | 干节 |
| `sound_knot` | 健全节 |
| `edge_knot` | 边节 |
| `small_knot` | 小节 |
| `split` | 裂纹 |
| `wave` | 波纹 |

`suspected_anomaly` 不是第 7 个模型类别，而是模型结果覆盖不足时由图像算法给出的人工复核候选。它显示的是候选强度，不是 YOLO 置信度，也不参与六类模型精度指标计算。现有权重没有“腐朽/空洞”类别，要获得可统计的此类缺陷识别能力仍需补充圆木横截面数据并重新训练。

## 系统架构

```text
浏览器 / 手机 / 平板
        │
        ▼
Nginx + Vue 3
  ├─ /api    → Spring Boot
  └─ /static → 上传图片与检测结果
        │
        ▼
Spring Boot + MyBatis-Plus
  ├─ 安全文件存储与静态资源访问
  ├─ 同步/异步检测任务和历史记录管理
  ├─ CSV / Excel / ZIP 导出
  ├─ 超时、重试、失败状态与事务补偿
  └─ Flyway 数据库迁移与 OpenAPI 文档
        │
        ▼
FastAPI + Ultralytics + PyTorch
  ├─ CPU 推理
  └─ NVIDIA CUDA 推理
        │
        ▼
MariaDB + Docker 持久化卷
```

## 技术栈

| 模块 | 主要技术 |
|---|---|
| 前端 | Vue 3、Vue Router、Element Plus、Axios、Vite |
| 网关与静态站点 | Nginx |
| 后端 | Java 17、Spring Boot 3.3、MyBatis-Plus、Flyway、Springdoc OpenAPI、Apache POI |
| 推理服务 | Python 3.11、FastAPI、Ultralytics、PyTorch、OpenCV |
| 数据库 | MariaDB 11.4 |
| 部署 | Docker、Docker Compose |

## 仓库结构

```text
wood/
├─ README.md
├─ 项目实现计划与进度.md
├─ 文档资料.docx
└─ 程序源码/
   ├─ docker-compose.yml
   ├─ docker-compose.gpu.yml
   ├─ .env.example
   ├─ scripts/
   │  ├─ start.ps1
   │  ├─ stop.ps1
   │  ├─ start.sh
   │  └─ stop.sh
   ├─ wood_detect_frontend/
   ├─ wood_detect_backend/wood_backend/
   ├─ wood_detect_python/wood_detect/
   └─ ultralytics-main/
      ├─ train.py / evaluate.py / export_onnx.py / benchmark.py
      └─ runs/detect/
         ├─ best.pt
         └─ best.onnx
```

## 快速开始

### 运行要求

- Docker Desktop，或 Docker Engine 与 Docker Compose v2。
- CPU 模式建议至少提供 8 GB 内存。
- 首次构建需要联网下载基础镜像和依赖。
- GPU 模式需要 NVIDIA 显卡、可用的宿主机驱动和 NVIDIA Container Toolkit。

宿主机不需要单独安装 Java、Node.js、Python、MariaDB 或 CUDA SDK。

### CPU 模式

克隆仓库并进入源码目录：

```bash
git clone https://github.com/xiangyu208-byte/wood.git
cd wood/程序源码
```

直接启动：

```bash
docker compose up -d --build
```

启动完成后访问：<http://localhost:8088>。

查看容器状态和日志：

```bash
docker compose ps
docker compose logs -f
```

停止服务：

```bash
docker compose down
```

### NVIDIA GPU 模式

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```

GPU 模式默认使用编号为 `0` 的显卡。macOS 不支持 NVIDIA 容器模式，请使用 CPU 配置。

### 一键启停脚本

Windows PowerShell：

```powershell
.\scripts\start.ps1
.\scripts\stop.ps1

# NVIDIA GPU 模式
.\scripts\start.ps1 -Gpu
.\scripts\stop.ps1 -Gpu
```

Linux / macOS：

```bash
chmod +x scripts/*.sh
./scripts/start.sh
./scripts/stop.sh

# NVIDIA GPU 模式
./scripts/start.sh --gpu
./scripts/stop.sh --gpu
```

脚本会在 `.env` 不存在时自动从 `.env.example` 创建一份本地配置。

## 配置说明

如需修改端口、数据库密码或推理参数，请先创建 `.env`：

```bash
cp .env.example .env
```

常用配置如下：

| 环境变量 | 默认值 | 说明 |
|---|---:|---|
| `FRONTEND_PORT` | `8088` | Web 页面端口 |
| `BACKEND_PORT` | `8080` | Spring Boot 调试端口 |
| `PYTHON_PORT` | `8001` | FastAPI 调试端口 |
| `DB_PORT` | `3306` | MariaDB 对外端口 |
| `DB_NAME` | `wood_detect` | 数据库名称 |
| `DB_USERNAME` | `wood` | 数据库业务用户 |
| `DB_PASSWORD` | `wood_change_me` | 数据库业务用户密码 |
| `DB_ROOT_PASSWORD` | `root_change_me` | 数据库 root 密码 |
| `ONNX_MODEL_PATH` | `./ultralytics-main/runs/detect/best.onnx` | CPU 推理模型路径 |
| `PYTORCH_MODEL_PATH` | `./ultralytics-main/runs/detect/best.pt` | GPU 推理模型路径 |
| `MODEL_DEVICE` | `0` | GPU 设备编号 |
| `CONFIDENCE_THRESHOLD` | `0.25` | 检测置信度阈值 |
| `IMAGE_SIZE` | `640` | 模型输入尺寸 |
| `TILE_IMAGE_SIZE` | `896` | 精细模式切片尺寸 |
| `TILE_OVERLAP` | `0.20` | 相邻切片重叠比例 |
| `NMS_IOU_THRESHOLD` | `0.50` | 跨切片重复框合并阈值 |
| `AUTO_MAX_DIMENSION` | `2560` | 自适应模式触发切片的最长边阈值 |
| `AUTO_PIXEL_COUNT` | `4000000` | 自适应模式触发切片的像素数阈值 |
| `AUTO_EDGE_MARGIN_RATIO` | `0.02` | 判断首轮结果是否仅位于图片边缘的边距比例 |
| `ANOMALY_FALLBACK_ENABLED` | `true` | 是否启用训练类别外的疑似异常补充候选 |
| `ANOMALY_MIN_WOOD_RATIO` | `0.30` | 启用补充候选所需的最小木材色调比例 |
| `ANOMALY_MIN_COMPONENT_RATIO` | `0.001` | 疑似异常区域最小面积比例 |
| `ANOMALY_MAX_COMPONENT_RATIO` | `0.15` | 疑似异常区域最大面积比例 |
| `ANOMALY_MAX_CANDIDATES` | `5` | 单张图片最多补充候选数 |
| `MAX_FILE_SIZE` | `20MB` | 单文件上传限制 |
| `MAX_REQUEST_SIZE` | `100MB` | 单次请求总大小限制 |
| `ALLOWED_IMAGE_EXTENSIONS` | `jpg,jpeg,png,bmp` | 允许的图片扩展名 |
| `MAX_IMAGE_WIDTH` / `MAX_IMAGE_HEIGHT` | `10000` | 最大图片宽高 |
| `MAX_IMAGE_PIXELS` | `40000000` | 最大图片像素数 |
| `MAX_BATCH_SIZE` | `50` | 单次批量图片上限 |
| `PYTHON_CONNECT_TIMEOUT` | `3s` | 推理服务连接超时 |
| `PYTHON_READ_TIMEOUT` | `120s` | 推理服务读取超时 |
| `PYTHON_MAX_ATTEMPTS` | `2` | 推理最大尝试次数 |
| `PYTHON_RETRY_DELAY` | `500ms` | 推理重试间隔 |
| `QUALITY_WEIGHT_SPLIT` / `DRY_KNOT` / `EDGE_KNOT` | `8` / `6` / `5` | 裂纹、干节、边节的单个缺陷扣分 |
| `QUALITY_WEIGHT_WAVE` / `SOUND_KNOT` / `SMALL_KNOT` | `3` / `2.5` / `2` | 波纹、健全节、小节的单个缺陷扣分 |
| `QUALITY_AREA_PENALTY_PER_PERCENT` | `0.35` | 缺陷去重覆盖率每 1% 的扣分 |
| `QUALITY_MAX_AREA_PENALTY_PER_PERCENT` | `0.25` | 最大单框面积率每 1% 的扣分 |
| `QUALITY_GRADE_A_MIN` / `B_MIN` / `C_MIN` | `90` / `75` / `60` | A、B、C 级最低分，低于 C 为 D 级 |
| `QUALITY_RULE_VERSION` | `WOOD-QS-1.0` | 随结果保存的评分规则版本 |

正式部署前请务必修改数据库密码，不要将实际 `.env` 文件提交到仓库。

## 服务地址与健康检查

| 服务 | 默认地址 | 健康检查 |
|---|---|---|
| Web 统一入口 | <http://localhost:8088> | <http://localhost:8088/health> |
| Spring Boot | <http://localhost:8080> | <http://localhost:8080/actuator/health> |
| FastAPI | <http://localhost:8001> | <http://localhost:8001/health> |
| MariaDB | `localhost:3306` | Compose 内置检查 |

实际使用时建议通过 `8088` 的 Nginx 统一入口访问系统。前端 API 使用同源 `/api`，图片资源使用同源 `/static`，不依赖写死的本机地址。

后端 API 文档可在 <http://localhost:8080/swagger-ui.html> 查看，OpenAPI JSON 位于 <http://localhost:8080/v3/api-docs>。

## 后端 API 概览

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/detect/upload` | 上传并识别单张图片 |
| `POST` | `/api/detect/batch-upload` | 批量上传并识别 |
| `POST` | `/api/detect/batch-upload-async` | 创建异步批量识别任务，HTTP 202 |
| `GET` | `/api/detect/batch-status/{batchNo}` | 查询批次总进度和逐项状态 |
| `POST` | `/api/detect/batch-cancel/{batchNo}` | 取消尚未完成的异步批次 |
| `POST` | `/api/detect/batch-retry/{batchNo}` | 重试批次中的失败和已取消项目，HTTP 202 |
| `POST` | `/api/detect/camera-upload` | 上传摄像头截图并识别 |
| `GET` | `/api/detect/history` | 分页查询历史记录 |
| `GET` | `/api/detect/{id}` | 查询检测详情 |
| `DELETE` | `/api/detect/{id}` | 删除单条记录 |
| `POST` | `/api/detect/batch-delete` | 按 ID 批量删除 |
| `POST` | `/api/detect/delete-by-condition` | 按筛选条件删除 |
| `GET` | `/api/detect/export/csv` | 导出 CSV |
| `GET` | `/api/detect/export/excel` | 导出 Excel |
| `GET` | `/api/detect/export/images` | 下载原图和结果图 ZIP |
| `GET` | `/actuator/health` | 后端健康检查 |
| `GET` | `/swagger-ui.html` | Swagger API 文档 |

FastAPI 推理服务提供：

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/predict` | 根据共享卷中的图片路径执行推理 |
| `GET` | `/health` | 推理服务健康检查 |

## 数据与模型持久化

Compose 创建两个命名卷：

- `wood-detect-db-data`：保存 MariaDB 数据。
- `wood-detect-uploads`：保存上传原图与推理结果图，并由后端和推理服务共享。

CPU 模式把 `ONNX_MODEL_PATH` 只读挂载到 `/models/best.onnx`；GPU 覆盖配置把 `PYTORCH_MODEL_PATH` 挂载到 `/models/best.pt`。修改对应变量即可切换模型，不需要重新制作镜像。

## 模型训练与评估

统一入口位于 `程序源码/ultralytics-main`：

```bash
python train.py --config configs/train.yaml
python evaluate.py --model runs/detect/best.pt --data yolo-bvn.yaml
python export_onnx.py --model runs/detect/best.pt --imgsz 896 --opset 17
python benchmark.py --models runs/detect/best.pt runs/detect/best.onnx --source path/to/images --device cpu
```

在线推理支持以下实际策略：

- `FAST`：整图 512px 推理，适合快速预览。
- `STANDARD`：先执行整图推理；高分辨率、首轮无结果、低置信度、小目标或仅边缘命中会自动升级为 896px、20% 重叠切片。
- `ACCURATE`：始终执行重叠切片，局部坐标还原到原图后使用按类别 NMS 合并重复框。

自适应或精细模式在模型没有给出有效内部区域时，会对木材色调图片中的封闭暗部和空洞补充 `suspected_anomaly` 候选。结果页会明确提示人工复核，不把该候选冒充模型类别或模型置信度。

每条检测记录会保存实际执行模式、模式选择原因、推理区域数、图片尺寸和端到端推理耗时。恢复带标签验证集后，可在推理容器中运行 `compare_modes.py` 对比三种模式。

模型报告记录了权重哈希、训练参数、类别、检查点历史指标、Wise-IoU 核实结果和 CPU 烟雾基准，详见 `程序源码/ultralytics-main/MODEL_REPORT.md`。仓库缺少原始数据集时，训练和评估入口会明确失败，不会生成伪造指标。

## 可解释质量评分

识别成功后，后端会统计各类别数量，计算检测框矩形并集占图片的比例和最大单框面积比例，并按 `WOOD-QS-1.0` 规则从 100 分中逐项扣分。默认等级为 A（90–100）、B（75–89.99）、C（60–74.99）和 D（低于 60）；权重、面积系数、扣分上限和等级阈值均可通过环境变量调整。

评分结果会保存规则快照并显示每条扣分原因。历史列表支持等级及分数区间筛选，CSV/Excel 包含评分、等级、面积占比、类别统计、扣分明细和规则版本。质量等级仅为本项目内部评价规则，用于相对比较和人工复核参考，不属于行业强制标准。

数据库结构不再依赖仅首次启动执行的初始化 SQL。后端启动时会通过 `src/main/resources/db/migration` 中的 Flyway 脚本检查并升级结构；迁移记录保存在 `flyway_schema_history` 表中。

普通执行 `docker compose down` 不会删除数据。以下命令会永久删除数据库和上传文件卷，请谨慎使用：

```bash
docker compose down -v
```

## 本地开发

### 前端

```bash
cd 程序源码/wood_detect_frontend
npm ci
npm test
npm run dev
```

Vite 开发服务器会把 `/api` 和 `/static` 代理到 `VITE_DEV_BACKEND_URL`，默认目标为 `http://127.0.0.1:8080`。

### Spring Boot 后端

后端使用 Java 17，并提供固定 Maven 版本的 Wrapper。先设置数据库环境变量，再构建或运行：

```powershell
cd 程序源码\wood_detect_backend\wood_backend
$env:DB_USERNAME='wood'
$env:DB_PASSWORD='your_password'
.\mvnw.cmd test
.\mvnw.cmd spring-boot:run
```

Linux/macOS 对应使用 `./mvnw`。配置分为：

- `application.yml`：公共配置和环境变量入口。
- `application-dev.yml`：本地开发连接地址；数据库凭据必须从环境变量传入。
- `application-docker.yml`：Compose 服务名和容器路径。
- `application-prod.yml`：生产环境配置，敏感值必须通过环境变量提供。

### Python 推理服务

```powershell
cd 程序源码\wood_detect_python\wood_detect
$env:MODEL_PATH='..\..\ultralytics-main\runs\detect\best.pt'
$env:UPLOAD_ROOT='.\data\uploads'
python detect.py
```

默认端口为 `8001`，设备配置为 `auto` 时会优先使用可用的 CUDA，否则回退到 CPU。

## 当前开发进度

已经完成：

- 第一阶段工程目录整理与配置环境变量化。
- CPU/GPU Dockerfile 和 Docker Compose 编排。
- Nginx 同源代理、四服务健康检查和持久化卷。
- Windows、Linux、macOS 启停脚本。
- 前端生产构建和依赖漏洞处理。
- Git 与 GitHub 版本管理。
- Flyway V1 至 V5 数据库自动迁移、批次、推理参数、自适应元数据和质量评价字段。
- UUID 文件存储、图片真实性/尺寸校验和删除补偿。
- `PENDING / PROCESSING / SUCCESS / FAIL / CANCELLED` 状态闭环、推理超时与重试。
- HTTP 错误语义、统一错误结构、数据库原生分页和一致筛选条件。
- 异步批量任务、逐项进度、Swagger 文档、Maven Wrapper 和可执行 JAR。
- 后端文件存储单元测试，以及 Docker 下 Flyway、API、万条分页的阶段验收。
- 异步批次进度、取消、失败项重试和单张重新识别前端流程。
- 统一 Axios 异常拦截、加载/空数据/断网/服务不可用状态和失败原因展示。
- 手机/平板响应式布局、键盘焦点、语义标签、减少动效支持和中文缺陷名称。
- 路由懒加载、Element Plus 按需注册和静态图片 WebP 压缩；生产构建无超大资源警告。
- 六类模型训练/评估/导出/基准入口、动态 ONNX CPU 推理和 PyTorch GPU 配置。
- 快速整图、自适应切片和精细切片推理，以及坐标还原、按类别 NMS 和疑似异常复核候选。
- 可解释质量评分、A/B/C/D 等级、扣分原因、历史筛选及 CSV/Excel 评价字段。

后续重点：

- 恢复不可变版本的原始数据集，重新生成混淆矩阵、PR/F1 曲线并独立复算论文指标。
- 实现主动学习与人工复核闭环。
- 补充单元测试、集成测试、端到端测试和跨平台验收。

详细任务、状态标记和验收记录见[项目实现计划与进度](项目实现计划与进度.md)。

## 已知限制

- 当前仓库未包含训练数据集，因此不能直接完整复现模型训练。
- 跨平台配置已经建立，但 Windows、Linux、macOS 和移动浏览器仍需完成正式验收矩阵。
- 现有指标来自 `best.pt` 检查点记录；因验证集缺失，尚不能独立复算混淆矩阵、PR/F1 曲线和论文指标。
- FP16 仅适用于 CUDA 推理环境；CPU 模式请选择 AUTO 或 FP32。

## 许可证说明

仓库内嵌的 Ultralytics 源码遵循其目录中的 AGPL-3.0 许可证。部署、修改或分发本项目之前，请评估并遵守相关开源许可证要求。

本仓库的其他业务代码目前尚未单独声明许可证；在明确许可之前，请勿将其视为可自由再分发的软件包。
