import os
from urllib.parse import urlparse


DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)


def parse_bounded_int(
    value: str | None,
    *,
    name: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    raw = str(default) if value is None or not value.strip() else value
    try:
        parsed = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc
    if not minimum <= parsed <= maximum:
        raise RuntimeError(f"{name} must be between {minimum} and {maximum}.")
    return parsed


def parse_cors_origins(value: str | None) -> list[str]:
    """Parse and validate the browser origins allowed to call the API."""
    candidates = value.split(",") if value is not None else DEFAULT_CORS_ORIGINS
    origins: list[str] = []

    for candidate in candidates:
        origin = str(candidate).strip().rstrip("/")
        if not origin:
            continue
        if origin == "*":
            raise RuntimeError(
                "CORS_ORIGINS cannot contain '*' while credentialed requests are enabled."
            )

        parsed = urlparse(origin)
        try:
            parsed.port
        except ValueError as exc:
            raise RuntimeError(f"Invalid CORS origin {origin!r}.") from exc

        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.path
            or parsed.params
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
        ):
            raise RuntimeError(
                f"Invalid CORS origin {origin!r}; use an origin such as http://localhost:3000."
            )
        if origin not in origins:
            origins.append(origin)

    if not origins:
        raise RuntimeError("CORS_ORIGINS must contain at least one explicit origin.")

    return origins


def get_cors_origins() -> list[str]:
    return parse_cors_origins(os.getenv("CORS_ORIGINS"))
