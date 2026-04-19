from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import AppSetting


def get_setting(session: Session, key: str, default: str = "") -> str:
    row = session.get(AppSetting, key)
    if row is None:
        return default
    return row.value


def set_setting(session: Session, key: str, value: str) -> None:
    row = session.get(AppSetting, key)
    if row is None:
        row = AppSetting(key=key, value=value)
        session.add(row)
    else:
        row.value = value


def get_notification_config(session: Session, settings: Settings) -> dict[str, str]:
    return {
        "webhook_url": get_setting(session, "discord_webhook_url", settings.discord_webhook_url),
        "username": get_setting(session, "discord_username", settings.discord_username),
        "avatar_url": get_setting(session, "discord_avatar_url", settings.discord_avatar_url),
        "enabled": get_setting(session, "enable_discord", "true" if settings.enable_discord else "false"),
    }

