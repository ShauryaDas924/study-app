import logging
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.jobs.concept_jobs import concept_extraction_job
from app.models import Class, Note
from app.services.auth import get_current_user_id
from app.services.file_extraction import extract_text
from app.services.upload_safety import DOCUMENT_UPLOAD_EXTENSIONS, read_upload_limited


router = APIRouter(prefix="/upload", tags=["upload"])
logger = logging.getLogger(__name__)


@router.post("/notes")
async def upload_note(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    class_id: UUID = Form(...),
    mode: Literal["normal", "math"] = Form("normal"),
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    class_res = await db.execute(
        select(Class.id).where(Class.id == class_id, Class.user_id == user_id)
    )
    if not class_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Class not found")

    filename, content = await read_upload_limited(file, DOCUMENT_UPLOAD_EXTENSIONS)
    logger.info("note_upload_received bytes=%d mode=%s", len(content), mode)

    try:
        text = await extract_text(filename, content)
    except Exception as exc:
        logger.warning("note_upload_extraction_failed error_type=%s", type(exc).__name__)
        raise HTTPException(status_code=400, detail="The uploaded file could not be processed.") from exc

    if not text or not text.strip() or text.strip().lower() == "unsupported file type":
        raise HTTPException(
            status_code=400,
            detail="No text could be extracted from the uploaded file.",
        )

    derived_title = filename.rsplit(".", 1)[0].strip() or "Study Note"
    note = Note(
        user_id=user_id,
        class_id=class_id,
        title=derived_title,
        content_json={"text": text},
        extraction_status="queued",
        extraction_progress=0,
        extraction_mode=mode,
        extraction_error=None,
        extraction_started_at=None,
        extraction_finished_at=None,
    )

    db.add(note)
    await db.commit()
    await db.refresh(note)

    background_tasks.add_task(
        concept_extraction_job,
        str(note.id),
        str(user_id),
        mode,
    )
    logger.info("note_upload_queued mode=%s extracted_chars=%d", mode, len(text))

    return {
        "filename": filename,
        "extracted_text": text,
        "flashcards": [],
        "note_id": str(note.id),
        "title": note.title,
        "status": "queued",
        "progress": 0,
        "mode": mode,
    }
