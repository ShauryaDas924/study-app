from fastapi import APIRouter, UploadFile, File, Form, Depends, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.services.llm import refine_notes
from app.services.file_extraction import extract_text
from app.services.auth import get_current_user_id
from app.jobs.concept_jobs import concept_extraction_job
from app.models import Note
from uuid import UUID

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("/notes")
async def upload_note(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    class_id: UUID = Form(...),
    mode: str = Form("normal"),
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    content = await file.read()

    raw_text = await extract_text(file.filename, content)
    text = await refine_notes(raw_text)

    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="No text could be extracted from the uploaded file.")

    derived_title = file.filename.rsplit(".", 1)[0].strip() or "Study Note"

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

    print(f"[upload_note] auto-created note={note.id} mode={mode}")

    background_tasks.add_task(
        concept_extraction_job,
        str(note.id),
        str(user_id),
        mode,
    )

    return {
        "filename": file.filename,
        "extracted_text": text,
        "flashcards": [],
        "note_id": str(note.id),
        "title": note.title,
        "status": "queued",
        "progress": 0,
        "mode": mode,
    }
