from __future__ import annotations

import unittest

from app.utils.time import now_utc
from app.worker_config import WorkerMonitorConfig
from app.worker_runtime import compute_changes, filter_counts


class WorkerRuntimeTests(unittest.TestCase):
    def test_filter_counts_uses_requested_categories(self) -> None:
        counts = {"Standing": 0, "ReservedA": 2, "ReservedB": 1}
        filtered = filter_counts(counts, ["ReservedA", "ReservedC"])
        self.assertEqual(filtered, {"ReservedA": 2, "ReservedC": 0})

    def test_compute_changes_alerts_on_zero_to_positive(self) -> None:
        monitor = WorkerMonitorConfig(
            id="sample",
            name="Sample",
            page_url="https://example.com",
        )
        changes, updated = compute_changes(
            monitor=monitor,
            previous_counts={"ReservedA": 0},
            last_alerted_at_by_category={},
            current_counts={"ReservedA": 3},
            checked_at=now_utc(),
        )

        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].category_name, "ReservedA")
        self.assertIn("ReservedA", updated)

    def test_compute_changes_does_not_alert_when_still_positive(self) -> None:
        monitor = WorkerMonitorConfig(
            id="sample",
            name="Sample",
            page_url="https://example.com",
        )
        changes, updated = compute_changes(
            monitor=monitor,
            previous_counts={"ReservedA": 2},
            last_alerted_at_by_category={},
            current_counts={"ReservedA": 5},
            checked_at=now_utc(),
        )

        self.assertEqual(changes, [])
        self.assertEqual(updated, {})


if __name__ == "__main__":
    unittest.main()
