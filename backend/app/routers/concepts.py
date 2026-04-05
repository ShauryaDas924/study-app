
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
async def extract_concepts(note_id: UUID, mode: str = "general", db: AsyncSession = Depends(get_db), user_id: UUID = Depends(get_current_user_id)):
    res = await db.execute(select(Note).where(Note.id == note_id, Note.user_id == user_id))
    note = res.scalar_one_or_none()
    if not note:
        raise HTTPException(404, "Note not found")

    def flatten_note_json(content):
        if isinstance(content, dict):
            parts = [flatten_note_json(v) for v in content.values()]
            return "\n".join(p for p in parts if p)
        if isinstance(content, list):
            parts = [flatten_note_json(v) for v in content]
            return "\n".join(p for p in parts if p)
        return str(content).strip()

    note_text = flatten_note_json(note.content_json)
    if mode == "math":
        concepts = await extract_math_concepts_from_note(note_text)
    else:
        concepts = await extract_concepts_from_note(note_text)
    
    enriched_concepts = []

    for c in concepts:
        pitfall_resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": "List one common exam mistake students make with this concept. Ground it in the provided evidence. One short sentence."
                },
                {
                    "role": "user",
                    "content": f"Concept: {c['name']}\nDescription: {c.get('description','')}\nEvidence: {c.get('evidence','')}"
                }
            ],
            temperature=0.2
        )
        pitfall_text = pitfall_resp.choices[0].message.content.strip()

        when_resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Explain when this concept should be used on an exam or in a problem. One short grounded sentence."
                },
                {
                    "role": "user",
                    "content": f"Concept: {c['name']}\nDescription: {c.get('description','')}\nEvidence: {c.get('evidence','')}"
                }
            ],
            temperature=0.2
        )
        when_text = when_resp.choices[0].message.content.strip()

        enriched_concepts.append({
            "name": c["name"],
            "description": c.get("description"),
            "definition": c.get("description"),
            "when_to_use": when_text,
            "pitfalls": pitfall_text,
            "evidence": c.get("evidence"),
            "confidence": float(c.get("confidence", 0.5)),
            "exam_priority_locked": c.get("exam_priority_locked", False),
        })
    created = []
    existing_names_res = await db.execute(
        select(Concept.name).where(
            Concept.user_id == note.user_id,
            Concept.class_id == note.class_id
        )
    )

    existing_names = {r[0].lower() for r in existing_names_res.fetchall()}


    for c in enriched_concepts:

        if c["name"].lower() in existing_names:
            existing_concept_res = await db.execute(
                select(Concept).where(
                    Concept.name.ilike(c["name"]),
                    Concept.user_id == note.user_id,
                    Concept.class_id == note.class_id
                )
            )
            concept = existing_concept_res.scalars().first()

            if concept:
                new_desc = c.get("description")
                new_evidence = c.get("evidence")
                new_conf = float(c.get("confidence", concept.confidence or 0.5))

                # Refresh description/definition if new one is stronger
                if new_desc and (
                    not concept.description or
                    len(new_desc) > len(concept.description or "")
                ):
                    concept.description = new_desc
                    concept.definition = new_desc

                # Always refresh evidence if new evidence exists
                if new_evidence:
                    concept.evidence = new_evidence

                # Keep strongest confidence seen so far
                concept.confidence = max(float(concept.confidence or 0.5), new_conf)

                # Refresh pitfall with grounded context
                concept.pitfalls = c.get("pitfalls")
                concept.when_to_use = c.get("when_to_use")

            # Avoid duplicate note-concept links
            existing_link = await db.execute(
                select(NoteConcept).where(
                    NoteConcept.note_id == note.id,
                    NoteConcept.concept_id == concept.id
                )
            )
            if not existing_link.scalar_one_or_none():
                db.add(
                    NoteConcept(
                        note_id=note.id,
                        concept_id=concept.id,
                        weight=float(c.get("confidence", 1.0))
                    )
                )

            continue

        
        
        concept = Concept(
            user_id=note.user_id,
            class_id=note.class_id,
            name=c["name"],
            description=c.get("description"),
            definition=c.get("definition"),
            when_to_use=c.get("when_to_use"),
            pitfalls=c.get("pitfalls"),
            confidence=float(c.get("confidence", 0.5)),
            evidence=c.get("evidence")
        )

        db.add(concept)
        await db.flush()

        text = f"""
        {concept.name}
        {concept.description or ""}
        {concept.definition or ""}
        """

        concept.embedding = embed_text(text)

        link = NoteConcept(
            note_id=note.id,
            concept_id=concept.id,
            weight=float(c.get("confidence", 1.0))
        )

        db.add(link)
        created.append({"id": str(concept.id), "name": concept.name})
    # -------- SMART FLASHCARD GENERATION --------
    concept_payloads = []

    concept_rows = await db.execute(
        select(Concept)
        .join(NoteConcept, NoteConcept.concept_id == Concept.id)
        .where(
            Concept.user_id == note.user_id,
            Concept.class_id == note.class_id,
            NoteConcept.note_id == note.id
        )
    )

    linked_concepts = concept_rows.scalars().all()

    for concept in linked_concepts:
        concept_payloads.append({
            "name": concept.name,
            "description": concept.description,
            "definition": concept.definition,
            "when_to_use": concept.when_to_use,
            "pitfalls": concept.pitfalls,
            "evidence": concept.evidence,
            "confidence": float(concept.confidence or 0.5),
        })
    
    if concept_payloads:

        if mode == "math":
            flashcards = await generate_math_flashcards_from_concepts(concept_payloads)
        else:
            flashcards = await generate_flashcards_from_concepts(concept_payloads)

        # get created concept objects
        concept_lookup = {}

        for c in enriched_concepts:
            res = await db.execute(
                select(Concept.id).where(
                    Concept.name.ilike(c["name"]),
                    Concept.class_id == note.class_id,
                    Concept.user_id == note.user_id
                )
            )
            cid = res.scalar()
            if cid:
                concept_lookup[c["name"]] = cid
                
        existing_flashcards_res = await db.execute(
            select(Flashcard.question).where(
                Flashcard.user_id == note.user_id,
                Flashcard.note_id == note.id
            )
        )
        existing_flashcard_questions = {
            row[0].strip().lower() for row in existing_flashcards_res.fetchall()
        }
        for card in flashcards:
            q_key = card.get("question", "").strip().lower()
            if not q_key or q_key in existing_flashcard_questions:
                continue

            matched_concept_id = concept_lookup.get(card.get("concept_name"))

            if not matched_concept_id:
                for name, cid in concept_lookup.items():
                    if name.replace("_", " ") in (
                        (card.get("question", "") + " " + card.get("answer", "")).lower()
                    ):
                        matched_concept_id = cid
                        break

            fc = Flashcard(
                user_id=note.user_id,
                class_id=note.class_id,
                note_id=note.id,
                concept_id=matched_concept_id,   # ⭐ important fix
                question=card["question"],
                answer=card["answer"],
                confidence=float(card.get("confidence", 0.7)),
                next_review=datetime.utcnow()
            )

            db.add(fc)
            existing_flashcard_questions.add(q_key)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
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
