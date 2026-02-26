



from fastapi import APIRouter, UploadFile, File, Form, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
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
router = APIRouter(prefix="/upload", tags=["upload"])




@router.post("/notes")
async def upload_note(
    file: UploadFile = File(...),
    class_id: UUID = Form(...),
    db: AsyncSession = Depends(get_db),
    user_id = Depends(get_current_user_id)
):
    content = await file.read()
    text = await extract_text(file.filename, content)

    # 1️⃣ Extract concepts
    concepts = await extract_concepts_from_note(text)

    # 2️⃣ Save concepts AND keep IDs
    saved_concepts = []

    for c in concepts:
        concept = Concept(
            user_id=user_id,
            class_id=class_id,
            name=c["name"],
            description=c["description"],
            confidence=c.get("confidence", 0.5)
        )

        db.add(concept)
        await db.flush()  # ⭐ get DB id immediately
        saved_concepts.append(concept)

    # 3️⃣ Generate flashcards FROM saved concepts
    all_flashcards = []

    for concept in saved_concepts:
        cards = await generate_flashcards_from_concepts([
            {
                "name": concept.name,
                "description": concept.description
            }
        ])

        for fc in cards:
            all_flashcards.append((fc, concept))

    # 4️⃣ Save flashcards + SRS state
    for fc, concept in all_flashcards:

        card = Flashcard(
            user_id=user_id,
            class_id=class_id,
            concept_id=concept.id,  # ⭐ REQUIRED
            question=fc["question"],
            answer=fc["answer"],
            confidence=concept.confidence,
            next_review=datetime.utcnow()
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
        "filename": file.filename,
        "concepts_saved": len(saved_concepts),
        "flashcards_saved": len(all_flashcards)
    }
