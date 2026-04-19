from __future__ import annotations

import re

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


def _click_locator(locator) -> bool:
    try:
        locator.first.click(timeout=3000)
        return True
    except Exception:
        return False


def _click_by_text(page, text: str) -> bool:
    if not text:
        return False

    for exact in (True, False):
        try:
            locator = page.get_by_text(text, exact=exact)
            if _click_locator(locator):
                return True
        except PlaywrightTimeoutError:
            continue
        except Exception:
            continue
    return False


def select_date_if_needed(page, date_label: str, selectors: dict) -> str | None:
    if not date_label:
        return None

    candidates: list[str] = []
    configured = selectors.get("date_button_text")
    if configured:
        candidates.append(str(configured))

    candidates.append(date_label)

    digits = re.findall(r"\d+", date_label)
    if digits:
        candidates.append(digits[-1].lstrip("0") or digits[-1])

    container_selector = selectors.get("date_picker_container")
    if container_selector:
        try:
            container = page.locator(container_selector)
            for candidate in candidates:
                if _click_locator(container.get_by_text(candidate, exact=False)):
                    return candidate
        except Exception:
            pass

    for candidate in candidates:
        if _click_by_text(page, candidate):
            return candidate

    return None


def select_round_if_needed(page, round_label: str, selectors: dict) -> str | None:
    if not round_label:
        return None

    candidates = [str(selectors.get("round_button_text", "")).strip(), round_label]

    for candidate in candidates:
        if candidate and _click_by_text(page, candidate):
            return candidate

    return None

