from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from uuid import UUID

from app.db import get_db
from app.models import Note
from app.services.auth import get_current_user_id
from app.services.queue import concept_queue
router = APIRouter(prefix="/notes", tags=["notes"])


class NoteIn(BaseModel):
    class_id: UUID
    title: str
    content_json: dict


class ExtractionStartBody(BaseModel):
    mode: str | None = None


@router.post("")
async def create_note(
    payload: NoteIn,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    text = ""
    if isinstance(payload.content_json, dict):
        text = (payload.content_json.get("text") or "").strip()

    if not text:
        raise HTTPException(400, "Note text is empty")

    obj = Note(
        user_id=user_id,
        class_id=payload.class_id,
        title=payload.title,
        content_json=payload.content_json,
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return {"id": str(obj.id), "title": obj.title}


@router.get("/by-class/{class_id}")
async def list_notes(
    class_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    res = await db.execute(
        select(Note).where(Note.user_id == user_id, Note.class_id == class_id)
    )
    rows = res.scalars().all()
    return [
        {
            "id": str(n.id),
            "title": n.title,
            "content_json": n.content_json,
            "extraction_status": n.extraction_status,
            "extraction_progress": n.extraction_progress,
            "extraction_mode": n.extraction_mode,
            "extraction_error": n.extraction_error,
        }
        for n in rows
    ]


@router.get("/{note_id}")
async def get_note(
    note_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    res = await db.execute(
        select(Note).where(Note.user_id == user_id, Note.id == note_id)
    )
    note = res.scalar_one_or_none()
    if not note:
        raise HTTPException(404, "Note not found")

    return {
        "id": str(note.id),
        "title": note.title,
        "content_json": note.content_json,
        "extraction_status": note.extraction_status,
        "extraction_progress": note.extraction_progress,
        "extraction_mode": note.extraction_mode,
        "extraction_error": note.extraction_error,
        "extraction_started_at": note.extraction_started_at,
        "extraction_finished_at": note.extraction_finished_at,
    }


@router.post("/{note_id}/extract/start")
async def start_note_extraction(
    note_id: UUID,
    body: ExtractionStartBody,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    res = await db.execute(
        select(Note).where(Note.user_id == user_id, Note.id == note_id)
    )
    note = res.scalar_one_or_none()

    if not note:
        raise HTTPException(404, "Note not found")

    if note.extraction_status in {"queued", "running"}:
        return {
            "message": "Extraction already in progress",
            "note_id": str(note.id),
            "status": note.extraction_status,
            "progress": note.extraction_progress,
            "mode": note.extraction_mode,
        }

    note.extraction_status = "queued"
    note.extraction_progress = 0
    note.extraction_mode = body.mode or "normal"
    note.extraction_error = None
    note.extraction_started_at = datetime.now(timezone.utc)
    note.extraction_finished_at = None
    await db.commit()
    
    print(f"[UVICORN] enqueueing worker job for note_id={note.id} mode={body.mode or 'normal'}")
    job = concept_queue.enqueue(
        "app.services.concept_jobs.concept_extraction_job",
        str(note.id),
        str(user_id),
        body.mode,
        job_timeout="60m",
    )

    print(f"[UVICORN] queued extraction job_id={job.id} note_id={note.id} mode={body.mode or 'normal'}")

    return {
        "message": "Extraction started",
        "note_id": str(note.id),
        "status": "queued",
        "progress": 0,
        "mode": body.mode or "normal",
        "job_id": job.id,
    }


@router.get("/{note_id}/extract/status")
async def get_note_extraction_status(
    note_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    res = await db.execute(
        select(Note).where(Note.user_id == user_id, Note.id == note_id)
    )
    note = res.scalar_one_or_none()

    if not note:
        raise HTTPException(404, "Note not found")
    print(
        f"[STATUS] note_id={note.id} status={note.extraction_status} "
        f"progress={note.extraction_progress} error={note.extraction_error}"
    )
    return {
        "note_id": str(note.id),
        "status": note.extraction_status,
        "progress": note.extraction_progress,
        "mode": note.extraction_mode,
        "error": note.extraction_error,
        "started_at": note.extraction_started_at,
        "finished_at": note.extraction_finished_at,
    }
