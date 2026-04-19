from __future__ import annotations

from datetime import timedelta
import unittest

from app.services.transition_logic import evaluate_transition
from app.utils.time import now_utc


class TransitionLogicTests(unittest.TestCase):
    def test_first_observation_zero_does_not_alert(self) -> None:
        decision = evaluate_transition(
            previous_count=None,
            current_count=0,
            now=now_utc(),
        )
        self.assertFalse(decision.should_alert)

    def test_zero_to_one_alerts(self) -> None:
        decision = evaluate_transition(
            previous_count=0,
            current_count=1,
            now=now_utc(),
        )
        self.assertTrue(decision.should_alert)

    def test_zero_to_five_alerts(self) -> None:
        decision = evaluate_transition(
            previous_count=0,
            current_count=5,
            now=now_utc(),
        )
        self.assertTrue(decision.should_alert)

    def test_positive_to_positive_does_not_alert(self) -> None:
        decision = evaluate_transition(
            previous_count=2,
            current_count=3,
            now=now_utc(),
        )
        self.assertFalse(decision.should_alert)

    def test_positive_to_zero_resets(self) -> None:
        decision = evaluate_transition(
            previous_count=3,
            current_count=0,
            now=now_utc(),
        )
        self.assertTrue(decision.reset_availability)
        self.assertFalse(decision.is_currently_available)

    def test_zero_to_one_after_reset_alerts_again(self) -> None:
        current_time = now_utc()
        reset = evaluate_transition(
            previous_count=4,
            current_count=0,
            now=current_time,
        )
        decision = evaluate_transition(
            previous_count=0,
            current_count=1,
            now=current_time + timedelta(seconds=1),
        )
        self.assertTrue(reset.reset_availability)
        self.assertTrue(decision.should_alert)


if __name__ == "__main__":
    unittest.main()

