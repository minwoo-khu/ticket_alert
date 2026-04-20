from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.utils.files import ensure_directory


def load_worker_state(path: str | Path) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return {"monitors": {}}

    raw = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {"monitors": {}}
    monitors = raw.get("monitors")
    if not isinstance(monitors, dict):
        raw["monitors"] = {}
    return raw


def save_worker_state(path: str | Path, state: dict[str, Any]) -> None:
    state_path = Path(path)
    ensure_directory(state_path.parent)
    temp_path = state_path.with_suffix(state_path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temp_path.replace(state_path)
