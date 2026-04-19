from __future__ import annotations

from html import unescape
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import unittest

from sqlalchemy import select

from app.browser.extraction import ExtractionResult, SeatExtractionError
from app.config import Settings
from app.db import configure_engine, dispose_engine, init_db, session_scope
from app.models import Alert, Monitor, Profile, SeatState
from app.services.monitor_runner import MonitorRunner
from app.utils.files import ensure_directory


def build_test_settings(base_dir: Path, database_url: str) -> Settings:
    return Settings(
        app_env="test",
        app_host="127.0.0.1",
        app_port=8000,
        database_url=database_url,
        timezone="Asia/Seoul",
        default_screenshot_dir=ensure_directory(base_dir / "screenshots"),
        default_profile_dir=ensure_directory(base_dir / "profiles"),
        discord_webhook_url="",
        discord_username="Ticket Alert Bot",
        discord_avatar_url="",
        enable_discord=False,
        max_screenshots_per_monitor=5,
        request_timeout_seconds=5,
        scheduler_sync_seconds=30,
        retain_monitor_runs=50,
        default_browser_type="chromium",
    )


def fixture_extractor(path: Path):
    html = path.read_text(encoding="utf-8")
    match = re.search(r'<div id="seat-summary">(.*?)</div>', html, re.DOTALL)
    if not match:
        raise AssertionError("Fixture is missing #seat-summary")
    summary_text = unescape(re.sub(r"<[^>]+>", " ", match.group(1)))

    def _extract(_monitor: Monitor) -> ExtractionResult:
        return ExtractionResult(raw_summary_text=summary_text)

    return _extract


class MonitorRunnerMockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)
        self.database_url = f"sqlite:///{(self.base_dir / 'test.db').as_posix()}"
        configure_engine(self.database_url)
        init_db()
        self.settings = build_test_settings(self.base_dir, self.database_url)

        with session_scope() as session:
            profile = Profile(
                name="test_profile",
                browser_type="chromium",
                profile_path=str(ensure_directory(self.base_dir / "profiles" / "test_profile")),
            )
            session.add(profile)
            session.flush()

            monitor = Monitor(
                name="Fixture Monitor",
                event_title="Fixture Event",
                page_url="https://tickets.interpark.com/goods/26005670",
                date_label="2026-08-09",
                round_label="",
                poll_interval_seconds=45,
                jitter_min_seconds=0,
                jitter_max_seconds=0,
                notification_cooldown_seconds=0,
                enabled=True,
                parser_profile="default",
                profile_id=profile.id,
                headless=True,
            )
            monitor.set_seat_categories(["ReservedA", "ReservedB"])
            monitor.set_selectors({})
            session.add(monitor)
            session.flush()
            self.monitor_id = monitor.id

    def tearDown(self) -> None:
        dispose_engine()
        self.temp_dir.cleanup()

    def test_runner_uses_fixture_and_creates_alert_on_zero_to_positive(self) -> None:
        runner = MonitorRunner(self.settings)
        fixture_zero = Path("fixtures/sample_seat_summary_01.html")
        fixture_available = Path("fixtures/sample_seat_summary_02.html")

        first_result = runner.run_monitor(
            self.monitor_id,
            force=True,
            extractor=fixture_extractor(fixture_zero),
        )
        second_result = runner.run_monitor(
            self.monitor_id,
            force=True,
            extractor=fixture_extractor(fixture_available),
        )

        self.assertEqual(first_result.status, "success")
        self.assertEqual(second_result.status, "success")
        self.assertEqual(second_result.parsed_counts["ReservedA"], 3)
        self.assertEqual(second_result.alerted_categories, ["ReservedA"])

        with session_scope() as session:
            alerts = list(session.execute(select(Alert)).scalars())
            states = list(
                session.execute(select(SeatState).where(SeatState.monitor_id == self.monitor_id)).scalars()
            )

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].category_name, "ReservedA")
        self.assertEqual({state.category_name: state.last_count for state in states}, {"ReservedA": 3, "ReservedB": 0})

    def test_runner_handles_extraction_failure(self) -> None:
        runner = MonitorRunner(self.settings)

        def failing_extractor(_monitor: Monitor) -> ExtractionResult:
            raise SeatExtractionError("fixture extraction failed", "fake.png")

        result = runner.run_monitor(self.monitor_id, force=True, extractor=failing_extractor)
        self.assertEqual(result.status, "error")
        self.assertEqual(result.screenshot_path, "fake.png")


if __name__ == "__main__":
    unittest.main()
