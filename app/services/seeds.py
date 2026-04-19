from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Monitor, Profile
from app.services.app_settings import set_setting
from app.utils.files import ensure_directory


DEFAULT_EVENT_TITLE = "Interpark Ticket 26005670"
DEFAULT_PAGE_URL = "https://tickets.interpark.com/goods/26005670"


def _ensure_default_profile(session: Session, settings: Settings) -> Profile:
    profile = session.execute(
        select(Profile).where(Profile.name == "interpark_main")
    ).scalar_one_or_none()
    if profile is not None:
        return profile

    profile_path = ensure_directory(settings.default_profile_dir / "interpark_main")
    profile = Profile(
        name="interpark_main",
        browser_type=settings.default_browser_type,
        profile_path=str(profile_path),
    )
    session.add(profile)
    session.flush()
    return profile


def _monitor_exists(session: Session, name: str) -> bool:
    return session.execute(select(Monitor).where(Monitor.name == name)).scalar_one_or_none() is not None


def seed_defaults(session: Session, settings: Settings) -> None:
    profile = _ensure_default_profile(session, settings)

    set_setting(session, "discord_username", settings.discord_username)
    set_setting(session, "discord_avatar_url", settings.discord_avatar_url)
    set_setting(session, "enable_discord", "true" if settings.enable_discord else "false")

    samples = [
        {
            "name": "Interpark 8/8 Watch",
            "date_label": "2026-08-08",
            "selectors": {
                "date_button_text": "8",
            },
        },
        {
            "name": "Interpark 8/9 Watch",
            "date_label": "2026-08-09",
            "selectors": {
                "date_button_text": "9",
            },
        },
    ]

    for sample in samples:
        if _monitor_exists(session, sample["name"]):
            continue

        monitor = Monitor(
            name=sample["name"],
            event_title=DEFAULT_EVENT_TITLE,
            page_url=DEFAULT_PAGE_URL,
            date_label=sample["date_label"],
            round_label="",
            poll_interval_seconds=45,
            jitter_min_seconds=5,
            jitter_max_seconds=12,
            notification_cooldown_seconds=0,
            enabled=False,
            parser_profile="default",
            profile_id=profile.id,
            headless=False,
        )
        monitor.set_seat_categories([])
        monitor.set_selectors(sample["selectors"])
        session.add(monitor)
