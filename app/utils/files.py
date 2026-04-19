from __future__ import annotations

import re
from pathlib import Path


_NON_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def ensure_directory(path: str | Path) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def slugify(value: str) -> str:
    cleaned = _NON_SAFE_CHARS.sub("-", value.strip()).strip("-")
    return cleaned.lower() or "default"


def safe_filename(value: str) -> str:
    return _NON_SAFE_CHARS.sub("_", value.strip()).strip("_") or "file"

