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


def _click_within_container(page, container_selector: str, text: str) -> bool:
    if not container_selector or not text:
        return False

    try:
        container = page.locator(container_selector).first
        if container.count() == 0:
            return False
        for exact in (True, False):
            if _click_locator(container.get_by_text(text, exact=exact)):
                return True
        clicked = page.evaluate(
            """
            ([selector, target]) => {
              const container = document.querySelector(selector);
              if (!container) return false;
              const candidates = [...container.querySelectorAll('*')]
                .filter((element) => {
                  const label = (element.innerText || '').trim();
                  const rect = element.getBoundingClientRect();
                  return label === target && rect.width > 0 && rect.height > 0;
                })
                .sort((left, right) => {
                  const leftArea = left.getBoundingClientRect().width * left.getBoundingClientRect().height;
                  const rightArea = right.getBoundingClientRect().width * right.getBoundingClientRect().height;
                  return leftArea - rightArea;
                });
              const candidate = candidates[0];
              if (!(candidate instanceof HTMLElement)) return false;
              candidate.click();
              return true;
            }
            """,
            [container_selector, text],
        )
        return bool(clicked)
    except Exception:
        return False

    return False


def _is_compact_numeric_candidate(text: str) -> bool:
    stripped = (text or "").strip()
    return stripped.isdigit() and 1 <= len(stripped) <= 2


def _read_selected_date(page, container_selector: str) -> str | None:
    selectors = [
        f"{container_selector} li.picked",
        f"{container_selector} .picked",
    ]
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if locator.count() == 0:
                continue
            value = (locator.text_content(timeout=1000) or "").strip()
            if value:
                return value
        except Exception:
            continue
    return None


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
    container_selectors = [container_selector, ".datepicker-panel"]
    for scoped_selector in container_selectors:
        if not scoped_selector:
            continue
        selected_value = _read_selected_date(page, scoped_selector)
        if selected_value:
            for candidate in candidates:
                if selected_value == str(candidate).strip():
                    return candidate
        for candidate in candidates:
            if _click_within_container(page, scoped_selector, candidate):
                return candidate

    for candidate in candidates:
        if _is_compact_numeric_candidate(candidate):
            continue
        if _click_by_text(page, candidate):
            return candidate

    return None


def select_round_if_needed(page, round_label: str, selectors: dict) -> str | None:
    if not round_label:
        return None

    candidates = [str(selectors.get("round_button_text", "")).strip(), round_label]

    container_selectors = [
        selectors.get("round_picker_container"),
        ".timeTableList",
        ".sideTimeTable",
    ]
    for scoped_selector in container_selectors:
        if not scoped_selector:
            continue
        for candidate in candidates:
            if candidate and _click_within_container(page, scoped_selector, candidate):
                return candidate

    for candidate in candidates:
        if candidate and _click_by_text(page, candidate):
            return candidate

    return None
