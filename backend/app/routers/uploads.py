


from app.models import Note
from fastapi import APIRouter, UploadFile, File, Form, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.services.llm import refine_notes
from app.models import Concept
from app.services.file_extraction import extract_text
from app.services.llm import (
    extract_concepts_from_note,
    generate_flashcards_from_concepts
)
from fastapi import Form, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.services.auth import get_current_user_id
from uuid import UUID
from app.models import Flashcard
from app.models import FlashcardState
from datetime import datetime
from sqlalchemy import select
router = APIRouter(prefix="/upload", tags=["upload"])




@router.post("/notes")
async def upload_note(
    file: UploadFile = File(...),
    class_id: UUID = Form(...),
    db: AsyncSession = Depends(get_db),
    user_id = Depends(get_current_user_id)
):
    content = await file.read()

    raw_text = await extract_text(file.filename, content)

    # Clean the notes with LLM
    text = await refine_notes(raw_text)
    
    # CREATE NOTE RECORD
    note = Note(
        user_id=user_id,
        class_id=class_id,
        title=file.filename,
        content_json={"text": text}
    )

    db.add(note)
    await db.flush()  # get note.id

    # 1️⃣ Extract concepts
    concepts = await extract_concepts_from_note(text)

    # 2️⃣ Save concepts AND keep IDs
    saved_concepts = []

    for c in concepts:
        existing_res = await db.execute(
            select(Concept).where(
                Concept.user_id == user_id,
                Concept.class_id == class_id,
                Concept.name == c["name"]
            )
        )

        existing_concept = existing_res.scalar_one_or_none()

        if existing_concept:
            saved_concepts.append(existing_concept)
            continue
            
        concept = Concept(
            user_id=user_id,
            class_id=class_id,
            name=c["name"],
            description=c["description"],
            evidence=c.get("evidence"),
            confidence=c.get("confidence", 0.5)
        )

        db.add(concept)
        await db.flush()  # ⭐ get DB id immediately
        saved_concepts.append(concept)

    # 3️⃣ Generate flashcards FROM ALL concepts at once

    all_flashcards = []

    for concept in saved_concepts:

        concept_payload = [{
            "name": concept.name,
            "description": concept.description,
            "evidence": concept.evidence or concept.description
        }]

        cards = await generate_flashcards_from_concepts(concept_payload)
    
        for fc in cards:
            all_flashcards.append((fc, concept))

    # 4️⃣ Save flashcards + SRS state
    for fc, concept in all_flashcards:

        existing_res = await db.execute(
            select(Flashcard).where(
                Flashcard.user_id == user_id,
                Flashcard.note_id == note.id,
                Flashcard.question == fc["question"]
            )
        )

        existing = existing_res.scalar_one_or_none()

        if existing:
            continue

        card = Flashcard(
            user_id=user_id,
            class_id=class_id,
            note_id=note.id,
            concept_id=concept.id,
            question=fc["question"],
            answer=fc["answer"]
        )

        db.add(card)
    
    # ⭐ Create ONE spaced repetition state per concept
    for concept in saved_concepts:

        existing_state = await db.get(
            FlashcardState,
            {"user_id": user_id, "concept_id": concept.id}
        )

        if not existing_state:
            db.add(
                FlashcardState(
                    user_id=user_id,
                    concept_id=concept.id,
                    due_at=datetime.utcnow()
                )
            )
        
    # 5️⃣ Commit once at end
    await db.commit()

    return {
        "note_id": str(note.id),
        "filename": file.filename,
        "concepts_saved": len(saved_concepts),
        "flashcards_saved": len(all_flashcards)
    }
