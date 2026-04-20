from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import threading
import time
from tempfile import TemporaryDirectory

from playwright.sync_api import sync_playwright

from app.utils.files import ensure_directory


def _resolve_launcher(playwright, browser_type: str):
    normalized = (browser_type or "chromium").strip().lower()
    if normalized == "chrome":
        return playwright.chromium, {"channel": "chrome"}
    if normalized in {"edge", "msedge"}:
        return playwright.chromium, {"channel": "msedge"}
    if normalized in {"chromium", "firefox", "webkit"}:
        return getattr(playwright, normalized), {}
    raise ValueError(
        f"Unsupported browser_type '{browser_type}'. Use chromium, chrome, firefox, webkit, or msedge."
    )


@contextmanager
def persistent_context(
    profile_path: str | Path | None,
    *,
    browser_type: str = "chromium",
    headless: bool = True,
    ephemeral_profile: bool = False,
):
    @contextmanager
    def _user_data_dir():
        if ephemeral_profile or profile_path is None:
            with TemporaryDirectory(prefix="ticket-alert-profile-") as temp_dir:
                yield Path(temp_dir)
            return
        yield ensure_directory(profile_path)

    with _user_data_dir() as profile_dir:
        with sync_playwright() as playwright:
            launcher, launch_options = _resolve_launcher(playwright, browser_type)
            context = launcher.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=headless,
                **launch_options,
            )
            try:
                yield context
            finally:
                context.close()


def open_login_session(profile_path: str | Path, start_url: str, browser_type: str = "chromium") -> None:
    profile_dir = ensure_directory(profile_path)

    with sync_playwright() as playwright:
        launcher, launch_options = _resolve_launcher(playwright, browser_type)
        context = launcher.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            **launch_options,
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
