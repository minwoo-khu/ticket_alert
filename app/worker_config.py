from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from app.config import BASE_DIR, load_env_file
from app.utils.files import slugify


DEFAULT_WORKER_CONFIG_PATH = BASE_DIR / "worker.json"


def _to_bool(value, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _to_int(value, default: int) -> int:
    if value is None or value == "":
        return default
    return int(value)


def _resolve_path(raw: str | Path | None, default: str) -> Path:
    candidate = Path(str(raw or default))
    if candidate.is_absolute():
        return candidate
    return BASE_DIR / candidate


@dataclass(frozen=True)
class WorkerDiscordConfig:
    webhook_url: str
    username: str
    avatar_url: str
    enabled: bool


@dataclass(frozen=True)
class WorkerMonitorConfig:
    id: str
    name: str
    page_url: str
    date_label: str = ""
    round_label: str = ""
    seat_categories: list[str] = field(default_factory=list)
    selectors: dict = field(default_factory=dict)
    poll_interval_seconds: int = 45
    headless: bool = False
    browser_type: str = "chromium"
    profile_path: Path | None = None
    persist_profile: bool = False
    notification_cooldown_seconds: int = 0
    notify_on_first_seen_available: bool = False
    enabled: bool = True

    @property
    def seat_category_list(self) -> list[str]:
        return self.seat_categories


@dataclass(frozen=True)
class WorkerConfig:
    timezone: str
    request_timeout_seconds: int
    idle_sleep_seconds: int
    screenshot_dir: Path
    state_path: Path
    profile_dir: Path
    discord: WorkerDiscordConfig
    monitors: list[WorkerMonitorConfig]


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"Worker config was not found at {path}. Create worker.json from the repo template and try again."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def load_worker_config(path: str | Path | None = None) -> WorkerConfig:
    load_env_file()
    config_path = _resolve_path(path or os.getenv("WORKER_CONFIG_PATH"), str(DEFAULT_WORKER_CONFIG_PATH))
    raw = _load_json(config_path)

    timezone = str(raw.get("timezone") or os.getenv("TIMEZONE") or "Asia/Seoul")
    request_timeout_seconds = _to_int(
        raw.get("request_timeout_seconds"),
        _to_int(os.getenv("REQUEST_TIMEOUT_SECONDS"), 45),
    )
    idle_sleep_seconds = _to_int(raw.get("idle_sleep_seconds"), 5)
    screenshot_dir = _resolve_path(
        raw.get("screenshot_dir") or os.getenv("WORKER_SCREENSHOT_DIR"),
        "./runtime/screenshots",
    )
    state_path = _resolve_path(
        raw.get("state_path") or os.getenv("WORKER_STATE_PATH"),
        "./runtime/state.json",
    )
    profile_dir = _resolve_path(
        raw.get("profile_dir") or os.getenv("WORKER_PROFILE_DIR"),
        "./runtime/profiles",
    )

    discord_raw = raw.get("discord", {})
    discord = WorkerDiscordConfig(
        webhook_url=str(discord_raw.get("webhook_url") or os.getenv("DISCORD_WEBHOOK_URL") or ""),
        username=str(discord_raw.get("username") or os.getenv("DISCORD_USERNAME") or "Ticket Alert Bot"),
        avatar_url=str(discord_raw.get("avatar_url") or os.getenv("DISCORD_AVATAR_URL") or ""),
        enabled=_to_bool(
            discord_raw.get("enabled"),
            _to_bool(os.getenv("ENABLE_DISCORD"), True),
        ),
    )

    monitors_raw = raw.get("monitors") or []
    if not isinstance(monitors_raw, list) or not monitors_raw:
        raise ValueError("worker.json must contain a non-empty monitors array.")

    seen_ids: set[str] = set()
    default_browser_type = str(os.getenv("DEFAULT_BROWSER_TYPE") or "chromium")
    monitors: list[WorkerMonitorConfig] = []

    for entry in monitors_raw:
        name = str(entry.get("name") or "").strip()
        page_url = str(entry.get("page_url") or "").strip()
        if not name or not page_url:
            raise ValueError("Each monitor must include non-empty name and page_url values.")

        monitor_id = str(entry.get("id") or slugify(name))
        if monitor_id in seen_ids:
            raise ValueError(f"Duplicate monitor id '{monitor_id}' in worker.json.")
        seen_ids.add(monitor_id)

        profile_path_raw = entry.get("profile_path")
        profile_path = (
            _resolve_path(profile_path_raw, str(profile_dir / slugify(monitor_id)))
            if profile_path_raw
            else profile_dir / slugify(monitor_id)
        )

        monitors.append(
            WorkerMonitorConfig(
                id=monitor_id,
                name=name,
                page_url=page_url,
                date_label=str(entry.get("date_label") or ""),
                round_label=str(entry.get("round_label") or ""),
                seat_categories=[str(item) for item in entry.get("seat_categories") or []],
                selectors=dict(entry.get("selectors") or {}),
                poll_interval_seconds=max(15, _to_int(entry.get("poll_interval_seconds"), 45)),
                headless=_to_bool(entry.get("headless"), False),
                browser_type=str(entry.get("browser_type") or default_browser_type).strip() or default_browser_type,
                profile_path=profile_path,
                persist_profile=_to_bool(entry.get("persist_profile"), False),
                notification_cooldown_seconds=max(
                    0,
                    _to_int(entry.get("notification_cooldown_seconds"), 0),
                ),
                notify_on_first_seen_available=_to_bool(
                    entry.get("notify_on_first_seen_available"),
                    False,
                ),
                enabled=_to_bool(entry.get("enabled"), True),
            )
        )

    return WorkerConfig(
        timezone=timezone,
        request_timeout_seconds=request_timeout_seconds,
        idle_sleep_seconds=max(1, idle_sleep_seconds),
        screenshot_dir=screenshot_dir,
        state_path=state_path,
        profile_dir=profile_dir,
        discord=discord,
        monitors=monitors,
    )
