from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from app.browser.playwright_manager import persistent_context
from app.browser.selector_helpers import select_date_if_needed, select_round_if_needed
from app.parsers.seat_parser import parse_seat_summary
from app.utils.files import ensure_directory, safe_filename
from app.utils.time import now_utc


class SeatExtractionError(RuntimeError):
    def __init__(self, message: str, screenshot_path: str | None = None):
        super().__init__(message)
        self.screenshot_path = screenshot_path


@dataclass
class ExtractionResult:
    raw_summary_text: str
    screenshot_path: str | None = None
    console_errors: list[str] = field(default_factory=list)


def _build_screenshot_path(screenshot_dir: str | Path, monitor_id: int) -> Path:
    directory = ensure_directory(screenshot_dir)
    timestamp = now_utc().strftime("%Y%m%d_%H%M%S")
    filename = safe_filename(f"monitor_{monitor_id}_{timestamp}.png")
    return directory / filename


def _take_screenshot(page, screenshot_dir: str | Path, monitor_id: int) -> str | None:
    path = _build_screenshot_path(screenshot_dir, monitor_id)
    try:
        page.screenshot(path=str(path), full_page=True)
        return str(path)
    except Exception:
        return None


def _extract_from_body_text(body_text: str, hint: str | None = None) -> str:
    if not body_text:
        return ""

    lines = [line.strip() for line in body_text.splitlines() if line.strip()]
    hint_lower = hint.lower() if hint else ""

    def line_score(line: str) -> tuple[int, int]:
        parsed_count = len(parse_seat_summary(line).counts)
        has_hint = 1 if hint_lower and hint_lower in line.lower() else 0
        return (has_hint, parsed_count)

    best_line = ""
    best_score = (-1, -1)
    for line in lines:
        score = line_score(line)
        if score > best_score:
            best_score = score
            best_line = line

    if best_score[1] > 0:
        return best_line

    compact_text = re.sub(r"\s+", " ", body_text).strip()
    return compact_text


def extract_seat_summary_text(page, selectors: dict, watched_categories: list[str]) -> str:
    seat_summary_selector = selectors.get("seat_summary_selector")
    if seat_summary_selector:
        try:
            text = page.locator(seat_summary_selector).first.text_content(timeout=4000) or ""
            if text.strip():
                return text.strip()
        except Exception:
            pass

    hint = selectors.get("seat_summary_text_hint")
    fallback_hints = [hint, *watched_categories]
    for candidate in fallback_hints:
        if not candidate:
            continue
        try:
            text = page.get_by_text(candidate, exact=False).first.text_content(timeout=4000) or ""
            if text.strip():
                return text.strip()
        except Exception:
            continue

    try:
        body_text = page.locator("body").inner_text(timeout=4000)
    except PlaywrightTimeoutError:
        body_text = ""

    return _extract_from_body_text(body_text, hint=hint)


def extract_monitor_page(
    *,
    monitor,
    profile_path: str | Path,
    browser_type: str,
    screenshot_dir: str | Path,
    request_timeout_seconds: int,
) -> ExtractionResult:
    selectors = monitor.selectors
    console_errors: list[str] = []

    with persistent_context(
        profile_path=profile_path,
        browser_type=browser_type,
        headless=monitor.headless,
    ) as context:
        page = context.pages[0] if context.pages else context.new_page()

        def on_console(message) -> None:
            if message.type == "error":
                console_errors.append(message.text)

        page.on("console", on_console)

        try:
            page.goto(
                monitor.page_url,
                wait_until="domcontentloaded",
                timeout=request_timeout_seconds * 1000,
            )
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except PlaywrightTimeoutError:
                pass

            page.wait_for_timeout(1200)
            select_date_if_needed(page, monitor.date_label, selectors)
            page.wait_for_timeout(500)
            select_round_if_needed(page, monitor.round_label, selectors)
            page.wait_for_timeout(800)

            raw_text = extract_seat_summary_text(
                page,
                selectors=selectors,
                watched_categories=monitor.seat_category_list,
            )
            if not raw_text.strip():
                screenshot_path = _take_screenshot(page, screenshot_dir, monitor.id)
                raise SeatExtractionError("Seat summary text was empty.", screenshot_path)

            return ExtractionResult(
                raw_summary_text=raw_text,
                console_errors=console_errors,
            )
        except SeatExtractionError:
            raise
        except Exception as exc:
            screenshot_path = _take_screenshot(page, screenshot_dir, monitor.id)
            raise SeatExtractionError(str(exc), screenshot_path) from exc
