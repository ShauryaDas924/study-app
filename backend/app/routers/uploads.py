


from app.models import Note
from fastapi import APIRouter, UploadFile, File, Form, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.services.llm import refine_notes
from app.models import Concept
from app.services.file_extraction import extract_text
from app.db import AsyncSessionLocal
from app.services.llm import (
    extract_concepts_from_note,
    extract_pitfalls_from_note,   # ✅ ADD
    attach_pitfalls_to_concepts, # ✅ ADD
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
    user_id = Depends(get_current_user_id)
):
    content = await file.read()

    # -------------------------
    # 🔥 STEP 1: NO DB YET
    # -------------------------
    raw_text = await extract_text(file.filename, content)
    text = await refine_notes(raw_text)

    # 1️⃣ Extract concepts
    concepts = await extract_concepts_from_note(text)

    # 1.5️⃣ Extract pitfalls
    try:
        pitfalls = await extract_pitfalls_from_note(text)
    except Exception as e:
        print("⚠️ PITFALL EXTRACTION FAILED:", e)
        pitfalls = []

    print("\n⚠️ PITFALLS EXTRACTED:\n", pitfalls)

    # 1.6️⃣ Attach pitfalls
    concepts = attach_pitfalls_to_concepts(concepts, pitfalls)

    print("\n🧠 CONCEPTS WITH PITFALLS:\n")
    for c in concepts:
        print({
            "name": c["name"],
            "pitfalls": c.get("pitfalls", [])
        })

    # -------------------------
    # 🔥 STEP 2: OPEN DB HERE
    # -------------------------
    async with AsyncSessionLocal() as db:

        # CREATE NOTE
        note = Note(
            user_id=user_id,
            class_id=class_id,
            title=file.filename,
            content_json={"text": text}
        )

        db.add(note)
        await db.flush()

        # 2️⃣ Save concepts
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
                definition=c.get("description"),
                when_to_use=c.get("when_to_use"),
                pitfalls="; ".join(c.get("pitfalls", [])) if c.get("pitfalls") else None,
                evidence=c.get("evidence"),
                confidence=c.get("confidence", 0.5)
            )

            db.add(concept)
            await db.flush()
            saved_concepts.append(concept)

        # -------------------------
        # 🔥 BUILD FULL PAYLOAD (ALL CONCEPTS TOGETHER)
        # -------------------------
        concept_payload = []

        for concept in saved_concepts:
            concept_payload.append({
                "name": concept.name,
                "description": concept.description,
                "definition": concept.definition,
                "when_to_use": concept.when_to_use,
                "evidence": concept.evidence or concept.description,
                "pitfalls": concept.pitfalls.split("; ") if concept.pitfalls else []
            })

        print("\n🔥 FULL FLASHCARD PAYLOAD:\n", concept_payload)
        print("\n🚨 FINAL CONCEPT PAYLOAD:")
        for c in concept_payload:
            print({
                "name": c["name"],
                "pitfalls": c["pitfalls"],
                "when_to_use": c["when_to_use"]
            })
        # -------------------------
        # 🔥 SINGLE LLM CALL
        # -------------------------
        cards = await generate_flashcards_from_concepts(concept_payload)
        print("\n🚨 RAW FLASHCARDS OUTPUT:\n", cards)
        print("🚨 COUNT:", len(cards))
        # -------------------------
        # 🔥 MAP CARDS BACK TO CONCEPTS
        # -------------------------
        all_flashcards = []

        for fc in cards:

            matched = None

            for concept in saved_concepts:
                if concept.name.replace("_", " ") in (
                    fc["question"] + " " + fc["answer"]
                ).lower():
                    matched = concept
                    break

            all_flashcards.append((fc, matched))

        # 4️⃣ Save flashcards
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

        # 5️⃣ SRS state
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

        await db.commit()

    return {
        "note_id": str(note.id),
        "filename": file.filename,
        "concepts_saved": len(saved_concepts),
        "flashcards_saved": len(all_flashcards)
    }
