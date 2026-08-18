import asyncio
import logging
from types import SimpleNamespace

from app.services.kimi import KIMI_MODEL, build_kimi_user_content


def test_kimi_content_attaches_images_but_not_pdf_data() -> None:
    png_content = build_kimi_user_content(
        "Review this work.",
        mime_type="image/png",
        media_base64="IMAGE_DATA",
    )
    jpeg_content = build_kimi_user_content(
        "Review this work.",
        mime_type="image/jpeg",
        media_base64="JPEG_DATA",
    )
    pdf_content = build_kimi_user_content(
        "Extracted PDF text.",
        mime_type="application/pdf",
        media_base64="PDF_DATA",
    )

    assert isinstance(png_content, list)
    assert png_content[1]["image_url"]["url"] == "data:image/png;base64,IMAGE_DATA"
    assert isinstance(jpeg_content, list)
    assert jpeg_content[1]["image_url"]["url"] == "data:image/jpeg;base64,JPEG_DATA"
    assert pdf_content == "Extracted PDF text."
    assert "PDF_DATA" not in pdf_content


def test_kimi_k26_uses_default_thinking_without_exposing_reasoning(
    monkeypatch,
    caplog,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-placeholder")
    monkeypatch.setenv("MOONSHOT_API_KEY", "test-only-placeholder")
    monkeypatch.setenv("ENABLE_REFINEMENT_CACHE", "0")

    from app.services import llm

    captured_request = {}
    private_reasoning = "PRIVATE_REASONING_MARKER"

    async def fake_kimi_chat_create(**kwargs):
        captured_request.update(kwargs)
        message = SimpleNamespace(
            content='{"clean_notes":"Final notes"}',
            reasoning_content=private_reasoning,
        )
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    monkeypatch.setattr(llm, "kimi_chat_create", fake_kimi_chat_create)
    caplog.set_level(logging.INFO, logger=llm.__name__)

    result = asyncio.run(llm.refine_notes("Original lecture text."))

    assert KIMI_MODEL == "kimi-k2.6"
    assert captured_request["model"] == KIMI_MODEL
    assert "thinking" not in captured_request
    assert "extra_body" not in captured_request
    assert "reasoning_effort" not in captured_request
    assert "temperature" not in captured_request
    assert result == "Final notes"
    assert private_reasoning not in result
    assert private_reasoning not in caplog.text
