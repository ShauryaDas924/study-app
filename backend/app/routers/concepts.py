
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import StreamingResponse
import csv
import io
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from uuid import UUID
from app.services.llm import embed_text
from app.db import get_db
from app.services.llm import client
from app.models import Note, Concept, NoteConcept, Flashcard, FlashcardState, Mastery, FlashcardSession
from app.services.auth import get_current_user_id
from app.services.llm import (
    extract_concepts_from_note,
    extract_math_concepts_from_note
)
from app.services.llm import classify_concept_role, assign_card_budget
from app.services.llm import (
    generate_flashcards_from_concepts,
    generate_math_flashcards_from_concepts
)
from datetime import timedelta

from datetime import datetime
from datetime import datetime, timezone
from pydantic import BaseModel
router = APIRouter(prefix="/notes", tags=["concepts"])
@router.post("/{note_id}/extract-concepts")
async def extract_concepts(
    note_id: UUID,
    mode: str = "general",
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    res = await db.execute(
        select(Note).where(Note.id == note_id, Note.user_id == user_id)
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
    note.extraction_mode = "math" if mode == "math" else "normal"
    note.extraction_error = None
    note.extraction_started_at = datetime.now(timezone.utc)
    note.extraction_finished_at = None
    await db.commit()

    from app.services.queue import concept_queue
    job = concept_queue.enqueue(
        "app.services.concept_jobs.concept_extraction_job",
        str(note.id),
        str(user_id),
        "math" if mode == "math" else None,
        job_timeout="60m",
    )

    return {
        "message": "Extraction queued",
        "note_id": str(note.id),
        "status": "queued",
        "progress": 0,
        "mode": note.extraction_mode,
        "job_id": job.id,
    }

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
    res = await db.execute(
        select(Flashcard)
        .where(
            Flashcard.user_id == user_id,
            Flashcard.class_id == class_id
        )
        .order_by(Flashcard.created_at.desc())
        .limit(500)
    )
    cards = res.scalars().all()

    return [
        {
            "id": str(c.id),
            "question": c.question,
            "answer": c.answer,
            "confidence": float(c.confidence or 0.5),
            "note_id": str(c.note_id) if getattr(c, "note_id", None) else None,
        }
        for c in cards
    ]


@router.get("/flashcards/by-note/{note_id}")
async def flashcards_by_note(
    note_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    # Get note (we need its class_id for fallback)
    note_res = await db.execute(
        select(Note).where(Note.id == note_id, Note.user_id == user_id)
    )
    note = note_res.scalar_one_or_none()
    if not note:
        raise HTTPException(404, "Note not found")

    # 1) NEW system: flashcards stamped with note_id
    res = await db.execute(
        select(Flashcard)
        .where(
            Flashcard.user_id == user_id,
            Flashcard.note_id == note_id
        )
        .order_by(Flashcard.created_at.desc())
        .limit(500)
    )
    cards = res.scalars().all()

    # 2) Old-but-linkable: concept_id ↔ note_concepts
    if not cards:
        res2 = await db.execute(
            select(Flashcard)
            .join(NoteConcept, NoteConcept.concept_id == Flashcard.concept_id)
            .where(
                Flashcard.user_id == user_id,
                NoteConcept.note_id == note_id
            )
            .order_by(Flashcard.created_at.desc())
            .limit(500)
        )
        cards = res2.scalars().all()

    # 3) HARD fallback: legacy unassigned cards for this class
    # This is the key fix for "I have flashcards but by-note is empty".
    if not cards:
        res3 = await db.execute(
            select(Flashcard)
            .where(
                Flashcard.user_id == user_id,
                Flashcard.class_id == note.class_id,
                Flashcard.note_id.is_(None)   # legacy/unassigned
            )
            .order_by(Flashcard.created_at.desc())
            .limit(500)
        )
        cards = res3.scalars().all()

    return [
        {
            "id": str(c.id),
            "question": c.question,
            "answer": c.answer,
            "confidence": float(c.confidence or 0.5),
            "note_id": str(c.note_id) if getattr(c, "note_id", None) else None,
        }
        for c in cards
    ]


@router.get("/flashcards/export-by-note/{note_id}")
async def export_flashcards_csv_by_note(
    note_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    # Get note for class fallback
    note_res = await db.execute(
        select(Note).where(Note.id == note_id, Note.user_id == user_id)
    )
    note = note_res.scalar_one_or_none()
    if not note:
        raise HTTPException(404, "Note not found")

    # 1) new way
    res = await db.execute(
        select(Flashcard)
        .where(
            Flashcard.user_id == user_id,
            Flashcard.note_id == note_id
        )
        .order_by(Flashcard.created_at.desc())
    )
    cards = res.scalars().all()

    # 2) old concept-linked
    if not cards:
        res2 = await db.execute(
            select(Flashcard)
            .join(NoteConcept, NoteConcept.concept_id == Flashcard.concept_id)
            .where(
                Flashcard.user_id == user_id,
                NoteConcept.note_id == note_id
            )
            .order_by(Flashcard.created_at.desc())
        )
        cards = res2.scalars().all()

    # 3) legacy unassigned
    if not cards:
        res3 = await db.execute(
            select(Flashcard)
            .where(
                Flashcard.user_id == user_id,
                Flashcard.class_id == note.class_id,
                Flashcard.note_id.is_(None)
            )
            .order_by(Flashcard.created_at.desc())
        )
        cards = res3.scalars().all()

    if not cards:
        raise HTTPException(404, "No flashcards found")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Question", "Answer", "Confidence"])

    for c in cards:
        writer.writerow([c.question, c.answer, float(c.confidence or 0.5)])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=flashcards_{note_id}.csv"},
    )
    
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
    # -------- UPDATE MASTERY --------

    m = await db.get(
        Mastery,
        {"user_id": user_id, "concept_id": concept_id}
    )

    if m:
        if payload.rating == "easy":
            m.mastery_prob = min(0.95, m.mastery_prob + 0.05)
        elif payload.rating == "medium":
            m.mastery_prob = min(0.95, m.mastery_prob + 0.02)
        else:
            m.mastery_prob = max(0.05, m.mastery_prob - 0.07)
    await db.commit()

    return {"ok": True}


@router.get("/flashcards/session/{note_id}")
async def get_flashcard_session(
    note_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):
    session = await db.get(
        FlashcardSession,
        {"user_id": user_id, "note_id": note_id}
    )

    if not session:
        return {
            "index": 0,
            "mode": "normal",
            "deck_ids": [],
            "all_deck_ids": [],
            "hard_ids": [],
            "medium_ids": [],
        }

    return {
        "index": session.current_index,
        "mode": session.mode or "normal",
        "deck_ids": session.deck_ids or [],
        "all_deck_ids": session.all_deck_ids or [],
        "hard_ids": session.hard_ids or [],
        "medium_ids": session.medium_ids or [],
    }
    


class SessionUpdate(BaseModel):
    index: int
    mode: str | None = "normal"
    deck_ids: list[str] = Field(default_factory=list)
    all_deck_ids: list[str] = Field(default_factory=list)
    hard_ids: list[str] = Field(default_factory=list)
    medium_ids: list[str] = Field(default_factory=list)


@router.post("/flashcards/session/{note_id}")
async def update_flashcard_session(
    note_id: UUID,
    payload: SessionUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):
    stmt = insert(FlashcardSession).values(
        user_id=user_id,
        note_id=note_id,
        current_index=payload.index,
        mode=payload.mode,
        deck_ids=payload.deck_ids,
        all_deck_ids=payload.all_deck_ids,
        hard_ids=payload.hard_ids,
        medium_ids=payload.medium_ids,
    )

    stmt = stmt.on_conflict_do_update(
        index_elements=["user_id", "note_id"],
        set_={
            "current_index": payload.index,
            "mode": payload.mode,
            "deck_ids": payload.deck_ids,
            "all_deck_ids": payload.all_deck_ids,
            "hard_ids": payload.hard_ids,
            "medium_ids": payload.medium_ids,
            "updated_at": func.now(),
        }
    )

    await db.execute(stmt)
    await db.commit()

    return {"ok": True}

@router.delete("/flashcards/session/{note_id}")
async def clear_flashcard_session(
    note_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):
    session = await db.get(
        FlashcardSession,
        {"user_id": user_id, "note_id": note_id}
    )

    if session:
        await db.delete(session)
        await db.commit()

    return {"ok": True}
