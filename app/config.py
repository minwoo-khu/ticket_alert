from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"


def load_env_file(path: Path = ENV_PATH) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _to_int(value: str | None, default: int) -> int:
    if value is None or not value.strip():
        return default
    return int(value)


def _to_path(value: str, default: str) -> Path:
    raw = value or default
    path = Path(raw)
    if path.is_absolute():
        return path
    return BASE_DIR / raw


@dataclass(frozen=True)
class Settings:
    app_env: str
    app_host: str
    app_port: int
    database_url: str
    timezone: str
    default_screenshot_dir: Path
    default_profile_dir: Path
    discord_webhook_url: str
    discord_username: str
    discord_avatar_url: str
    enable_discord: bool
    max_screenshots_per_monitor: int
    request_timeout_seconds: int
    scheduler_sync_seconds: int
    retain_monitor_runs: int
    default_browser_type: str

    @classmethod
    def load(cls) -> "Settings":
        load_env_file()
        return cls(
            app_env=os.getenv("APP_ENV", "development"),
            app_host=os.getenv("APP_HOST", "127.0.0.1"),
            app_port=_to_int(os.getenv("APP_PORT"), 8000),
            database_url=os.getenv("DATABASE_URL", "sqlite:///./data/app.db"),
            timezone=os.getenv("TIMEZONE", "Asia/Seoul"),
            default_screenshot_dir=_to_path(
                os.getenv("DEFAULT_SCREENSHOT_DIR", "./screenshots"),
                "./screenshots",
            ),
            default_profile_dir=_to_path(
                os.getenv("DEFAULT_PROFILE_DIR", "./profiles"),
                "./profiles",
            ),
            discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL", ""),
            discord_username=os.getenv("DISCORD_USERNAME", "Ticket Alert Bot"),
            discord_avatar_url=os.getenv("DISCORD_AVATAR_URL", ""),
            enable_discord=_to_bool(os.getenv("ENABLE_DISCORD"), True),
            max_screenshots_per_monitor=_to_int(
                os.getenv("MAX_SCREENSHOTS_PER_MONITOR"),
                30,
            ),
            request_timeout_seconds=_to_int(
                os.getenv("REQUEST_TIMEOUT_SECONDS"),
                45,
            ),
            scheduler_sync_seconds=_to_int(
                os.getenv("SCHEDULER_SYNC_SECONDS"),
                30,
            ),
            retain_monitor_runs=_to_int(os.getenv("RETAIN_MONITOR_RUNS"), 200),
            default_browser_type=os.getenv("DEFAULT_BROWSER_TYPE", "chromium"),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.load()

