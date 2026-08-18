import pytest

from app.services.schema_safety import validate_generated_json


def test_schema_validation_error_does_not_include_provider_content() -> None:
    marker = "PRIVATE_STUDENT_CONTEXT_MARKER"
    schema = {
        "type": "object",
        "properties": {"answer": {"type": "integer"}},
        "required": ["answer"],
    }

    with pytest.raises(ValueError) as exc_info:
        validate_generated_json(
            {"answer": marker},
            schema,
            kind="Question",
        )

    assert str(exc_info.value) == "Question model returned an invalid schema"
    assert marker not in str(exc_info.value)


def test_valid_generated_json_passes_schema_validation() -> None:
    validate_generated_json(
        {"answer": 42},
        {
            "type": "object",
            "properties": {"answer": {"type": "integer"}},
            "required": ["answer"],
        },
        kind="Question",
    )
