from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.analyzers import build_context, safe_extract_zip
from app.schemas import ProjectContext


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True)


def json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def build_project_context(project_name: str, project_root: str | Path) -> ProjectContext:
    context_data = build_context(project_root, project_name=project_name)
    return ProjectContext.model_validate(context_data)


def extract_zip_safely(zip_path: str | Path, destination_dir: str | Path) -> Path:
    return safe_extract_zip(zip_path, destination_dir)
