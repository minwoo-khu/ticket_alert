from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from app.browser.selector_helpers import select_date_if_needed


class SelectorHelpersTests(unittest.TestCase):
    def test_select_date_skips_click_when_date_is_already_selected(self) -> None:
        page = Mock()

        picked_locator = Mock()
        picked_locator.first = picked_locator
        picked_locator.count.return_value = 1
        picked_locator.text_content.return_value = "8"

        empty_locator = Mock()
        empty_locator.first = empty_locator
        empty_locator.count.return_value = 0

        def locator_side_effect(selector: str):
            if selector in {".datepicker-panel li.picked", ".datepicker-panel .picked"}:
                return picked_locator
            return empty_locator

        page.locator.side_effect = locator_side_effect

        with patch("app.browser.selector_helpers._click_within_container") as click_within, patch(
            "app.browser.selector_helpers._click_by_text"
        ) as click_by_text:
            selected = select_date_if_needed(page, "2026-08-08", {"date_button_text": "8"})

        self.assertEqual(selected, "8")
        click_within.assert_not_called()
        click_by_text.assert_not_called()

    def test_select_date_does_not_global_click_compact_numeric_candidate(self) -> None:
        page = Mock()

        empty_locator = Mock()
        empty_locator.first = empty_locator
        empty_locator.count.return_value = 0
        page.locator.return_value = empty_locator

        with patch("app.browser.selector_helpers._click_within_container", return_value=False), patch(
            "app.browser.selector_helpers._click_by_text",
            return_value=False,
        ) as click_by_text:
            selected = select_date_if_needed(page, "2026-08-08", {"date_button_text": "8"})

        self.assertIsNone(selected)
        click_by_text.assert_called_once_with(page, "2026-08-08")


if __name__ == "__main__":
    unittest.main()
