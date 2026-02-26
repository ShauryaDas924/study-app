
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from app.services.llm import embed_text
from app.db import get_db
from app.models import Note, Concept, NoteConcept
from app.services.auth import get_current_user_id
from app.services.llm import (
    extract_concepts_from_note,
    extract_math_concepts_from_note
)
from app.models import Flashcard
from datetime import datetime
from app.models import FlashcardState
from datetime import datetime, timezone
from pydantic import BaseModel
router = APIRouter(prefix="/notes", tags=["concepts"])
@router.post("/{note_id}/extract-concepts")
async def extract_concepts(note_id: UUID, mode: str = "general", db: AsyncSession = Depends(get_db), user_id: UUID = Depends(get_current_user_id)):
    res = await db.execute(select(Note).where(Note.id == note_id, Note.user_id == user_id))
    note = res.scalar_one_or_none()
    if not note:
        raise HTTPException(404, "Note not found")

    def flatten_note_json(content):
        if isinstance(content, dict):
            return " ".join(flatten_note_json(v) for v in content.values())
        if isinstance(content, list):
            return " ".join(flatten_note_json(v) for v in content)
        return str(content)

    note_text = flatten_note_json(note.content_json)
    if mode == "math":
        concepts = await extract_math_concepts_from_note(note_text)
    else:
        concepts = await extract_concepts_from_note(note_text)

    created = []
    for c in concepts:
        concept = Concept(
            user_id=note.user_id,
            class_id=note.class_id,
            name=c["name"],
            description=c.get("description"),
            definition=c.get("definition"),
            when_to_use=c.get("when_to_use"),
            pitfalls=c.get("pitfalls"),
        )
        

        text = f"""
        {concept.name}
        {concept.description or ""}
        {concept.definition or ""}
        {concept.when_to_use or ""}
        {concept.pitfalls or ""}
        """

        concept.embedding = embed_text(text)
        db.add(concept)
        await db.flush()

        link = NoteConcept(
            note_id=note.id,
            concept_id=concept.id,
            weight=float(c.get("confidence", 1.0))
        )
        db.add(link)
        

        
        # ⭐ AUTO FLASHCARD CREATION
        fc = Flashcard(
            user_id=note.user_id,
            class_id=note.class_id,
            concept_id=concept.id,
            question=f"What is {concept.name.replace('_',' ')}?",
            answer=concept.description or concept.definition or "No description",
            next_review=datetime.utcnow()
        )

        db.add(fc)
        created.append({"id": str(concept.id), "name": concept.name})

    await db.commit()
    return {"message": "Concepts extracted", "concepts": created}

@router.get("/concepts/by-class/{class_id}")
async def get_concepts_by_class(
    class_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    res = await db.execute(
        select(Concept).where(
            Concept.class_id == class_id,
            Concept.user_id == user_id
        )
    )

    concepts = res.scalars().all()

    return [
        {
            "id": str(c.id),
            "name": c.name,
            "description": c.description,
        }
        for c in concepts
    ]
    


@router.get("/flashcards/by-class/{class_id}")
async def flashcards_by_class(
    class_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):

    now = datetime.now(timezone.utc)

    # join Flashcard ↔ FlashcardState properly
    res = await db.execute(
        select(Flashcard)
        .outerjoin(
            FlashcardState,
            (FlashcardState.concept_id == Flashcard.concept_id)
            & (FlashcardState.user_id == user_id)
        )
        .where(
            Flashcard.user_id == user_id,
            Flashcard.class_id == class_id
        )
        .limit(200)
    )

    cards = res.scalars().all()

    return [
        {
            "id": str(c.id),
            "question": c.question,
            "answer": c.answer,
            "confidence": float(c.confidence)
        }
        for c in cards
    ]


class ReviewIn(BaseModel):
    rating: str  # "easy" | "medium" | "hard"

@router.post("/flashcards/{concept_id}/review")
async def review_flashcard(
    concept_id: UUID,
    payload: ReviewIn,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):
    fs = await db.get(
        FlashcardState,
        {"user_id": user_id, "concept_id": concept_id}
    )

    if not fs:
        raise HTTPException(404, "Flashcard not found")

    if payload.rating == "easy":
        fs.interval_days *= 2
    elif payload.rating == "medium":
        fs.interval_days = int(fs.interval_days * 1.5)
    else:
        fs.interval_days = 1

    fs.due_at = datetime.now(timezone.utc) + timedelta(days=fs.interval_days)
    fs.last_reviewed_at = datetime.now(timezone.utc)

    await db.commit()

    return {"ok": True}
