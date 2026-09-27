# Wood — 木材表面缺陷检测系统

Wood 是一个面向木材表面质量检查场景的全栈缺陷检测系统。用户可以通过浏览器上传单张或多张木材图片，也可以调用摄像头拍照识别；系统使用 YOLO 模型完成推理，保存原图、检测结果图与缺陷框明细，并提供历史查询、筛选、删除和报表导出功能。

项目采用前后端分离架构，默认提供无需 CUDA 的 CPU 容器方案，同时保留 NVIDIA GPU 推理方案。Windows、Linux 和 macOS 可使用 Docker Compose 部署，手机和平板可作为浏览器客户端访问。

> 当前默认部署为新训练的 10 类模型（162 轮训练中的第 161 轮最佳权重），不含髓心破坏、虫蛀和霉变。检查点验证 mAP50=72.90%、mAP50–95=51.08%，不是本次独立复评结果。完整进度见[项目实现计划与进度](项目实现计划与进度.md)。

## 主要功能

- 单张图片上传识别，并展示带检测框的结果图。
- 多张图片同步识别，以及带总进度和逐项状态的异步批量任务。
- 支持取消异步批次、重试失败/取消项目，以及单张重新识别。
- 支持快速整图、自适应和精细切片三种模式；自适应模式会根据图片尺寸与首轮结果决定是否执行重叠切片，首轮结果仅位于图片边缘时也会复查整幅图片。
- 基于缺陷类别数量、去重覆盖面积和最大缺陷面积生成 0–100 分与 A/B/C/D 级评价，并逐项展示扣分原因；该等级是可配置的项目内部规则，不是行业强制标准。
- 低置信度记录自动进入复核队列；用户可确认、改类、改框、删除误检框或补充漏检框，并一键导出已复核 YOLO 数据集。
- 自适应/精细模式用真实局部切片、对比度增强和灰度裂纹复查补检，所有结果遵守请求阈值，不再生成“疑似异常”类别或强行归类。
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

当前模型识别以下 10 类木材表面缺陷：

| 类别标识 | 中文含义 |
|---|---|
| `dry_knot` | 干节 |
| `sound_knot` | 健全节 |
| `edge_knot` | 边节 |
| `small_knot` | 小节 |
| `split` | 裂纹 |
| `wave` | 波纹 |
| `decay` | 腐朽/腐烂 |
| `large_hole` | 大型空洞/树洞 |
| `bark_pocket` | 树皮脱落/夹皮 |
| `stain` | 颜色异常/污渍 |

旧版 `suspected_anomaly` 只在历史记录兼容逻辑中保留。最终优化没有训练、修改或替换权重；重新识别使用新推理流程（版本后缀 `-mv1`）。局部复查只保留模型真实框和置信度，所有结果遵守请求阈值，新增增强视图结果至少达到 0.35。连续裂纹可在模型检出后沿细暗线补全框，类别和置信度保持模型输出。快速模式仍为单次整图推理。每次识别生成独立结果文件，避免覆盖历史结果或被浏览器缓存旧图。

最后一轮优化的 GitHub 参考、固定样本对比、网页验收与使用限制见[推理优化报告](程序源码/deploy/inference-final-optimization-20260927.md)。

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

> 注意：脚本和 `docker-compose.yml` 都在 `程序源码` 目录下，请先 `cd 程序源码` 再执行下面的命令。
> 也可以在任意目录用绝对路径调用：`D:\wood_detection\wood\程序源码\scripts\start.ps1`（脚本会自动切换到项目根目录）。

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
| `FRONTEND_BIND_HOST` | `0.0.0.0` | 前端监听地址，允许局域网设备访问 |
| `BACKEND_BIND_HOST` / `PYTHON_BIND_HOST` / `DB_BIND_HOST` | `127.0.0.1` | 内部调试端口仅监听本机；不要无必要暴露到局域网或公网 |
| `DB_NAME` | `wood_detect` | 数据库名称 |
| `DB_USERNAME` | `wood` | 数据库业务用户 |
| `DB_PASSWORD` | `wood_change_me` | 数据库业务用户密码 |
| `DB_ROOT_PASSWORD` | `root_change_me` | 数据库 root 密码 |
| `ONNX_MODEL_PATH` | `./ultralytics-main/runs/detect/best.onnx` | CPU 推理模型路径 |
| `PYTORCH_MODEL_PATH` | `./ultralytics-main/runs/detect/best.pt` | GPU 推理模型路径 |
| `MODEL_DEVICE` | `0` | GPU 设备编号 |
| `CONFIDENCE_THRESHOLD` | `0.25` | 检测置信度阈值 |
| `IMAGE_SIZE` | `640` | 模型输入尺寸 |
| `MAX_CONCURRENT_INFERENCES` | `1` | 每个推理服务进程允许的并发推理数 |
| `INFERENCE_ACQUIRE_TIMEOUT_SECONDS` | `5` | 等待推理并发槽的最长秒数，超时返回 503 |
| `TILE_IMAGE_SIZE` | `896` | 局部模型输入尺寸（与原图裁剪尺寸分离） |
| `TILE_WINDOW_SIZE` | `640` | 小图局部窗口上限，实际窗口按短边的 78% 对齐到 32 像素 |
| `MAX_TILE_COUNT` | `24` | 每种视图的切片数上限，超出时扩大窗口保持覆盖 |
| `ENHANCED_REVIEW_ENABLED` | `true` | 对比度增强及灰度裂纹复查 |
| `CRACK_TRACE_ENABLED` | `true` | 模型检出裂纹后的连续暗线补全 |
| `TILE_OVERLAP` | `0.20` | 相邻切片重叠比例 |
| `NMS_IOU_THRESHOLD` | `0.50` | 跨切片重复框合并阈值 |
| `AUTO_MAX_DIMENSION` | `2560` | 自适应模式触发切片的最长边阈值 |
| `AUTO_PIXEL_COUNT` | `4000000` | 自适应模式触发切片的像素数阈值 |
| `AUTO_EDGE_MARGIN_RATIO` | `0.02` | 判断首轮结果是否仅位于图片边缘的边距比例 |
| `ANOMALY_FALLBACK_ENABLED` | `true` | 是否启用暗部区域的模型最高概率类别复查 |
| `ANOMALY_MIN_WOOD_RATIO` | `0.30` | 启用补充候选所需的最小木材色调比例 |
| `ANOMALY_MIN_COMPONENT_RATIO` | `0.001` | 局部复查区域最小面积比例 |
| `ANOMALY_MAX_COMPONENT_RATIO` | `0.15` | 局部复查区域最大面积比例 |
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
| `MODEL_VERSION` | 自动生成 | 可选的模型版本名；留空时使用“权重文件名-SHA256 前 12 位” |
| `ACTIVE_LEARNING_LOW_CONFIDENCE_THRESHOLD` | `0.45` | 低于该值的模型检测自动进入待复核队列 |

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

`/predict` 只接受 `UPLOAD_ROOT` 内的真实文件路径，会拒绝路径穿越和符号链接逃逸；校验失败、服务繁忙和内部错误均返回统一的 `success/code/message` JSON。默认 Compose 只把推理、后端和数据库调试端口绑定到 `127.0.0.1`，移动设备应通过前端统一入口访问。

## 数据与模型持久化

Compose 创建两个命名卷：

- `wood-detect-db-data`：保存 MariaDB 数据。
- `wood-detect-uploads`：保存上传原图与推理结果图，并由后端和推理服务共享。

CPU 模式把 `ONNX_MODEL_PATH` 只读挂载到 `/models/best.onnx`；GPU 覆盖配置把 `PYTORCH_MODEL_PATH` 挂载到 `/models/best.pt`。修改对应变量即可切换模型，不需要重新制作镜像。

## 模型训练与评估

统一入口位于 `程序源码/ultralytics-main`：

```bash
python train.py --config configs/train-10class.yaml
python evaluate.py --model runs/detect/wood-yolov8s-c2fpsa-10class/weights/best.pt --data yolo-bvn-10class.yaml
python export_onnx.py --model runs/detect/wood-yolov8s-c2fpsa-10class/weights/best.pt --imgsz 896 --opset 17
python benchmark.py --models runs/detect/wood-yolov8s-c2fpsa-10class/weights/best.pt runs/detect/wood-yolov8s-c2fpsa-10class/weights/best.onnx --source path/to/images --device cpu
```

在线推理支持以下实际策略：

- `FAST`：整图 512px 推理，适合快速预览。
- `STANDARD`：先执行整图推理；高分辨率、首轮无结果、低置信度、小目标或仅边缘命中会自动升级为重叠切片，并用灰度局部视图复查裂纹。小图也会真实裁剪，而非仅放大整图。
- `ACCURATE`：始终保留整图与重叠切片检测，再执行增强复查；小图增加短边 67% 窗口的第二轮灰度裂纹检查，新增结果至少为 0.45。局部坐标还原到原图后使用按类别 NMS 合并重复框。

自适应和精细模式对明显暗部进行内部区域定位，再由原模型按请求阈值复查。区域定位本身不生成公开结果；不再使用 `conf=0`、最高概率强制归类或把模型小框替换成整个候选区域。灰度增强仅补充裂纹类，局部铺满三条裁剪边界的大框会被过滤。

每条检测记录会保存实际执行模式、模式选择原因、推理区域数、图片尺寸和端到端推理耗时。恢复带标签验证集后，可在推理容器中运行 `compare_modes.py` 对比三种模式。

模型报告记录了权重哈希、训练参数、类别、检查点历史指标、Wise-IoU 核实结果和 CPU 烟雾基准，详见 `程序源码/ultralytics-main/MODEL_REPORT.md`。本次 GitHub 运行版包含默认 PT/ONNX 权重，不包含训练图片和标注；克隆后可直接运行系统，只有重新训练或完整复评时才需要另行准备 10 类数据集。

## 可解释质量评分

识别成功后，后端会统计各类别数量，计算检测框矩形并集占图片的比例和最大单框面积比例，并按 `WOOD-QS-1.0` 规则从 100 分中逐项扣分。默认等级为 A（90–100）、B（75–89.99）、C（60–74.99）和 D（低于 60）；权重、面积系数、扣分上限和等级阈值均可通过环境变量调整。

评分结果会保存规则快照并显示每条扣分原因。历史列表支持等级及分数区间筛选，CSV/Excel 包含评分、等级、面积占比、类别统计、扣分明细和规则版本。质量等级仅为本项目内部评价规则，用于相对比较和人工复核参考，不属于行业强制标准。

## 主动学习与人工复核

系统按以下流程保留可追溯的数据闭环：

1. 推理服务根据模型权重 SHA-256 生成稳定版本号，后端保存原始模型框、最低置信度和模型版本。
2. 低置信度检测自动进入历史页“待复核”队列（含局部兜底归类后的具体缺陷；旧版异常记录保留兼容）。
3. 在记录详情中确认结果、修正类别和坐标、删除误检框或补充漏检目标；人工标注保存到独立表，不覆盖原始模型结果。
4. 历史页可将已复核记录导出为包含 `images/train`、`labels/train`、`data.yaml` 和 `manifest.json` 的 YOLO ZIP 数据包。
5. 使用现有 `train.py`、`evaluate.py` 和 `export_onnx.py` 完成再训练、独立验证和部署；新权重上线后，版本看板对比人工确认率、纠错率、平均质量分和推理耗时。

未复核记录不会进入 YOLO 导出包；标记为结果错误且无补充框的图片会作为空标签负样本。训练前仍需划分独立验证集，不能使用训练目录评价模型。

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
$env:UPLOAD_PATH='..\..\data\uploads'
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
$env:UPLOAD_ROOT='..\..\data\uploads'
python detect.py
```

默认端口为 `8001`，设备配置为 `auto` 时会优先使用可用的 CUDA，否则回退到 CPU。后端的 `UPLOAD_PATH` 与推理服务的 `UPLOAD_ROOT` 必须解析到同一目录；按上述两个子项目目录启动时，默认都会指向 `程序源码/data/uploads`。

### 自动化检查与容器冒烟测试

```powershell
cd 程序源码
python -m unittest discover -s wood_detect_python\wood_detect -p "test_*.py" -v
python .\scripts\smoke_test.py
```

冒烟脚本会检查前端、后端/数据库、推理服务、推理路径边界和静态资源 404 语义。GitHub Actions 还会自动运行后端测试、前端测试与构建、Python 测试、依赖漏洞检查和 Compose 配置校验。

## 当前开发进度

已经完成：

- 第一阶段工程目录整理与配置环境变量化。
- CPU/GPU Dockerfile 和 Docker Compose 编排。
- Nginx 同源代理、四服务健康检查和持久化卷。
- Windows、Linux、macOS 启停脚本。
- 前端生产构建和依赖漏洞处理。
- Git 与 GitHub 版本管理。
- Flyway V1 至 V6 数据库自动迁移、批次、推理参数、自适应元数据、质量评价和人工复核字段。
- UUID 文件存储、图片真实性/尺寸校验和删除补偿。
- `PENDING / PROCESSING / SUCCESS / FAIL / CANCELLED` 状态闭环、推理超时与重试。
- HTTP 错误语义、统一错误结构、数据库原生分页和一致筛选条件。
- 异步批量任务、逐项进度、Swagger 文档、Maven Wrapper 和可执行 JAR。
- 后端文件存储单元测试，以及 Docker 下 Flyway、API、万条分页的阶段验收。
- 异步批次进度、取消、失败项重试和单张重新识别前端流程。
- 统一 Axios 异常拦截、加载/空数据/断网/服务不可用状态和失败原因展示。
- 手机/平板响应式布局、键盘焦点、语义标签、减少动效支持和中文缺陷名称。
- 路由懒加载、Element Plus 按需注册和静态图片 WebP 压缩；生产构建无超大资源警告。
- 十类模型训练/评估/导出/基准入口、动态 ONNX CPU 推理和 PyTorch GPU 配置。
- 快速整图、自适应补检和精细补检，以及坐标还原、按类别 NMS 和遵守阈值的多视图复查。
- 可解释质量评分、A/B/C/D 等级、扣分原因、历史筛选及 CSV/Excel 评价字段。
- 主动学习复核队列、人工框修正、YOLO 数据回流、模型哈希版本和版本指标对比。
- 推理并发保护、上传目录边界校验、统一错误响应、Docker 冒烟脚本和 GitHub Actions 持续集成。

后续重点：

- 使用本地留存的数据集重新生成混淆矩阵、PR/F1 曲线并独立复算论文指标。
- 使用专家复核样本执行真实再训练，并对比新旧模型的独立验证集指标。
- 补充单元测试、集成测试、端到端测试和跨平台验收。

详细任务、状态标记和验收记录见[项目实现计划与进度](项目实现计划与进度.md)。

## 已知限制

- 训练图片和标注未包含在本次运行版提交中；这不影响识别服务，但不能只靠本仓库重新训练或完整复评。
- 跨平台配置已经建立，但 Windows、Linux、macOS 和移动浏览器仍需完成正式验收矩阵。
- 现有指标来自 `best.pt` 检查点记录；虽然验证数据已恢复，但尚未重新执行评估，不能把检查点历史值当作本次独立复评结果。
- FP16 仅适用于 CUDA 推理环境；CPU 模式请选择 AUTO 或 FP32。

## 许可证说明

仓库内嵌的 Ultralytics 源码遵循其目录中的 AGPL-3.0 许可证。部署、修改或分发本项目之前，请评估并遵守相关开源许可证要求。

本仓库的其他业务代码目前尚未单独声明许可证；在明确许可之前，请勿将其视为可自由再分发的软件包。
