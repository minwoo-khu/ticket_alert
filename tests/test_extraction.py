from __future__ import annotations

import unittest
from unittest.mock import patch

from app.browser.extraction import wait_for_seat_summary_text


class _FakePage:
    def __init__(self) -> None:
        self.wait_calls: list[int] = []

    def wait_for_timeout(self, timeout_ms: int) -> None:
        self.wait_calls.append(timeout_ms)


class ExtractionTests(unittest.TestCase):
    def test_wait_for_seat_summary_text_retries_until_counts_exist(self) -> None:
        page = _FakePage()
        results = iter(
            [
                "예매 안내",
                "예매 안내",
                "스탠딩R 0석 지정석A 1석",
            ]
        )

        with patch(
            "app.browser.extraction.extract_seat_summary_text",
            side_effect=lambda *args, **kwargs: next(results),
        ):
            value = wait_for_seat_summary_text(
                page,
                selectors={},
                watched_categories=[],
                timeout_ms=1500,
                poll_interval_ms=500,
            )

        self.assertEqual(value, "스탠딩R 0석 지정석A 1석")
        self.assertEqual(page.wait_calls, [500, 500])

    def test_wait_for_seat_summary_text_returns_last_text_after_timeout(self) -> None:
        page = _FakePage()

        with patch(
            "app.browser.extraction.extract_seat_summary_text",
            return_value="예매 안내",
        ):
            value = wait_for_seat_summary_text(
                page,
                selectors={},
                watched_categories=[],
                timeout_ms=1000,
                poll_interval_ms=500,
            )

        self.assertEqual(value, "예매 안내")
        self.assertEqual(page.wait_calls, [500, 500])


if __name__ == "__main__":
    unittest.main()
