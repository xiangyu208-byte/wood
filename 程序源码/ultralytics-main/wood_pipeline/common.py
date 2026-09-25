from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping

import yaml


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_NAMES = (
    "dry_knot",
    "sound_knot",
    "edge_knot",
    "small_knot",
    "split",
    "wave",
)


def resolve_project_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def load_yaml(path: str | Path) -> dict[str, Any]:
    resolved = resolve_project_path(path)
    if not resolved.is_file():
        raise FileNotFoundError(f"配置文件不存在: {resolved}")
    with resolved.open("r", encoding="utf-8") as stream:
        value = yaml.safe_load(stream) or {}
    if not isinstance(value, dict):
        raise ValueError(f"配置文件顶层必须是对象: {resolved}")
    return value


def normalized_names(names: Mapping[int | str, str] | list[str] | tuple[str, ...]) -> tuple[str, ...]:
    if isinstance(names, Mapping):
        ordered = [names[key] if key in names else names[str(key)] for key in range(len(names))]
    else:
        ordered = list(names)
    return tuple(str(name) for name in ordered)


def require_expected_names(names: Mapping[int | str, str] | list[str] | tuple[str, ...], source: str) -> None:
    actual = normalized_names(names)
    if actual != EXPECTED_NAMES:
        raise ValueError(f"{source} 类别不一致。期望 {EXPECTED_NAMES}，实际 {actual}")


def validate_dataset_yaml(path: str | Path, require_files: bool = True) -> tuple[Path, dict[str, Any]]:
    yaml_path = resolve_project_path(path)
    config = load_yaml(yaml_path)
    require_expected_names(config.get("names", {}), str(yaml_path))
    for key in ("path", "train", "val"):
        if not config.get(key):
            raise ValueError(f"数据集 YAML 缺少必填字段: {key}")

    root = Path(config["path"]).expanduser()
    if not root.is_absolute():
        root = (yaml_path.parent / root).resolve()
    missing: list[Path] = []
    for key in ("train", "val"):
        values = config[key] if isinstance(config[key], list) else [config[key]]
        for value in values:
            candidate = Path(value).expanduser()
            candidate = candidate if candidate.is_absolute() else root / candidate
            if not candidate.exists():
                missing.append(candidate)
    if require_files and missing:
        joined = "\n- ".join(str(item) for item in missing)
        raise FileNotFoundError(f"训练数据集未就绪，缺少路径:\n- {joined}")
    return yaml_path, config


def dataset_fingerprint(path: str | Path) -> str:
    yaml_path, config = validate_dataset_yaml(path, require_files=True)
    root = Path(config["path"])
    if not root.is_absolute():
        root = (yaml_path.parent / root).resolve()
    digest = hashlib.sha256()
    digest.update(yaml_path.read_bytes())
    for relative in sorted(p.relative_to(root) for p in root.rglob("*") if p.is_file()):
        file_path = root / relative
        digest.update(relative.as_posix().encode("utf-8"))
        with file_path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    return digest.hexdigest()


def git_revision() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def write_json(path: str | Path, payload: Mapping[str, Any]) -> Path:
    output = resolve_project_path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output
