# Wood Detect Frontend

木材表面缺陷检测系统的 Vue 3 客户端。页面覆盖批量图片检测、摄像头采集、历史筛选和检测详情，并通过 Nginx 同源访问 Spring Boot 的 `/api` 与图片资源 `/static`。

## 已实现能力

- 异步批量上传，总进度与逐张 `PENDING / PROCESSING / SUCCESS / FAIL / CANCELLED` 状态。
- 批次取消、失败项重试、单张重新识别。
- 快速、标准、精确三种模型模式，置信度阈值和 AUTO/FP32/FP16 精度设置。
- 摄像头拍照、重拍、重新识别和权限错误提示。
- 历史记录筛选、分页、删除及 CSV、Excel、图片 ZIP 导出。
- 统一 Axios 响应拦截，区分业务错误、超时、网络中断、服务离线和服务器错误。
- 中文缺陷类别与百分比置信度显示。
- 桌面、平板和手机响应式布局；移动端历史表格自动转为记录条目。
- 跳转主内容、语义状态、键盘焦点、44px 触控目标和减少动效支持。
- 路由懒加载、Element Plus 按需注册和 WebP 静态资源。

## 开发命令

要求 Node.js `20.19+` 或 `22.12+`。

```bash
npm ci
npm run dev
```

默认访问 <http://localhost:5173>。开发服务器会把 `/api` 与 `/static` 代理到 `VITE_DEV_BACKEND_URL`，默认值为 `http://127.0.0.1:8080`。

运行状态工具单元测试：

```bash
npm test
```

执行生产构建与本地预览：

```bash
npm run build
npm run preview
```

构建产物位于 `dist/`。项目使用 HTML5 History 路由，生产 Nginx 已通过 `try_files $uri $uri/ /index.html` 支持任意路由直接刷新。

## 目录说明

```text
src/
├─ api/detect.js              Axios 实例、统一错误与检测 API
├─ components/
│  ├─ DetectionSettings.vue   渐进式推理参数
│  ├─ ResultDetails.vue       图片、参数和缺陷明细
│  ├─ StatePanel.vue          加载、空数据和错误状态
│  └─ StatusBadge.vue         业务状态语义
├─ router/index.js            懒加载路由
├─ utils/detection.js         状态、类别和置信度格式
└─ views/                     检测、摄像头、历史与详情页面
```

## 接口约定

Axios 拦截器返回后端统一响应体，页面从 `payload.data` 读取业务数据。异常会转换为带 `kind` 的 `ApiError`：

| `kind` | 含义 |
|---|---|
| `business` | HTTP 成功但业务响应失败 |
| `timeout` | 请求超过客户端超时 |
| `offline` | 浏览器无法建立连接 |
| `service` | 后端返回 503，通常为推理服务不可用 |
| `server` | 其他 5xx 错误 |
| `request` | 参数或其他请求错误 |
| `cancelled` | 用户主动取消等待 |

异步批量流程使用：

1. `POST /api/detect/batch-upload-async` 创建任务。
2. `GET /api/detect/batch-status/{batchNo}` 轮询进度。
3. 终态后读取成功记录详情。
4. 可调用 `batch-cancel` 或 `batch-retry` 取消与重试。

## 设计与可访问性

项目根目录的 `PRODUCT.md` 和 `DESIGN.md` 记录产品原则与视觉规范。界面不依赖颜色表达状态；关键状态均提供中文文字，移动端保留完整操作能力。建议使用 Chrome、Edge、Firefox 或 Safari 的当前稳定版本。
