from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MonitorCreate(BaseModel):
    name: str
    event_title: str = ""
    page_url: str
    date_label: str = ""
    round_label: str = ""
    seat_categories: list[str] = Field(default_factory=list)
    poll_interval_seconds: int = 45
    jitter_min_seconds: int = 5
    jitter_max_seconds: int = 12
    notification_cooldown_seconds: int = 0
    enabled: bool = False
    selectors_json: dict[str, Any] = Field(default_factory=dict)
    parser_profile: str = "default"
    profile_id: int | None = None
    headless: bool = False
    notify_on_first_seen_available: bool = False


class MonitorRead(MonitorCreate):
    id: int
    last_check_at: datetime | None = None
    last_status: str = ""
    last_result_summary: str = ""
    last_error: str = ""

    model_config = {"from_attributes": True}


class AlertRead(BaseModel):
    id: int
    monitor_id: int
    category_name: str
    old_count: int | None = None
    new_count: int
    message: str
    sent_at: datetime
    provider: str
    success: bool

    model_config = {"from_attributes": True}


class HealthResponse(BaseModel):
    status: str = "ok"

