from datetime import datetime, timedelta, timezone
import math

import pytest

from app.services.mastery import (
    apply_forgetting,
    days_since,
    next_review_days,
    suggest_difficulty,
    update_mastery_value,
)


def test_forgetting_decay_is_exponential_and_never_rewinds() -> None:
    assert apply_forgetting(0.8, 0) == pytest.approx(0.8)
    assert apply_forgetting(0.8, -5) == pytest.approx(0.8)
    assert apply_forgetting(0.8, 10, lam=0.05) == pytest.approx(
        0.8 * math.exp(-0.5)
    )


def test_mastery_updates_in_the_expected_direction_and_stays_bounded() -> None:
    correct = update_mastery_value(0.5, True, 3, 3, 120)
    incorrect = update_mastery_value(0.5, False, 3, 3, 120)

    assert 0.5 < correct <= 0.99
    assert 0.01 <= incorrect < 0.5
    assert update_mastery_value(0.999, True, 5, 5, 1) == 0.99


def test_days_since_handles_missing_and_aware_dates() -> None:
    assert days_since(None) == 0
    one_day_ago = datetime.now(timezone.utc) - timedelta(days=1)
    assert days_since(one_day_ago) == pytest.approx(1, abs=0.01)


@pytest.mark.parametrize(
    ("mastery", "difficulty", "review_days"),
    [
        (0.2, 2, 1),
        (0.5, 3, 4),
        (0.75, 4, 7),
        (0.9, 4, 14),
    ],
)
def test_mastery_threshold_recommendations(
    mastery: float, difficulty: int, review_days: int
) -> None:
    assert suggest_difficulty(mastery) == difficulty
    assert next_review_days(mastery) == review_days


def test_repeated_mistakes_force_next_day_review() -> None:
    assert next_review_days(0.95, recent_mistakes=3) == 1
