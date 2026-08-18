import os
import re
from pathlib import PurePosixPath

from fastapi import HTTPException, UploadFile


DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ABSOLUTE_MAX_UPLOAD_BYTES = 50 * 1024 * 1024

DOCUMENT_UPLOAD_EXTENSIONS = frozenset(
    {".pdf", ".txt", ".md", ".pptx", ".png", ".jpg", ".jpeg"}
)
EXAM_PREP_UPLOAD_EXTENSIONS = frozenset({".pdf", ".txt", ".md", ".pptx"})
IMAGE_OR_PDF_EXTENSIONS = frozenset({".pdf", ".png", ".jpg", ".jpeg"})
SYLLABUS_UPLOAD_EXTENSIONS = frozenset({".pdf", ".txt", ".md"})


def configured_max_upload_bytes(value: str | None = None) -> int:
    raw = value if value is not None else os.getenv("MAX_UPLOAD_BYTES")
    if raw is None or not raw.strip():
        return DEFAULT_MAX_UPLOAD_BYTES

    try:
        limit = int(raw)
    except ValueError as exc:
        raise RuntimeError("MAX_UPLOAD_BYTES must be an integer.") from exc

    if limit <= 0 or limit > ABSOLUTE_MAX_UPLOAD_BYTES:
        raise RuntimeError(
            f"MAX_UPLOAD_BYTES must be between 1 and {ABSOLUTE_MAX_UPLOAD_BYTES}."
        )
    return limit


MAX_UPLOAD_BYTES = configured_max_upload_bytes()


def sanitize_upload_filename(filename: str | None) -> str:
    """Keep a display-safe basename instead of accepting a client-supplied path."""
    normalized = str(filename or "").replace("\\", "/")
    basename = PurePosixPath(normalized).name
    basename = re.sub(r"[\x00-\x1f\x7f]", "", basename).strip()
    if not basename or basename in {".", ".."}:
        raise HTTPException(status_code=400, detail="Uploaded file must have a filename.")

    if len(basename) > 255:
        suffix = PurePosixPath(basename).suffix
        basename = f"{basename[: 255 - len(suffix)]}{suffix}"
    return basename


def validate_upload_filename(
    filename: str | None,
    allowed_extensions: frozenset[str],
) -> str:
    safe_filename = sanitize_upload_filename(filename)
    extension = PurePosixPath(safe_filename).suffix.lower()
    if extension not in allowed_extensions:
        allowed = ", ".join(sorted(allowed_extensions))
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type. Allowed extensions: {allowed}.",
        )
    return safe_filename


async def read_upload_limited(
    file: UploadFile,
    allowed_extensions: frozenset[str],
    max_bytes: int = MAX_UPLOAD_BYTES,
) -> tuple[str, bytes]:
    filename = validate_upload_filename(file.filename, allowed_extensions)

    declared_size = getattr(file, "size", None)
    if declared_size is not None and declared_size > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Upload exceeds the {max_bytes}-byte limit.",
        )

    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Upload exceeds the {max_bytes}-byte limit.",
        )
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    return filename, content
