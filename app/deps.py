from __future__ import annotations

from fastapi import Request

from app.config import get_settings
from app.db import get_db


def get_scheduler(request: Request):
    return request.app.state.scheduler


__all__ = ["get_db", "get_scheduler", "get_settings"]

