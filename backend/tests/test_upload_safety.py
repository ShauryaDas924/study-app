import asyncio

from fastapi import HTTPException
import pytest

from app.services.upload_safety import (
    ABSOLUTE_MAX_UPLOAD_BYTES,
    DEFAULT_MAX_UPLOAD_BYTES,
    DOCUMENT_UPLOAD_EXTENSIONS,
    configured_max_upload_bytes,
    read_upload_limited,
    sanitize_upload_filename,
    validate_upload_filename,
)


class FakeUpload:
    def __init__(self, filename: str | None, content: bytes, size: int | None = None):
        self.filename = filename
        self.size = len(content) if size is None else size
        self.content = content
        self.read_limit: int | None = None

    async def read(self, size: int) -> bytes:
        self.read_limit = size
        return self.content[:size]


def test_filename_sanitization_removes_client_paths_and_controls() -> None:
    assert sanitize_upload_filename("../../lecture.pdf") == "lecture.pdf"
    assert sanitize_upload_filename(r"C:\fakepath\lecture.pdf") == "lecture.pdf"
    assert sanitize_upload_filename("notes\x00\n.txt") == "notes.txt"


def test_long_filename_is_bounded_without_losing_extension() -> None:
    result = sanitize_upload_filename(f"{'a' * 300}.pdf")
    assert len(result) == 255
    assert result.endswith(".pdf")


def test_extension_validation_is_case_insensitive() -> None:
    assert validate_upload_filename(
        "Lecture.PDF", DOCUMENT_UPLOAD_EXTENSIONS
    ) == "Lecture.PDF"


@pytest.mark.parametrize("filename", [None, "", "../"])
def test_missing_filename_is_rejected(filename: str | None) -> None:
    with pytest.raises(HTTPException) as exc_info:
        sanitize_upload_filename(filename)
    assert exc_info.value.status_code == 400


def test_unsupported_extension_is_rejected() -> None:
    with pytest.raises(HTTPException) as exc_info:
        validate_upload_filename("payload.exe", DOCUMENT_UPLOAD_EXTENSIONS)
    assert exc_info.value.status_code == 415


def test_upload_limit_configuration_has_safe_bounds() -> None:
    assert configured_max_upload_bytes(None) == DEFAULT_MAX_UPLOAD_BYTES
    assert configured_max_upload_bytes("") == DEFAULT_MAX_UPLOAD_BYTES
    assert configured_max_upload_bytes("1024") == 1024

    for value in ("not-a-number", "0", "-1", str(ABSOLUTE_MAX_UPLOAD_BYTES + 1)):
        with pytest.raises(RuntimeError):
            configured_max_upload_bytes(value)


def test_limited_read_accepts_valid_nonempty_upload() -> None:
    upload = FakeUpload("notes.txt", b"bounded content")
    filename, content = asyncio.run(
        read_upload_limited(upload, DOCUMENT_UPLOAD_EXTENSIONS, max_bytes=32)
    )

    assert filename == "notes.txt"
    assert content == b"bounded content"
    assert upload.read_limit == 33


def test_limited_read_rejects_declared_or_actual_oversize() -> None:
    declared = FakeUpload("notes.txt", b"small", size=100)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            read_upload_limited(declared, DOCUMENT_UPLOAD_EXTENSIONS, max_bytes=10)
        )
    assert exc_info.value.status_code == 413
    assert declared.read_limit is None

    actual = FakeUpload("notes.txt", b"01234567890", size=10)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            read_upload_limited(actual, DOCUMENT_UPLOAD_EXTENSIONS, max_bytes=10)
        )
    assert exc_info.value.status_code == 413
    assert actual.read_limit == 11


def test_limited_read_rejects_empty_upload() -> None:
    upload = FakeUpload("notes.txt", b"")
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            read_upload_limited(upload, DOCUMENT_UPLOAD_EXTENSIONS, max_bytes=10)
        )
    assert exc_info.value.status_code == 400
