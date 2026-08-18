from datetime import datetime, timedelta, timezone

import app.services.planner as planner


FIXED_NOW = datetime(2026, 8, 17, 15, 0, tzinfo=timezone.utc)


class FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return FIXED_NOW.replace(tzinfo=None)
        return FIXED_NOW.astimezone(tz)


def _mastery_rows() -> list[dict]:
    return [
        {
            "concept_id": "weak-due",
            "name": "Weak and due",
            "mastery_prob": 0.2,
            "next_review_at": FIXED_NOW - timedelta(hours=1),
            "mistake_count": 2,
            "exam_importance": 1.0,
        },
        {
            "concept_id": "strong",
            "name": "Strong",
            "mastery_prob": 0.8,
            "next_review_at": FIXED_NOW + timedelta(days=3),
            "mistake_count": 0,
            "exam_importance": 0.2,
        },
    ]


def _task_minutes(day: dict) -> int:
    return sum(task["minutes"] for task in day["tasks"])


def test_daily_plan_has_deterministic_dates_and_respects_budget(monkeypatch) -> None:
    monkeypatch.setattr(planner, "datetime", FrozenDateTime)

    result = planner.build_study_plan(
        FIXED_NOW + timedelta(days=4),
        _mastery_rows(),
        available_minutes_per_day=60,
    )

    assert result["days_left"] == 4
    assert [day["day"] for day in result["plan"]] == [
        "2026-08-17",
        "2026-08-18",
        "2026-08-19",
        "2026-08-20",
    ]
    assert all(_task_minutes(day) == 60 for day in result["plan"])
    assert result["plan"][0]["tasks"][0]["concept_id"] == "weak-due"


def test_daily_plan_fills_budget_even_without_concepts(monkeypatch) -> None:
    monkeypatch.setattr(planner, "datetime", FrozenDateTime)

    result = planner.build_study_plan(
        FIXED_NOW + timedelta(days=1),
        [],
        available_minutes_per_day=25,
    )

    assert len(result["plan"]) == 1
    assert _task_minutes(result["plan"][0]) == 25
    assert [task["type"] for task in result["plan"][0]["tasks"]] == [
        "practice",
        "reflection",
    ]


def test_weekly_plan_stops_at_exam_and_respects_each_daily_budget(monkeypatch) -> None:
    monkeypatch.setattr(planner, "datetime", FrozenDateTime)
    exam_date = FIXED_NOW + timedelta(days=8)

    result = planner.build_weekly_curriculum(
        exam_date,
        _mastery_rows(),
        available_minutes_per_day=60,
    )
    days = [day for week in result["weekly_plan"] for day in week["days"]]

    assert result["days_left"] == 8
    assert result["weeks_left"] == 2
    assert days[0]["day"] == "2026-08-17"
    assert days[-1]["day"] == "2026-08-25"
    assert all(datetime.fromisoformat(day["day"]).date() <= exam_date.date() for day in days)
    assert all(_task_minutes(day) == 60 for day in days)
