from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Monitor
from app.services.app_settings import get_notification_config
from app.services.discord_provider import DiscordWebhookProvider, NotificationResult
from app.utils.time import format_local


@dataclass
class CategoryChange:
    category_name: str
    old_count: int | None
    new_count: int


class NotificationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _provider(self, session: Session) -> DiscordWebhookProvider | None:
        config = get_notification_config(session, self.settings)
        enabled = config["enabled"].lower() in {"1", "true", "yes", "on"}
        if not enabled:
            return None
        return DiscordWebhookProvider(
            webhook_url=config["webhook_url"],
            username=config["username"],
            avatar_url=config["avatar_url"],
        )

    def send_test_notification(self, session: Session, message: str | None = None) -> NotificationResult:
        provider = self._provider(session)
        if provider is None:
            return NotificationResult(False, None, "Discord notifications are disabled.")
        return provider.send(message or "[Ticket Alert] Test notification")

    def send_availability_alert(
        self,
        session: Session,
        monitor: Monitor,
        changes: list[CategoryChange],
        checked_at: datetime,
        screenshot_path: str | None = None,
    ) -> NotificationResult:
        provider = self._provider(session)
        if provider is None:
            return NotificationResult(False, None, "Discord notifications are disabled.")

        content = self.build_availability_message(
            monitor=monitor,
            changes=changes,
            checked_at=checked_at,
            screenshot_path=screenshot_path,
        )
        return provider.send(content)

    def build_availability_message(
        self,
        *,
        monitor: Monitor,
        changes: list[CategoryChange],
        checked_at: datetime,
        screenshot_path: str | None = None,
    ) -> str:
        lines = [
            "[Ticket Alert]",
            f"Monitor: {monitor.name}",
            f"Event: {monitor.event_title or monitor.name}",
            f"Date: {monitor.date_label or '-'}",
            f"Round: {monitor.round_label or '-'}",
            "Changes:",
        ]

        for change in changes:
            old_count = 0 if change.old_count is None else change.old_count
            lines.append(f"- {change.category_name}: {old_count} -> {change.new_count}")

        lines.extend(
            [
                f"URL: {monitor.page_url}",
                f"Checked: {format_local(checked_at, self.settings.timezone)}",
            ]
        )

        if screenshot_path:
            lines.append(f"Screenshot: {screenshot_path}")

        return "\n".join(lines)

