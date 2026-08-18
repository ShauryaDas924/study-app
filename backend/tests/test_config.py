import pytest

from app.config import DEFAULT_CORS_ORIGINS, parse_bounded_int, parse_cors_origins


def test_cors_defaults_are_explicit_local_origins() -> None:
    assert parse_cors_origins(None) == list(DEFAULT_CORS_ORIGINS)
    assert "*" not in parse_cors_origins(None)


def test_cors_parser_normalizes_and_deduplicates() -> None:
    assert parse_cors_origins(
        " https://app.example.com/, http://localhost:3000, https://app.example.com "
    ) == ["https://app.example.com", "http://localhost:3000"]


@pytest.mark.parametrize(
    "value",
    [
        "*",
        "",
        "   ,  ",
        "example.com",
        "ftp://example.com",
        "https://example.com/a/path",
    ],
)
def test_cors_parser_rejects_wildcard_empty_and_invalid_origins(value: str) -> None:
    with pytest.raises(RuntimeError):
        parse_cors_origins(value)


def test_bounded_integer_config_uses_default_and_valid_value() -> None:
    args = {"name": "WORKERS", "default": 3, "minimum": 1, "maximum": 20}
    assert parse_bounded_int(None, **args) == 3
    assert parse_bounded_int("", **args) == 3
    assert parse_bounded_int("7", **args) == 7


@pytest.mark.parametrize("value", ["not-a-number", "0", "21"])
def test_bounded_integer_config_rejects_invalid_values(value: str) -> None:
    with pytest.raises(RuntimeError):
        parse_bounded_int(
            value,
            name="WORKERS",
            default=3,
            minimum=1,
            maximum=20,
        )
