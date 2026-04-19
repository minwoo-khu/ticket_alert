from __future__ import annotations

import unittest

from app.parsers.seat_parser import parse_counts, parse_seat_summary


class SeatParserTests(unittest.TestCase):
    def test_standard_single_line_input(self) -> None:
        text = "Standing 0 seats / ReservedA 1 seats / ReservedB 12 seats"
        self.assertEqual(
            parse_counts(text),
            {"Standing": 0, "ReservedA": 1, "ReservedB": 12},
        )

    def test_multiple_spaces(self) -> None:
        text = "Standing   0 seats   /   ReservedA   5 seats"
        self.assertEqual(parse_counts(text), {"Standing": 0, "ReservedA": 5})

    def test_line_breaks(self) -> None:
        text = "Standing 0 seats\nReservedA 2 seats\nReservedB 0 seats"
        self.assertEqual(
            parse_counts(text),
            {"Standing": 0, "ReservedA": 2, "ReservedB": 0},
        )

    def test_mixed_separators(self) -> None:
        text = "Standing 0 seats, ReservedA 2 seats | ReservedB 3 seats"
        self.assertEqual(
            parse_counts(text),
            {"Standing": 0, "ReservedA": 2, "ReservedB": 3},
        )

    def test_korean_labels(self) -> None:
        text = "스탠딩 0석 / 지정석A 1석 / 지정석B 12석"
        self.assertEqual(parse_counts(text), {"스탠딩": 0, "지정석A": 1, "지정석B": 12})

    def test_bad_input_returns_empty_counts(self) -> None:
        result = parse_seat_summary("Seat summary unavailable")
        self.assertEqual(result.counts, {})
        self.assertEqual(result.error, "no categories found")


if __name__ == "__main__":
    unittest.main()

