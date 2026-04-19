from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class TransitionDecision:
    previous_count: int | None
    current_count: int
    should_alert: bool
    became_available: bool
    reset_availability: bool
    is_currently_available: bool


def evaluate_transition(
    *,
    previous_count: int | None,
    current_count: int,
    now: datetime,
    cooldown_seconds: int = 0,
    last_alerted_at: datetime | None = None,
    notify_on_first_seen_available: bool = False,
) -> TransitionDecision:
    is_currently_available = current_count > 0
    first_observation = previous_count is None
    became_available = False

    if is_currently_available:
        if previous_count == 0:
            became_available = True
        elif first_observation and notify_on_first_seen_available:
            became_available = True

    reset_availability = current_count == 0 and (previous_count or 0) > 0
    should_alert = became_available

    if should_alert and last_alerted_at is not None and cooldown_seconds > 0:
        should_alert = now >= last_alerted_at + timedelta(seconds=cooldown_seconds)

    return TransitionDecision(
        previous_count=previous_count,
        current_count=current_count,
        should_alert=should_alert,
        became_available=became_available,
        reset_availability=reset_availability,
        is_currently_available=is_currently_available,
    )

