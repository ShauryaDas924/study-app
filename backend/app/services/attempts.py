from typing import Any


def public_question_json(
    *, question_type: str, question_json: dict[str, Any] | None
) -> dict[str, Any]:
    """Return only the fields needed to render a question before it is answered."""
    if question_type != "mcq":
        return {"type": "open"}

    question = question_json or {}
    options = question.get("options")
    safe_options = [str(option) for option in options] if isinstance(options, list) else []
    return {"type": "mcq", "options": safe_options}


def resolve_practice_difficulty(
    requested: int | None,
    mastery_values: list[float],
) -> int:
    """Choose a bounded fallback when adaptive difficulty has no mastery history."""
    if requested is not None:
        return requested
    if not mastery_values:
        return 3

    average = sum(mastery_values) / len(mastery_values)
    if average < 0.4:
        return 2
    if average < 0.7:
        return 3
    return 4


def resolve_attempt_correctness(
    *,
    question_type: str,
    question_json: dict[str, Any] | None,
    user_answer_json: dict[str, Any],
    self_reported: bool,
) -> bool:
    """Grade deterministic questions server-side; open answers remain self-assessed."""
    if question_type != "mcq":
        return self_reported

    question = question_json or {}
    selected = user_answer_json.get("selected_index")
    correct = question.get("correct_index")
    options = question.get("options")

    if isinstance(selected, bool) or isinstance(correct, bool):
        return False
    if not isinstance(selected, int) or not isinstance(correct, int):
        return False
    if not isinstance(options, list) or not options:
        return False
    if not 0 <= selected < len(options) or not 0 <= correct < len(options):
        return False

    return selected == correct
