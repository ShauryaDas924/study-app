from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from uuid import UUID

from app.db import get_db
from app.models import Note
from app.services.auth import get_current_user_id

router = APIRouter(prefix="/notes", tags=["notes"])

class NoteIn(BaseModel):
    class_id: UUID
    title: str
    content_json: dict

@router.post("")
async def create_note(payload: NoteIn, db: AsyncSession = Depends(get_db), user_id: UUID = Depends(get_current_user_id)):
    obj = Note(user_id=user_id, class_id=payload.class_id, title=payload.title, content_json=payload.content_json)
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
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
