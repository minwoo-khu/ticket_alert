from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
import json
import logging
from pathlib import Path
import random
import time

from sqlalchemy import select

from app.browser.extraction import ExtractionResult, SeatExtractionError, extract_monitor_page
from app.config import Settings
from app.db import session_scope
from app.models import Alert, Monitor, MonitorRun, SeatState
from app.parsers.normalizers import normalize_category_label
from app.parsers.seat_parser import parse_seat_summary
from app.services.notifications import CategoryChange, NotificationService
from app.services.screenshot_retention import prune_monitor_screenshots
from app.services.transition_logic import evaluate_transition
from app.utils.files import ensure_directory
from app.utils.time import now_utc


logger = logging.getLogger(__name__)


@dataclass
class RunResult:
    monitor_id: int
    status: str
    parsed_counts: dict[str, int] = field(default_factory=dict)
    raw_summary_text: str = ""
    screenshot_path: str | None = None
    error_message: str = ""
    alerted_categories: list[str] = field(default_factory=list)


class MonitorRunner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.notification_service = NotificationService(settings)

    def run_monitor(
        self,
        monitor_id: int,
        *,
        force: bool = False,
        extractor=None,
    ) -> RunResult:
        with session_scope() as session:
            monitor = session.get(Monitor, monitor_id)
            if monitor is None:
                raise ValueError(f"Monitor {monitor_id} was not found.")

            if not monitor.enabled and not force:
                return RunResult(monitor_id=monitor_id, status="skipped")

            if self._should_backoff(monitor, force=force):
                return RunResult(
                    monitor_id=monitor_id,
                    status="skipped",
                    error_message="backoff active",
                )

            run = MonitorRun(monitor_id=monitor.id, status="partial")
            session.add(run)
            session.flush()

            try:
                if not force and extractor is None:
                    self._sleep_jitter(monitor)

                checked_at = now_utc()
                extraction = (
                    extractor(monitor)
                    if extractor is not None
                    else self._run_live_extraction(monitor)
                )

                parse_result = parse_seat_summary(extraction.raw_summary_text)
                if not parse_result.counts:
                    raise ValueError(parse_result.error or "No seat counts were parsed.")

                watched_counts = self._filter_counts(
                    parsed_counts=parse_result.counts,
                    watched_categories=monitor.seat_category_list,
                )
                changes = self._update_states_and_collect_changes(
                    session=session,
                    monitor=monitor,
                    current_counts=watched_counts,
                    checked_at=checked_at,
                )

                notification_result = None
                message = ""
                if changes:
                    notification_result = self.notification_service.send_availability_alert(
                        session=session,
                        monitor=monitor,
                        changes=changes,
                        checked_at=checked_at,
                        screenshot_path=extraction.screenshot_path,
                    )
                    message = self.notification_service.build_availability_message(
                        monitor=monitor,
                        changes=changes,
                        checked_at=checked_at,
                        screenshot_path=extraction.screenshot_path,
                    )
                    self._record_alerts(
                        session=session,
                        monitor=monitor,
                        changes=changes,
                        message=message,
                        checked_at=checked_at,
                        notification_result=notification_result,
                    )

                run.status = "success"
                run.raw_summary_text = extraction.raw_summary_text
                run.parsed_counts_json = json.dumps(watched_counts, ensure_ascii=False)
                run.console_errors = json.dumps(extraction.console_errors, ensure_ascii=False)
                run.screenshot_path = extraction.screenshot_path
                monitor.last_check_at = checked_at
                monitor.last_status = "success"
                monitor.last_result_summary = self._build_summary_text(watched_counts)
                monitor.last_error = ""
                monitor.consecutive_failures = 0
                run.finished_at = now_utc()

                self._trim_monitor_runs(session, monitor.id)
                prune_monitor_screenshots(
                    monitor.id,
                    self.settings.default_screenshot_dir,
                    self.settings.max_screenshots_per_monitor,
                )

                return RunResult(
                    monitor_id=monitor.id,
                    status="success",
                    parsed_counts=watched_counts,
                    raw_summary_text=extraction.raw_summary_text,
                    screenshot_path=extraction.screenshot_path,
                    alerted_categories=[change.category_name for change in changes],
                )
            except Exception as exc:
                checked_at = now_utc()
                screenshot_path = getattr(exc, "screenshot_path", None)
                run.status = "error"
                run.finished_at = checked_at
                run.error_message = str(exc)
                run.screenshot_path = screenshot_path
                monitor.last_check_at = checked_at
                monitor.last_status = "error"
                monitor.last_error = str(exc)
                monitor.last_result_summary = ""
                monitor.consecutive_failures += 1

                logger.exception("Monitor %s failed", monitor.id)

                return RunResult(
                    monitor_id=monitor.id,
                    status="error",
                    screenshot_path=screenshot_path,
                    error_message=str(exc),
                )

    def _run_live_extraction(self, monitor: Monitor) -> ExtractionResult:
        profile_path = self._resolve_profile_path(monitor)
        ensure_directory(profile_path)
        return extract_monitor_page(
            monitor=monitor,
            profile_path=profile_path,
            browser_type=monitor.profile.browser_type if monitor.profile else self.settings.default_browser_type,
            screenshot_dir=self.settings.default_screenshot_dir,
            request_timeout_seconds=self.settings.request_timeout_seconds,
        )

    def _resolve_profile_path(self, monitor: Monitor) -> Path:
        if monitor.profile and monitor.profile.profile_path:
            return Path(monitor.profile.profile_path)
        return ensure_directory(self.settings.default_profile_dir / "default")

    def _sleep_jitter(self, monitor: Monitor) -> None:
        low = max(0, monitor.jitter_min_seconds)
        high = max(low, monitor.jitter_max_seconds)
        time.sleep(random.randint(low, high))

    def _should_backoff(self, monitor: Monitor, *, force: bool) -> bool:
        if force or monitor.consecutive_failures <= 0 or monitor.last_check_at is None:
            return False

        base = max(monitor.poll_interval_seconds, 15)
        multiplier = min(2 ** (monitor.consecutive_failures - 1), 8)
        wait_window = timedelta(seconds=base * multiplier)
        return now_utc() < monitor.last_check_at + wait_window

    def _filter_counts(
        self,
        *,
        parsed_counts: dict[str, int],
        watched_categories: list[str],
    ) -> dict[str, int]:
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

    def _load_state_map(self, session, monitor_id: int) -> dict[str, SeatState]:
        rows = session.execute(
            select(SeatState).where(SeatState.monitor_id == monitor_id)
        ).scalars()
        return {row.category_name: row for row in rows}

    def _update_states_and_collect_changes(
        self,
        *,
        session,
        monitor: Monitor,
        current_counts: dict[str, int],
        checked_at,
    ) -> list[CategoryChange]:
        state_map = self._load_state_map(session, monitor.id)
        changes: list[CategoryChange] = []

        for category_name, current_count in current_counts.items():
            state = state_map.get(category_name)
            if state is None:
                state = SeatState(
                    monitor_id=monitor.id,
                    category_name=category_name,
                )
                session.add(state)

            previous_count = state.last_count
            decision = evaluate_transition(
                previous_count=previous_count,
                current_count=current_count,
                now=checked_at,
                cooldown_seconds=monitor.notification_cooldown_seconds,
                last_alerted_at=state.last_alerted_at,
                notify_on_first_seen_available=monitor.notify_on_first_seen_available,
            )

            if decision.should_alert:
                changes.append(
                    CategoryChange(
                        category_name=category_name,
                        old_count=previous_count,
                        new_count=current_count,
                    )
                )
                state.last_alerted_at = checked_at

            state.last_count = current_count
            state.last_seen_at = checked_at
            state.is_currently_available = decision.is_currently_available

        return changes

    def _record_alerts(
        self,
        *,
        session,
        monitor: Monitor,
        changes: list[CategoryChange],
        message: str,
        checked_at,
        notification_result,
    ) -> None:
        for change in changes:
            session.add(
                Alert(
                    monitor_id=monitor.id,
                    category_name=change.category_name,
                    old_count=change.old_count,
                    new_count=change.new_count,
                    message=message,
                    sent_at=checked_at,
                    provider="discord_webhook",
                    success=notification_result.success,
                    provider_response=notification_result.response_text,
                )
            )

    def _trim_monitor_runs(self, session, monitor_id: int) -> None:
        keep = max(self.settings.retain_monitor_runs, 1)
        rows = list(
            session.execute(
                select(MonitorRun)
                .where(MonitorRun.monitor_id == monitor_id)
                .order_by(MonitorRun.started_at.desc())
            ).scalars()
        )
        for stale in rows[keep:]:
            session.delete(stale)

    def _build_summary_text(self, counts: dict[str, int]) -> str:
        if not counts:
            return "No categories parsed"
        return ", ".join(f"{name}={count}" for name, count in counts.items())

