from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_local(timezone_name: str) -> datetime:
    return now_utc().astimezone(ZoneInfo(timezone_name))


def format_local(dt: datetime | None, timezone_name: str, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    if dt is None:
        return "-"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ZoneInfo(timezone_name)).strftime(fmt)

