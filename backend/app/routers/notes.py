from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from app.jobs.concept_jobs import (
    concept_extraction_job,
    get_concept_job_status,
    set_concept_job_status,
)
from app.db import get_db
from app.models import Class, Note
from app.services.auth import get_current_user_id

router = APIRouter(prefix="/notes", tags=["notes"])

class NoteIn(BaseModel):
    class_id: UUID
    title: str
    content_json: dict
    auto_extract: bool = False
    mode: Optional[str] = None
    
class StartExtractionIn(BaseModel):
    mode: Optional[str] = None


class StartExtractionOut(BaseModel):
    message: str
    note_id: str
    status: str
    progress: int
    mode: str


class ExtractionStatusOut(BaseModel):
    note_id: str
    status: str
    progress: int
    mode: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    
@router.post("")
async def create_note(
    payload: NoteIn,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    class_res = await db.execute(
        select(Class.id).where(Class.id == payload.class_id, Class.user_id == user_id)
    )
    if not class_res.scalar_one_or_none():
        raise HTTPException(404, "Class not found")

    obj = Note(
        user_id=user_id,
        class_id=payload.class_id,
        title=payload.title,
        content_json=payload.content_json,
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)

    mode = payload.mode or "normal"

    if payload.auto_extract:
        obj.extraction_status = "queued"
        obj.extraction_progress = 0
        obj.extraction_mode = mode
        obj.extraction_error = None
        obj.extraction_started_at = None
        obj.extraction_finished_at = None
        await db.commit()

        set_concept_job_status(
            str(obj.id),
            {
                "note_id": str(obj.id),
                "user_id": str(user_id),
                "status": "queued",
                "progress": 0,
                "mode": mode,
                "error": None,
                "started_at": None,
                "finished_at": None,
            },
        )

        print(f"[notes.create_note] queued extraction for note={obj.id} mode={mode}")

        background_tasks.add_task(
            concept_extraction_job,
            str(obj.id),
            str(user_id),
            mode,
        )

        return {
            "id": str(obj.id),
            "title": obj.title,
            "status": "queued",
            "progress": 0,
            "mode": mode,
        }

    return {"id": str(obj.id), "title": obj.title}

@router.get("/by-class/{class_id}")
async def list_notes(class_id: UUID, db: AsyncSession = Depends(get_db), user_id: UUID = Depends(get_current_user_id)):
    res = await db.execute(select(Note).where(Note.user_id == user_id, Note.class_id == class_id))
    rows = res.scalars().all()
    return [{"id": str(n.id), "title": n.title, "content_json": n.content_json} for n in rows]

@router.get("/{note_id}")
async def get_note(note_id: UUID, db: AsyncSession = Depends(get_db), user_id: UUID = Depends(get_current_user_id)):
    res = await db.execute(select(Note).where(Note.user_id == user_id, Note.id == note_id))
    note = res.scalar_one_or_none()
    if not note:
        raise HTTPException(404, "Note not found")
    return {"id": str(note.id), "title": note.title, "content_json": note.content_json}

@router.post("/{note_id}/extract/start", response_model=StartExtractionOut)
async def start_extract_note_concepts(
    note_id: UUID,
    payload: StartExtractionIn,
    background_tasks: BackgroundTasks,
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
            "progress": int(note.extraction_progress or 0),
            "mode": note.extraction_mode or "normal",
        }

    mode = payload.mode or "normal"

    note.extraction_status = "queued"
    note.extraction_progress = 0
    note.extraction_mode = mode
    note.extraction_error = None
    note.extraction_started_at = None
    note.extraction_finished_at = None
    await db.commit()
    
    set_concept_job_status(
        str(note.id),
        {
            "note_id": str(note.id),
            "user_id": str(user_id),
            "status": "queued",
            "progress": 0,
            "mode": mode,
            "error": None,
            "started_at": None,
            "finished_at": None,
        },
    )

    background_tasks.add_task(
        concept_extraction_job,
        str(note.id),
        str(user_id),
        mode,
    )

    return {
        "message": "Extraction queued",
        "note_id": str(note.id),
        "status": "queued",
        "progress": 0,
        "mode": mode,
    }
    
@router.get("/{note_id}/extract/status", response_model=ExtractionStatusOut)
async def get_extract_note_status(
    note_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    job = get_concept_job_status(str(note_id))

    if job:
        if str(job.get("user_id")) != str(user_id):
            raise HTTPException(404, "Job not found")

        return {
            "note_id": str(note_id),
            "status": job.get("status", "idle"),
            "progress": int(job.get("progress", 0)),
            "mode": job.get("mode"),
            "error": job.get("error"),
            "started_at": job.get("started_at"),
            "finished_at": job.get("finished_at"),
        }

    # Fallback to persisted DB status if in-memory job state is missing.
    res = await db.execute(
        select(Note).where(Note.id == note_id, Note.user_id == user_id)
    )
    note = res.scalar_one_or_none()

    if not note:
        raise HTTPException(404, "Note not found")

    return {
        "note_id": str(note.id),
        "status": note.extraction_status or "idle",
        "progress": int(note.extraction_progress or 0),
        "mode": note.extraction_mode,
        "error": note.extraction_error,
        "started_at": note.extraction_started_at.isoformat() if note.extraction_started_at else None,
        "finished_at": note.extraction_finished_at.isoformat() if note.extraction_finished_at else None,
    }
