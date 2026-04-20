from __future__ import annotations

import unittest
from unittest.mock import patch

from app.browser.extraction import extract_seat_summary_text, wait_for_seat_summary_text


class _FakePage:
    def __init__(self) -> None:
        self.wait_calls: list[int] = []

    def wait_for_timeout(self, timeout_ms: int) -> None:
        self.wait_calls.append(timeout_ms)


class _FakeLocator:
    def __init__(self, text: str = "") -> None:
        self._text = text

    @property
    def first(self):
        return self

    def text_content(self, timeout: int | None = None) -> str:
        return self._text


class _FakePageForExtraction:
    def __init__(self, body_text: str, selectors: dict[str, str] | None = None) -> None:
        self.body_text = body_text
        self.selectors = selectors or {}

    def locator(self, selector: str):
        if selector == "body":
            class _Body:
                def __init__(self, value: str) -> None:
                    self.value = value

                def inner_text(self, timeout: int | None = None) -> str:
                    return self.value

            return _Body(self.body_text)
        return _FakeLocator(self.selectors.get(selector, ""))


class ExtractionTests(unittest.TestCase):
    def test_extract_seat_summary_text_prefers_side_content_selector(self) -> None:
        page = _FakePageForExtraction(
            body_text="홈 페이지 텍스트",
            selectors={".sideContent": "1회 19:00\n잔여석\n스탠딩R0석스탠딩S0석지정석A1석\n예매하기"},
        )

        value = extract_seat_summary_text(page, selectors={}, watched_categories=[])

        self.assertEqual(value, "스탠딩R0석스탠딩S0석지정석A1석")

    def test_extract_seat_summary_text_uses_booking_block_from_body(self) -> None:
        page = _FakePageForExtraction(
            body_text="상품 예매하기\n회차\n1회 19:00\n잔여석\n스탠딩R0석스탠딩S0석지정석A1석\n예매하기\nPLAY DB",
        )

        value = extract_seat_summary_text(page, selectors={}, watched_categories=[])

        self.assertEqual(value, "스탠딩R0석스탠딩S0석지정석A1석")

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
