from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from ultralytics import YOLO
from pathlib import Path
from typing import List, Literal, Mapping, Union
import cv2
import torch
import os

# =========================
# 1. FastAPI 应用
app = FastAPI(title="Wood Defect Detection Service")

# =========================
# 2. 配置区域（Docker 和本地开发均通过环境变量覆盖）
MODEL_PATH = Path(os.getenv("MODEL_PATH", "../../ultralytics-main/runs/detect/best.pt")).expanduser().resolve()
UPLOAD_ROOT = Path(os.getenv("UPLOAD_ROOT", "./data/uploads")).expanduser().resolve()
ACCESS_URL_PREFIX = os.getenv("ACCESS_URL_PREFIX", "/static/")
MODEL_DEVICE = os.getenv("MODEL_DEVICE", "auto").strip().lower()
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.25"))
IMAGE_SIZE = int(os.getenv("IMAGE_SIZE", "640"))

# 结果图保存目录
RESULT_DIR = UPLOAD_ROOT / "result"
RESULT_DIR.mkdir(parents=True, exist_ok=True)

# =========================
# 3. 启动时加载模型
# =========================
if not MODEL_PATH.is_file():
    raise RuntimeError(f"模型文件不存在: {MODEL_PATH}")

model = YOLO(str(MODEL_PATH))


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
    details: List[DetectItem]


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


def resolve_inference_size(mode: str) -> int:
    """将前端可理解的模式映射为实际推理尺寸。"""
    return {
        "FAST": 512,
        "STANDARD": IMAGE_SIZE,
        "ACCURATE": 960,
    }[mode]


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
        "device": str(resolve_device()),
        "backend": MODEL_PATH.suffix.lower().lstrip("."),
        "classNames": class_names,
    }


# =========================
# 7. 推理接口
# =========================
@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    image_path = Path(req.imagePath)

    # 1. 检查图片是否存在
    if not image_path.exists():
        raise HTTPException(status_code=400, detail=f"图片不存在: {req.imagePath}")

    # 2. 读取图片
    image = cv2.imread(str(image_path))
    if image is None:
        raise HTTPException(status_code=400, detail=f"图片读取失败: {req.imagePath}")

    # 3. YOLO 推理
    try:
        device = resolve_device()
        results = model.predict(
            source=str(image_path),
            save=False,
            conf=req.confidenceThreshold,
            imgsz=resolve_inference_size(req.modelMode),
            device=device,
            half=resolve_half_precision(req.precision, device)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"模型推理失败: {str(e)}")

    if not results or len(results) == 0:
        raise HTTPException(status_code=500, detail="模型未返回结果")

    result = results[0]
    class_names = normalize_model_names(result.names)

    # 4. 提取检测框明细
    details = []
    boxes = result.boxes

    if boxes is not None and len(boxes) > 0:
        xyxy_list = boxes.xyxy.cpu().numpy()
        conf_list = boxes.conf.cpu().numpy()
        cls_list = boxes.cls.cpu().numpy()

        for xyxy, conf, cls_id in zip(xyxy_list, conf_list, cls_list):
            x1, y1, x2, y2 = map(int, xyxy.tolist())
            cls_id = int(cls_id)

            class_name = class_names.get(cls_id, str(cls_id))

            details.append(
                DetectItem(
                    className=class_name,
                    confidence=round(float(conf), 4),
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2
                )
            )

    # 5. 生成带框结果图
    plotted_image = result.plot()

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
        totalCount=len(details),
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
