from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from ultralytics import YOLO
from pathlib import Path
from typing import List, Literal, Mapping, Union
import hashlib
import cv2
import torch
import os
import logging

from inference_pipeline import (
    AUTO_CONFIDENCE_THRESHOLD,
    AUTO_MAX_DIMENSION,
    AUTO_PIXEL_COUNT,
    NMS_IOU_THRESHOLD,
    TILE_IMAGE_SIZE,
    TILE_OVERLAP,
    SUSPECTED_ANOMALY_CLASS_ID,
    SUSPECTED_ANOMALY_CLASS_NAME,
    Detection,
    run_inference,
)
from service_runtime import InferenceBusyError, InferenceGate, InputImageError, resolve_input_image

logger = logging.getLogger("wood-detect-inference")

# =========================
# 1. FastAPI 应用
app = FastAPI(title="Wood Defect Detection Service")

# =========================
# 2. 配置区域（Docker 和本地开发均通过环境变量覆盖）
MODEL_PATH = Path(os.getenv("MODEL_PATH", "../../ultralytics-main/runs/detect/best.pt")).expanduser().resolve()
UPLOAD_ROOT = Path(os.getenv("UPLOAD_ROOT", "../../data/uploads")).expanduser().resolve()
ACCESS_URL_PREFIX = os.getenv("ACCESS_URL_PREFIX", "/static/")
MODEL_DEVICE = os.getenv("MODEL_DEVICE", "auto").strip().lower()
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.25"))
IMAGE_SIZE = int(os.getenv("IMAGE_SIZE", "640"))
MAX_CONCURRENT_INFERENCES = int(os.getenv("MAX_CONCURRENT_INFERENCES", "1"))
INFERENCE_ACQUIRE_TIMEOUT_SECONDS = float(os.getenv("INFERENCE_ACQUIRE_TIMEOUT_SECONDS", "5"))

# 结果图保存目录
RESULT_DIR = UPLOAD_ROOT / "result"
RESULT_DIR.mkdir(parents=True, exist_ok=True)

# =========================
# 3. 启动时加载模型
# =========================
if not MODEL_PATH.is_file():
    raise RuntimeError(f"模型文件不存在: {MODEL_PATH}")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as model_file:
        for chunk in iter(lambda: model_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


MODEL_SHA256 = file_sha256(MODEL_PATH)
configured_model_version = os.getenv("MODEL_VERSION", "").strip()
MODEL_VERSION = configured_model_version or f"{MODEL_PATH.stem}-{MODEL_SHA256[:12]}"

model = YOLO(str(MODEL_PATH))
inference_gate = InferenceGate(MAX_CONCURRENT_INFERENCES, INFERENCE_ACQUIRE_TIMEOUT_SECONDS)


def normalize_model_names(names: Mapping[int | str, str] | List[str]) -> dict[int, str]:
    """将 PyTorch/ONNX 模型元数据中的类别统一为整数键字典。"""
    if isinstance(names, Mapping):
        return {int(class_id): str(name) for class_id, name in names.items()}
    return {class_id: str(name) for class_id, name in enumerate(names)}


# =========================
# 4. 请求 / 响应模型
# =========================
class PredictRequest(BaseModel):
    imagePath: str
    modelMode: Literal["FAST", "STANDARD", "ACCURATE"] = "STANDARD"
    confidenceThreshold: float = Field(default=CONFIDENCE_THRESHOLD, ge=0.05, le=0.95)
    precision: Literal["AUTO", "FP32", "FP16"] = "AUTO"


class DetectItem(BaseModel):
    className: str
    confidence: float
    x1: int
    y1: int
    x2: int
    y2: int


class PredictResponse(BaseModel):
    success: bool
    resultImagePath: str
    resultImageUrl: str
    totalCount: int
    modelVersion: str
    actualMode: str
    decisionReason: str
    inferenceDurationMs: int
    tileCount: int
    imageWidth: int
    imageHeight: int
    details: List[DetectItem]


def error_payload(code: str, message: str) -> dict[str, object]:
    return {"success": False, "code": code, "message": message}


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    field_candidates = {
        ".".join(part for part in error["loc"] if isinstance(part, str) and part != "body")
        for error in exc.errors()
    }
    fields = sorted(field for field in field_candidates if field)
    suffix = f"：{', '.join(fields)}" if fields else ""
    return JSONResponse(status_code=422, content=error_payload("VALIDATION_ERROR", f"请求参数校验失败{suffix}"))


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    if exc.status_code == 503:
        code = "INFERENCE_BUSY"
    elif exc.status_code == 404:
        code = "NOT_FOUND"
    elif exc.status_code < 500:
        code = "BAD_REQUEST"
    else:
        code = "INFERENCE_ERROR"
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(code, str(exc.detail)),
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception):
    logger.exception("未处理的推理服务异常", exc_info=exc)
    return JSONResponse(status_code=500, content=error_payload("INTERNAL_ERROR", "推理服务内部错误"))


# =========================
# 5. 工具函数
# =========================
def build_result_filename(image_path: Path) -> str:
    """
    保持结果图文件名与原图一致
    例如 abc.jpg -> abc.jpg
    """
    return image_path.name


def build_result_image_url(filename: str) -> str:
    """
    构造返回给 Spring Boot / 前端的结果图访问 URL
    例如 /static/result/abc_result.jpg
    """
    prefix = ACCESS_URL_PREFIX
    if not prefix.endswith("/"):
        prefix += "/"
    return f"{prefix}result/{filename}"


def resolve_device() -> Union[int, str]:
    """根据配置选择推理设备，默认优先使用 CUDA。"""
    if MODEL_DEVICE == "auto":
        return 0 if torch.cuda.is_available() else "cpu"
    if MODEL_DEVICE == "cpu":
        return "cpu"
    if MODEL_DEVICE.isdigit():
        return int(MODEL_DEVICE)
    return MODEL_DEVICE


def resolve_half_precision(precision: str, device: Union[int, str]) -> bool:
    """AUTO 在 CUDA 上使用 FP16，在 CPU 上保持 FP32。"""
    using_cuda = device != "cpu"
    if precision == "FP16" and not using_cuda:
        raise HTTPException(status_code=400, detail="FP16 仅可在 CUDA 推理设备上使用")
    if precision == "FP32":
        return False
    return using_cuda


# =========================
# 6. 健康检查接口
# =========================
@app.get("/health")
def health():
    try:
        class_names = normalize_model_names(model.names)
    except (AttributeError, TypeError, ValueError):
        class_names = {}
    return {
        "success": True,
        "message": "Python detection service is running",
        "model": MODEL_PATH.name,
        "modelVersion": MODEL_VERSION,
        "modelSha256": MODEL_SHA256,
        "device": str(resolve_device()),
        "backend": MODEL_PATH.suffix.lower().lstrip("."),
        "classNames": class_names,
        "concurrency": {
            "maxConcurrentInferences": MAX_CONCURRENT_INFERENCES,
            "acquireTimeoutSeconds": INFERENCE_ACQUIRE_TIMEOUT_SECONDS,
        },
        "adaptiveInference": {
            "tileSize": TILE_IMAGE_SIZE,
            "tileOverlap": TILE_OVERLAP,
            "nmsIouThreshold": NMS_IOU_THRESHOLD,
            "autoMaxDimension": AUTO_MAX_DIMENSION,
            "autoPixelCount": AUTO_PIXEL_COUNT,
            "autoConfidenceThreshold": AUTO_CONFIDENCE_THRESHOLD,
        },
    }


# =========================
# 7. 推理接口
# =========================
@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    try:
        image_path = resolve_input_image(req.imagePath, UPLOAD_ROOT)
    except InputImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        with inference_gate.slot():
            return run_prediction(req, image_path)
    except InferenceBusyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def run_prediction(req: PredictRequest, image_path: Path) -> PredictResponse:

    # 2. 读取图片
    image = cv2.imread(str(image_path))
    if image is None:
        raise HTTPException(status_code=400, detail="图片读取失败或格式不受支持")

    # 3. YOLO 推理。STANDARD 可根据分辨率或首轮结果自动升级到重叠切片。
    try:
        device = resolve_device()

        def predict_region(region, image_size):
            results = model.predict(
                source=region,
                save=False,
                conf=req.confidenceThreshold,
                imgsz=image_size,
                device=device,
                half=resolve_half_precision(req.precision, device),
                verbose=False,
            )
            if not results:
                raise RuntimeError("模型未返回结果")
            result = results[0]
            detections = []
            if result.boxes is not None and len(result.boxes) > 0:
                for xyxy, confidence, class_id in zip(
                    result.boxes.xyxy.cpu().numpy(),
                    result.boxes.conf.cpu().numpy(),
                    result.boxes.cls.cpu().numpy(),
                ):
                    detections.append(
                        Detection(
                            class_id=int(class_id),
                            confidence=float(confidence),
                            x1=float(xyxy[0]),
                            y1=float(xyxy[1]),
                            x2=float(xyxy[2]),
                            y2=float(xyxy[3]),
                        )
                    )
            return detections, normalize_model_names(result.names)

        outcome = run_inference(image, req.modelMode, predict_region, IMAGE_SIZE)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("模型推理失败, image=%s", image_path.name)
        raise HTTPException(status_code=500, detail="模型推理失败") from exc

    class_names = {
        **normalize_model_names(model.names),
        SUSPECTED_ANOMALY_CLASS_ID: SUSPECTED_ANOMALY_CLASS_NAME,
    }

    # 4. 提取检测框明细
    details = []
    for item in outcome.detections:
        details.append(
            DetectItem(
                className=class_names.get(item.class_id, str(item.class_id)),
                confidence=round(item.confidence, 4),
                x1=round(item.x1),
                y1=round(item.y1),
                x2=round(item.x2),
                y2=round(item.y2),
            )
        )

    # 5. 生成带框结果图
    plotted_image = outcome.plotted_image

    # 6. 保存结果图
    result_filename = build_result_filename(image_path)
    result_image_path = RESULT_DIR / result_filename

    success = cv2.imwrite(str(result_image_path), plotted_image)
    if not success:
        raise HTTPException(status_code=500, detail="结果图保存失败")

    # 7. 构造返回
    return PredictResponse(
        success=True,
        resultImagePath=str(result_image_path).replace("\\", "/"),
        resultImageUrl=build_result_image_url(result_filename),
        totalCount=sum(item.class_id != SUSPECTED_ANOMALY_CLASS_ID for item in outcome.detections),
        modelVersion=MODEL_VERSION,
        actualMode=outcome.actual_mode,
        decisionReason=outcome.decision_reason,
        inferenceDurationMs=outcome.duration_ms,
        tileCount=outcome.tile_count,
        imageWidth=outcome.image_width,
        imageHeight=outcome.image_height,
        details=details
    )

# 关键：添加直接运行的启动代码
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "detect:app",
        host=os.getenv("PYTHON_HOST", "0.0.0.0"),
        port=int(os.getenv("PYTHON_PORT", "8001")),
        reload=os.getenv("PYTHON_RELOAD", "false").lower() == "true"
    )
