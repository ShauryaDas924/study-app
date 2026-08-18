from typing import Any


KIMI_MODEL = "kimi-k2.6"
KIMI_IMAGE_MIME_TYPES = frozenset({"image/jpeg", "image/png"})


def build_kimi_user_content(
    text: str,
    *,
    mime_type: str | None = None,
    media_base64: str | None = None,
) -> str | list[dict[str, Any]]:
    """Attach only image formats supported by this application's Kimi inputs."""
    if mime_type not in KIMI_IMAGE_MIME_TYPES or not media_base64:
        return text

    return [
        {"type": "text", "text": text},
        {
            "type": "image_url",
            "image_url": {"url": f"data:{mime_type};base64,{media_base64}"},
        },
    ]
