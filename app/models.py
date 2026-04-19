from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db import Base
from app.utils.time import now_utc


def _decode_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def _decode_json_dict(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


class TimestampMixin:
    created_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=now_utc,
        onupdate=now_utc,
        nullable=False,
    )


class Profile(TimestampMixin, Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), unique=True, nullable=False)
    browser_type = Column(String(40), default="chromium", nullable=False)
    profile_path = Column(String(500), nullable=False)

    monitors = relationship("Monitor", back_populates="profile")


class Monitor(TimestampMixin, Base):
    __tablename__ = "monitors"

    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False)
    event_title = Column(String(255), default="", nullable=False)
    page_url = Column(String(1000), nullable=False)
    date_label = Column(String(100), default="", nullable=False)
    round_label = Column(String(100), default="", nullable=False)
    seat_categories_json = Column(Text, default="[]", nullable=False)
    poll_interval_seconds = Column(Integer, default=45, nullable=False)
    jitter_min_seconds = Column(Integer, default=5, nullable=False)
    jitter_max_seconds = Column(Integer, default=12, nullable=False)
    notification_cooldown_seconds = Column(Integer, default=0, nullable=False)
    enabled = Column(Boolean, default=False, nullable=False)
    selectors_json = Column(Text, default="{}", nullable=False)
    parser_profile = Column(String(120), default="default", nullable=False)
    profile_id = Column(Integer, ForeignKey("profiles.id"), nullable=True)
    headless = Column(Boolean, default=False, nullable=False)
    notify_on_first_seen_available = Column(Boolean, default=False, nullable=False)
    last_check_at = Column(DateTime(timezone=True), nullable=True)
    last_status = Column(String(40), default="", nullable=False)
    last_result_summary = Column(Text, default="", nullable=False)
    last_error = Column(Text, default="", nullable=False)
    consecutive_failures = Column(Integer, default=0, nullable=False)

    profile = relationship("Profile", back_populates="monitors")
    runs = relationship("MonitorRun", back_populates="monitor")
    seat_states = relationship("SeatState", back_populates="monitor")
    alerts = relationship("Alert", back_populates="monitor")

    @property
    def seat_category_list(self) -> list[str]:
        return _decode_json_list(self.seat_categories_json)

    def set_seat_categories(self, categories: list[str]) -> None:
        self.seat_categories_json = json.dumps(categories, ensure_ascii=False)

    @property
    def selectors(self) -> dict[str, Any]:
        return _decode_json_dict(self.selectors_json)

    def set_selectors(self, selectors: dict[str, Any]) -> None:
        self.selectors_json = json.dumps(selectors, ensure_ascii=False, indent=2)


class MonitorRun(Base):
    __tablename__ = "monitor_runs"

    id = Column(Integer, primary_key=True)
    monitor_id = Column(Integer, ForeignKey("monitors.id"), nullable=False)
    started_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(40), default="partial", nullable=False)
    raw_summary_text = Column(Text, default="", nullable=False)
    parsed_counts_json = Column(Text, default="{}", nullable=False)
    screenshot_path = Column(String(1000), nullable=True)
    error_message = Column(Text, default="", nullable=False)
    console_errors = Column(Text, default="", nullable=False)

    monitor = relationship("Monitor", back_populates="runs")


class SeatState(Base):
    __tablename__ = "seat_states"

    id = Column(Integer, primary_key=True)
    monitor_id = Column(Integer, ForeignKey("monitors.id"), nullable=False)
    category_name = Column(String(200), nullable=False)
    last_count = Column(Integer, nullable=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    last_alerted_at = Column(DateTime(timezone=True), nullable=True)
    is_currently_available = Column(Boolean, default=False, nullable=False)

    monitor = relationship("Monitor", back_populates="seat_states")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True)
    monitor_id = Column(Integer, ForeignKey("monitors.id"), nullable=False)
    category_name = Column(String(200), nullable=False)
    old_count = Column(Integer, nullable=True)
    new_count = Column(Integer, nullable=False)
    message = Column(Text, default="", nullable=False)
    sent_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)
    provider = Column(String(80), default="discord_webhook", nullable=False)
    success = Column(Boolean, default=False, nullable=False)
    provider_response = Column(Text, default="", nullable=False)

    monitor = relationship("Monitor", back_populates="alerts")


class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String(120), primary_key=True)
    value = Column(Text, default="", nullable=False)

