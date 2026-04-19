from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import threading
import time

from playwright.sync_api import sync_playwright

from app.utils.files import ensure_directory


@contextmanager
def persistent_context(profile_path: str | Path, *, browser_type: str = "chromium", headless: bool = True):
    profile_dir = ensure_directory(profile_path)

    with sync_playwright() as playwright:
        launcher = getattr(playwright, browser_type)
        context = launcher.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
        )
        try:
            yield context
        finally:
            context.close()


def open_login_session(profile_path: str | Path, start_url: str, browser_type: str = "chromium") -> None:
    profile_dir = ensure_directory(profile_path)

    with sync_playwright() as playwright:
        launcher = getattr(playwright, browser_type)
        context = launcher.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
        )
        page = context.pages[0] if context.pages else context.new_page()

        if start_url:
            page.goto(start_url, wait_until="domcontentloaded")

        try:
            while True:
                open_pages = [candidate for candidate in context.pages if not candidate.is_closed()]
                if not open_pages:
                    break
                time.sleep(1)
        finally:
            context.close()


def start_login_session_thread(profile_path: str | Path, start_url: str, browser_type: str = "chromium") -> threading.Thread:
    thread = threading.Thread(
        target=open_login_session,
        kwargs={
            "profile_path": str(profile_path),
            "start_url": start_url,
            "browser_type": browser_type,
        },
        daemon=True,
    )
    thread.start()
    return thread

