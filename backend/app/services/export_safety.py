from typing import Any


SPREADSHEET_FORMULA_PREFIXES = ("=", "+", "-", "@")


def spreadsheet_safe_text(value: Any) -> str:
    """Prevent text exported to CSV from being interpreted as a formula."""
    text = "" if value is None else str(value)
    probe = text.lstrip(" \t\r\n\v\f")
    if probe.startswith(SPREADSHEET_FORMULA_PREFIXES):
        return f"'{text}"
    return text
