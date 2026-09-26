"""Docker Compose 启动后的无第三方依赖冒烟测试。"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    env_file = PROJECT_ROOT / ".env"
    if env_file.is_file():
        for raw_line in env_file.read_text(encoding="utf-8-sig").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def request_json(url: str, *, expected_status: int = 200, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            status = response.status
            body = response.read()
    except urllib.error.HTTPError as error:
        status = error.code
        body = error.read()
    if status != expected_status:
        raise RuntimeError(f"{url} 期望 HTTP {expected_status}，实际为 {status}: {body[:300]!r}")
    return json.loads(body.decode("utf-8"))


def request_text(url: str, *, expected_status: int = 200) -> str:
    with urllib.request.urlopen(url, timeout=10) as response:
        if response.status != expected_status:
            raise RuntimeError(f"{url} 期望 HTTP {expected_status}，实际为 {response.status}")
        return response.read().decode("utf-8").strip()


def main() -> int:
    values = load_env()
    frontend_port = os.getenv("FRONTEND_PORT", values.get("FRONTEND_PORT", "8088"))
    backend_port = os.getenv("BACKEND_PORT", values.get("BACKEND_PORT", "8080"))
    python_port = os.getenv("PYTHON_PORT", values.get("PYTHON_PORT", "8001"))

    frontend = request_text(f"http://127.0.0.1:{frontend_port}/health")
    backend = request_json(f"http://127.0.0.1:{backend_port}/actuator/health")
    inference = request_json(f"http://127.0.0.1:{python_port}/health")
    escaped = request_json(
        f"http://127.0.0.1:{python_port}/predict",
        expected_status=400,
        payload={"imagePath": "/etc/passwd"},
    )
    missing = request_json(
        f"http://127.0.0.1:{frontend_port}/static/__smoke_missing__.jpg",
        expected_status=404,
    )

    if frontend != "ok":
        raise RuntimeError(f"前端健康检查响应异常: {frontend}")
    if backend.get("status") != "UP":
        raise RuntimeError(f"后端健康检查响应异常: {backend}")
    if inference.get("success") is not True:
        raise RuntimeError(f"推理健康检查响应异常: {inference}")
    if escaped.get("code") != "BAD_REQUEST" or escaped.get("success") is not False:
        raise RuntimeError(f"推理路径边界检查响应异常: {escaped}")
    if missing.get("code") != 404:
        raise RuntimeError(f"静态资源 404 响应异常: {missing}")

    print("PASS frontend, backend/database, inference, path-boundary, static-404")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        raise SystemExit(1)
