from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

from app.browser.extraction import extract_monitor_page
from app.parsers.normalizers import normalize_category_label
from app.parsers.seat_parser import parse_seat_summary
from app.services.discord_provider import DiscordWebhookProvider
from app.services.transition_logic import evaluate_transition
from app.utils.files import ensure_directory
from app.utils.time import format_local, now_utc
from app.worker_config import WorkerConfig, WorkerDiscordConfig, WorkerMonitorConfig


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkerCategoryChange:
    category_name: str
    old_count: int | None
    new_count: int


@dataclass(frozen=True)
class WorkerRunResult:
    monitor_id: str
    status: str
    parsed_counts: dict[str, int]
    raw_summary_text: str
    screenshot_path: str | None
    error_message: str
    alerted_categories: list[str]


def build_provider(discord: WorkerDiscordConfig) -> DiscordWebhookProvider | None:
    if not discord.enabled:
        logger.info("Discord notifications are disabled.")
        return None
    if not discord.webhook_url:
        logger.warning("Discord notifications are enabled but DISCORD_WEBHOOK_URL is empty.")
        return None
    return DiscordWebhookProvider(
        webhook_url=discord.webhook_url,
        username=discord.username,
        avatar_url=discord.avatar_url,
    )


def default_monitor_state() -> dict[str, Any]:
    return {
        "counts": {},
        "last_alerted_at": {},
        "last_checked_at": None,
        "last_status": "idle",
        "last_error": "",
        "last_summary": "",
        "last_screenshot_path": None,
    }


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def build_summary_text(counts: dict[str, int]) -> str:
    if not counts:
        return "No categories parsed"
    return ", ".join(f"{name}={count}" for name, count in counts.items())


def filter_counts(parsed_counts: dict[str, int], watched_categories: list[str]) -> dict[str, int]:
    if not watched_categories:
        return parsed_counts

    filtered: dict[str, int] = {}
    normalized_map = {
        normalize_category_label(name): count
        for name, count in parsed_counts.items()
    }
    for category in watched_categories:
        normalized = normalize_category_label(category)
        filtered[normalized or category.strip()] = normalized_map.get(normalized, 0)
    return filtered


def compute_changes(
    *,
    monitor: WorkerMonitorConfig,
    previous_counts: dict[str, int],
    last_alerted_at_by_category: dict[str, str],
    current_counts: dict[str, int],
    checked_at: datetime,
) -> tuple[list[WorkerCategoryChange], dict[str, str]]:
    changes: list[WorkerCategoryChange] = []
    next_last_alerted_at = dict(last_alerted_at_by_category)

    for category_name, current_count in current_counts.items():
        previous_count = previous_counts.get(category_name)
        last_alerted_at = parse_iso_datetime(last_alerted_at_by_category.get(category_name))
        decision = evaluate_transition(
            previous_count=previous_count,
            current_count=current_count,
            now=checked_at,
            cooldown_seconds=monitor.notification_cooldown_seconds,
            last_alerted_at=last_alerted_at,
            notify_on_first_seen_available=monitor.notify_on_first_seen_available,
        )
        if decision.should_alert:
            changes.append(
                WorkerCategoryChange(
                    category_name=category_name,
                    old_count=previous_count,
                    new_count=current_count,
                )
            )
            next_last_alerted_at[category_name] = checked_at.isoformat()

    return changes, next_last_alerted_at


def build_alert_message(
    *,
    monitor: WorkerMonitorConfig,
    changes: list[WorkerCategoryChange],
    checked_at: datetime,
    timezone_name: str,
    screenshot_path: str | None = None,
) -> str:
    lines = [
        "[Ticket Alert]",
        f"Monitor: {monitor.name}",
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
            f"Checked: {format_local(checked_at, timezone_name)}",
        ]
    )

    if screenshot_path:
        lines.append(f"Screenshot: {screenshot_path}")

    return "\n".join(lines)


def is_monitor_due(monitor: WorkerMonitorConfig, monitor_state: dict[str, Any], now: datetime) -> bool:
    if not monitor.enabled:
        return False

    last_checked_at = parse_iso_datetime(monitor_state.get("last_checked_at"))
    if last_checked_at is None:
        return True
    return now >= last_checked_at + timedelta(seconds=monitor.poll_interval_seconds)


def run_monitor_once(
    *,
    monitor: WorkerMonitorConfig,
    config: WorkerConfig,
    state: dict[str, Any],
    provider: DiscordWebhookProvider | None,
) -> WorkerRunResult:
    ensure_directory(config.screenshot_dir)
    ensure_directory(config.profile_dir)
    if monitor.persist_profile:
        ensure_directory(monitor.profile_path or config.profile_dir)

    checked_at = now_utc()
    monitors_state = state.setdefault("monitors", {})
    monitor_state = monitors_state.setdefault(monitor.id, default_monitor_state())

    try:
        extraction = extract_monitor_page(
            monitor=monitor,
            profile_path=(monitor.profile_path or (config.profile_dir / monitor.id))
            if monitor.persist_profile
            else None,
            browser_type=monitor.browser_type,
            screenshot_dir=config.screenshot_dir,
            request_timeout_seconds=config.request_timeout_seconds,
            ephemeral_profile=not monitor.persist_profile,
        )
        parse_result = parse_seat_summary(extraction.raw_summary_text)
        if not parse_result.counts:
            logger.warning(
                "Monitor %s parse failed. Raw text snippet: %s",
                monitor.id,
                extraction.raw_summary_text[:200],
            )
            raise ValueError(parse_result.error or "No seat counts were parsed.")

        watched_counts = filter_counts(parse_result.counts, monitor.seat_category_list)
        changes, last_alerted_at = compute_changes(
            monitor=monitor,
            previous_counts=dict(monitor_state.get("counts") or {}),
            last_alerted_at_by_category=dict(monitor_state.get("last_alerted_at") or {}),
            current_counts=watched_counts,
            checked_at=checked_at,
        )

        if changes:
            message = build_alert_message(
                monitor=monitor,
                changes=changes,
                checked_at=checked_at,
                timezone_name=config.timezone,
                screenshot_path=extraction.screenshot_path,
            )
            if provider is not None:
                notification = provider.send(message)
                if notification.success:
                    logger.info(
                        "Alert sent for %s: %s",
                        monitor.id,
                        ", ".join(change.category_name for change in changes),
                    )
                else:
                    logger.warning(
                        "Discord send failed for %s: %s",
                        monitor.id,
                        notification.response_text,
                    )
            else:
                logger.info(
                    "Availability change detected for %s, but notifications are disabled.",
                    monitor.id,
                )

        monitor_state.update(
            {
                "counts": watched_counts,
                "last_alerted_at": last_alerted_at,
                "last_checked_at": checked_at.isoformat(),
                "last_status": "success",
                "last_error": "",
                "last_summary": build_summary_text(watched_counts),
                "last_screenshot_path": extraction.screenshot_path,
            }
        )

        return WorkerRunResult(
            monitor_id=monitor.id,
            status="success",
            parsed_counts=watched_counts,
            raw_summary_text=extraction.raw_summary_text,
            screenshot_path=extraction.screenshot_path,
            error_message="",
            alerted_categories=[change.category_name for change in changes],
        )
    except Exception as exc:
        screenshot_path = getattr(exc, "screenshot_path", None)
        monitor_state.update(
            {
                "last_checked_at": checked_at.isoformat(),
                "last_status": "error",
                "last_error": str(exc),
                "last_summary": "",
                "last_screenshot_path": screenshot_path,
            }
        )
        logger.exception("Monitor %s failed", monitor.id)
        return WorkerRunResult(
            monitor_id=monitor.id,
            status="error",
            parsed_counts={},
            raw_summary_text="",
            screenshot_path=screenshot_path,
            error_message=str(exc),
            alerted_categories=[],
        )
