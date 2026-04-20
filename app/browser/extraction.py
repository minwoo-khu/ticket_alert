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


def _trim_to_seat_summary(text: str) -> str:
    candidate = (text or "").strip()
    if not candidate:
        return ""

    if "잔여석" in candidate:
        candidate = candidate.split("잔여석", 1)[1].strip()
    if "예매하기" in candidate:
        candidate = candidate.split("예매하기", 1)[0].strip()

    return candidate.strip()


def _booking_panel_ready(page) -> bool:
    selector_candidates = [
        ".sideContainer.containerMiddle.sideToggleWrap .sideContent",
        ".sideContent",
        ".productSide",
    ]
    for selector in selector_candidates:
        try:
            locator = page.locator(selector).first
            if locator.count() == 0:
                continue
            text = (locator.text_content(timeout=1000) or "").strip()
            if "잔여석" in text or ("상품 예매하기" in text and "관람일" in text):
                return True
        except Exception:
            continue

    try:
        body_text = page.locator("body").inner_text(timeout=1000)
    except Exception:
        body_text = ""

    return "상품 예매하기" in body_text and "관람일" in body_text and "잔여석" in body_text


def wait_for_booking_panel(page, *, timeout_ms: int = 30000, poll_interval_ms: int = 1000) -> bool:
    waited = 0
    while waited <= timeout_ms:
        if _booking_panel_ready(page):
            return True
        if waited >= timeout_ms:
            break
        page.wait_for_timeout(poll_interval_ms)
        waited += poll_interval_ms
    return False


def dismiss_known_overlays(page) -> None:
    notice_popup = page.locator("#popup-prdGuide.is-visible, .popup.popPrdGuide.is-visible").first
    if notice_popup.count() == 0:
        return

    try:
        page.evaluate(
            """
            () => {
              const checkbox = document.querySelector('#popup-prdGuide .popupCheckLabel');
              if (checkbox instanceof HTMLElement) {
                checkbox.click();
              }
            }
            """
        )
        page.wait_for_timeout(150)
    except Exception:
        pass

    try:
        page.evaluate(
            """
            () => {
              const closeButton = document.querySelector('#popup-prdGuide .popupCloseBtn');
              if (closeButton instanceof HTMLElement) {
                closeButton.click();
              }
            }
            """
        )
        page.wait_for_timeout(250)
    except Exception:
        pass


def extract_seat_summary_text(page, selectors: dict, watched_categories: list[str]) -> str:
    selector_candidates = [
        selectors.get("seat_summary_selector"),
        ".sideContainer.containerMiddle.sideToggleWrap .sideContent",
        ".sideContent",
    ]
    for seat_summary_selector in selector_candidates:
        if not seat_summary_selector:
            continue
        try:
            text = page.locator(seat_summary_selector).first.text_content(timeout=4000) or ""
            text = _trim_to_seat_summary(text)
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

    booking_match = re.search(r"잔여석\s*(?P<summary>.+?)\s*예매하기", body_text, re.DOTALL)
    if booking_match:
        summary = _trim_to_seat_summary(booking_match.group("summary"))
        if summary:
            return summary

    return _extract_from_body_text(body_text, hint=hint)


def wait_for_seat_summary_text(
    page,
    *,
    selectors: dict,
    watched_categories: list[str],
    timeout_ms: int = 12000,
    poll_interval_ms: int = 500,
) -> str:
    deadline = timeout_ms
    waited = 0
    last_text = ""

    while waited <= deadline:
        candidate = extract_seat_summary_text(
            page,
            selectors=selectors,
            watched_categories=watched_categories,
        )
        if candidate.strip():
            last_text = candidate.strip()
            if parse_seat_summary(last_text).counts:
                return last_text

        if waited >= deadline:
            break

        page.wait_for_timeout(poll_interval_ms)
        waited += poll_interval_ms

    return last_text


def extract_monitor_page(
    *,
    monitor,
    profile_path: str | Path | None,
    browser_type: str,
    screenshot_dir: str | Path,
    request_timeout_seconds: int,
    ephemeral_profile: bool = False,
) -> ExtractionResult:
    selectors = monitor.selectors
    console_errors: list[str] = []

    with persistent_context(
        profile_path=profile_path,
        browser_type=browser_type,
        headless=monitor.headless,
        ephemeral_profile=ephemeral_profile,
    ) as context:
        page = context.pages[0] if context.pages else context.new_page()

        def on_console(message) -> None:
            if message.type == "error":
                console_errors.append(message.text)

        page.on("console", on_console)

        try:
            def load_target_page() -> None:
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
                dismiss_known_overlays(page)

            load_target_page()
            if not wait_for_booking_panel(page, timeout_ms=30000):
                # Slow cloud runners sometimes land on a partially rendered marketing shell first.
                load_target_page()
                if not wait_for_booking_panel(page, timeout_ms=30000):
                    screenshot_path = _take_screenshot(page, screenshot_dir, monitor.id)
                    raise SeatExtractionError(
                        f"Booking panel did not become ready. URL={page.url} TITLE={page.title()}",
                        screenshot_path,
                    )
            if monitor.date_label:
                select_date_if_needed(page, monitor.date_label, selectors)
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except PlaywrightTimeoutError:
                pass
            page.wait_for_timeout(800)
            if monitor.round_label:
                select_round_if_needed(page, monitor.round_label, selectors)
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except PlaywrightTimeoutError:
                pass
            page.wait_for_timeout(1200)
            dismiss_known_overlays(page)
            if not wait_for_booking_panel(page, timeout_ms=15000):
                screenshot_path = _take_screenshot(page, screenshot_dir, monitor.id)
                raise SeatExtractionError(
                    f"Booking panel disappeared before extraction. URL={page.url} TITLE={page.title()}",
                    screenshot_path,
                )

            raw_text = wait_for_seat_summary_text(
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
