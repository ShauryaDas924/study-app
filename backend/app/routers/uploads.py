from fastapi import APIRouter, UploadFile, File, Form, Depends, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db

from app.services.file_extraction import extract_text
from app.services.auth import get_current_user_id
from app.jobs.concept_jobs import concept_extraction_job
from app.models import Note
from uuid import UUID
from datetime import datetime, timezone
router = APIRouter(prefix="/upload", tags=["upload"])

class StepTimer:
    def __init__(self, label: str, extra: dict | None = None):
        self.label = label
        self.extra = extra or {}
        self.start = None

    def __enter__(self):
        self.start = datetime.now(timezone.utc)
        print(f"[UPLOAD_TIMER] START {self.label}", self.extra)
        return self

    def __exit__(self, exc_type, exc, tb):
        end = datetime.now(timezone.utc)
        elapsed = (end - self.start).total_seconds() if self.start else 0
        print(f"[UPLOAD_TIMER] END {self.label} elapsed={elapsed:.2f}s", self.extra)

@router.post("/notes")
async def upload_note(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    class_id: UUID = Form(...),
    mode: str = Form("normal"),
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    with StepTimer("read_uploaded_file", {"filename": file.filename}):
        content = await file.read()

    print(
        "[upload_note] file_summary",
        {
            "filename": file.filename,
            "bytes": len(content),
            "mode": mode,
            "class_id": str(class_id),
            "user_id": str(user_id),
        },
    )

    with StepTimer("extract_text_from_file", {"filename": file.filename, "bytes": len(content)}):
        raw_text = await extract_text(file.filename, content)

    print(
        "[upload_note] raw_text_summary",
        {
            "filename": file.filename,
            "raw_chars": len(raw_text or ""),
        },
    )

    with StepTimer("prepare_note_text_no_llm", {"filename": file.filename, "raw_chars": len(raw_text or "")}):
        text = raw_text

    print(
        "[upload_note] prepared_text_summary",
        {
            "filename": file.filename,
            "text_chars": len(text or ""),
            "strategy": "raw_text_saved_refinement_runs_in_background_job",
        },
    )

    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="No text could be extracted from the uploaded file.")

    derived_title = file.filename.rsplit(".", 1)[0].strip() or "Study Note"

    with StepTimer("create_note_db_row", {"filename": file.filename}):
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

    with StepTimer("queue_concept_extraction_job", {"note_id": str(note.id), "mode": mode}):
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
