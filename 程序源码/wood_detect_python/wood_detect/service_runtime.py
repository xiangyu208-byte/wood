"""推理 API 的运行时安全与并发控制工具。"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from threading import BoundedSemaphore
from typing import Iterator


class InputImageError(ValueError):
    """请求图片不存在、不是普通文件或越过上传目录。"""


class InferenceBusyError(RuntimeError):
    """推理并发槽在限定时间内不可用。"""


def resolve_input_image(raw_path: str, upload_root: Path) -> Path:
    """只允许读取上传根目录内真实存在的普通文件，并阻止路径穿越与符号链接逃逸。"""
    if not raw_path or not raw_path.strip():
        raise InputImageError("图片路径不能为空")

    root = upload_root.expanduser().resolve()
    try:
        image_path = Path(raw_path).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise InputImageError("图片不存在或无法访问") from exc

    try:
        image_path.relative_to(root)
    except ValueError as exc:
        raise InputImageError("图片必须位于上传目录内") from exc

    if not image_path.is_file():
        raise InputImageError("图片路径不是普通文件")
    return image_path


class InferenceGate:
    """限制单进程并发推理数量，避免 CPU/GPU 内存被并发请求耗尽。"""

    def __init__(self, max_concurrency: int, acquire_timeout_seconds: float):
        if max_concurrency < 1:
            raise ValueError("max_concurrency 必须大于等于 1")
        if acquire_timeout_seconds < 0:
            raise ValueError("acquire_timeout_seconds 不能小于 0")
        self.max_concurrency = max_concurrency
        self.acquire_timeout_seconds = acquire_timeout_seconds
        self._semaphore = BoundedSemaphore(max_concurrency)

    @contextmanager
    def slot(self) -> Iterator[None]:
        acquired = self._semaphore.acquire(timeout=self.acquire_timeout_seconds)
        if not acquired:
            raise InferenceBusyError("推理服务繁忙，请稍后重试")
        try:
            yield
        finally:
            self._semaphore.release()
