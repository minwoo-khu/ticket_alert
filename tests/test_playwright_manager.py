from __future__ import annotations

import unittest
from unittest.mock import patch

from app.browser.playwright_manager import _build_launch_options


class PlaywrightManagerTests(unittest.TestCase):
    def test_chromium_gets_safe_docker_args(self) -> None:
        options = _build_launch_options("chromium", {})
        self.assertIn("--disable-dev-shm-usage", options["args"])

    def test_root_adds_no_sandbox_for_chromium(self) -> None:
        with patch("app.browser.playwright_manager.os.geteuid", return_value=0, create=True):
            options = _build_launch_options("chromium", {})
        self.assertIn("--no-sandbox", options["args"])
        self.assertIn("--disable-setuid-sandbox", options["args"])

    def test_firefox_keeps_args_empty(self) -> None:
        options = _build_launch_options("firefox", {})
        self.assertNotIn("args", options)


if __name__ == "__main__":
    unittest.main()
