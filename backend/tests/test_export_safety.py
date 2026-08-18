import pytest

from app.services.export_safety import spreadsheet_safe_text


@pytest.mark.parametrize(
    "value",
    [
        "=HYPERLINK(\"https://example.invalid\")",
        "+SUM(1,2)",
        "-10+20",
        "@SUM(1,2)",
        " \t=cmd|' /C calc'!A0",
    ],
)
def test_spreadsheet_formula_prefixes_are_escaped(value: str) -> None:
    assert spreadsheet_safe_text(value) == f"'{value}"


@pytest.mark.parametrize("value", ["Question", "1 + 1", "", None, 0.5])
def test_plain_csv_values_are_left_as_text(value: object) -> None:
    expected = "" if value is None else str(value)
    assert spreadsheet_safe_text(value) == expected
