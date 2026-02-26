
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from uuid import UUID
from sqlalchemy import delete
from app.models import Note, Concept, Mastery, NoteConcept
from app.db import get_db
from app.models import Flashcard
from app.models import Class
from app.services.auth import get_current_user_id
from app.models import Flashcard, FlashcardState
router = APIRouter(prefix="/classes", tags=["classes"])

class ClassIn(BaseModel):
    name: str
    term: str | None = None

@router.post("")
async def create_class(payload: ClassIn, db: AsyncSession = Depends(get_db), user_id: UUID = Depends(get_current_user_id)):
    obj = Class(user_id=user_id, name=payload.name, term=payload.term)
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return {"id": str(obj.id), "name": obj.name, "term": obj.term}

@router.get("")
async def list_classes(db: AsyncSession = Depends(get_db), user_id: UUID = Depends(get_current_user_id)):
    res = await db.execute(select(Class).where(Class.user_id == user_id))
    rows = res.scalars().all()
    return [{"id": str(c.id), "name": c.name, "term": c.term} for c in rows]

@router.delete("/{class_id}/clear")
async def clear_class_data(
    class_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    # 1️⃣ delete flashcards FIRST
    await db.execute(
        delete(Flashcard).where(
            Flashcard.user_id == user_id,
            Flashcard.class_id == class_id,
        )
    )

    # 2️⃣ delete flashcard states
    await db.execute(
        delete(FlashcardState).where(
            FlashcardState.user_id == user_id
        )
    )

    # 3️⃣ delete mastery
    await db.execute(
        delete(Mastery).where(
            Mastery.user_id == user_id
        )
    )

    # 4️⃣ delete note↔concept links
    await db.execute(delete(NoteConcept))

    # 5️⃣ delete concepts
    await db.execute(
        delete(Concept).where(
            Concept.user_id == user_id,
            Concept.class_id == class_id,
        )
    )

    # 6️⃣ delete notes
    await db.execute(
        delete(Note).where(
            Note.user_id == user_id,
            Note.class_id == class_id,
        )
    )

    await db.commit()

    return {"message": "Class data cleared"}
