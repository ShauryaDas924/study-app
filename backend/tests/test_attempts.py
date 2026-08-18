import pytest

from app.services.attempts import (
    public_question_json,
    resolve_attempt_correctness,
    resolve_practice_difficulty,
)


MCQ = {
    "options": ["Mercury", "Venus", "Earth", "Mars"],
    "correct_index": 2,
}


def test_mcq_is_graded_from_the_stored_answer_not_the_self_report() -> None:
    assert resolve_attempt_correctness(
        question_type="mcq",
        question_json=MCQ,
        user_answer_json={"selected_index": 2},
        self_reported=False,
    )
    assert not resolve_attempt_correctness(
        question_type="mcq",
        question_json=MCQ,
        user_answer_json={"selected_index": 1},
        self_reported=True,
    )


def test_malformed_mcq_answers_fail_closed() -> None:
    invalid_answers = [
        ({"selected_index": True}, MCQ),
        ({"selected_index": -1}, MCQ),
        ({"selected_index": 4}, MCQ),
        ({}, MCQ),
        ({"selected_index": 2}, {"options": [], "correct_index": 0}),
        ({"selected_index": 2}, None),
    ]

    for user_answer, question in invalid_answers:
        assert not resolve_attempt_correctness(
            question_type="mcq",
            question_json=question,
            user_answer_json=user_answer,
            self_reported=True,
        )


def test_open_answers_keep_explicit_self_assessment() -> None:
    for self_reported in (False, True):
        assert (
            resolve_attempt_correctness(
                question_type="open",
                question_json=None,
                user_answer_json={"answer": "A reasoned response"},
                self_reported=self_reported,
            )
            is self_reported
        )


def test_public_mcq_payload_does_not_expose_the_answer_key() -> None:
    question = {
        **MCQ,
        "type": "mcq",
        "explanation": "Earth is the third planet.",
        "common_mistakes": [{"description": "Picking Mars"}],
    }

    assert public_question_json(question_type="mcq", question_json=question) == {
        "type": "mcq",
        "options": MCQ["options"],
    }


def test_public_open_payload_does_not_expose_solution_material() -> None:
    question = {
        "type": "short",
        "solution": {"steps": ["secret step"], "final_answer": "secret"},
        "reasoning_path": ["secret step"],
    }

    assert public_question_json(question_type="short", question_json=question) == {
        "type": "open"
    }


@pytest.mark.parametrize(
    ("requested", "mastery_values", "expected"),
    [
        (5, [], 5),
        (None, [], 3),
        (None, [0.2, 0.3], 2),
        (None, [0.5, 0.6], 3),
        (None, [0.8, 0.9], 4),
    ],
)
def test_practice_difficulty_always_has_a_deterministic_value(
    requested: int | None,
    mastery_values: list[float],
    expected: int,
) -> None:
    assert resolve_practice_difficulty(requested, mastery_values) == expected
