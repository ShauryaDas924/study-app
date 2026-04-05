


from app.models import Note
from fastapi import APIRouter, UploadFile, File, Form, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.services.llm import refine_notes
from app.models import Concept
from app.models import NoteConcept
from app.services.file_extraction import extract_text
from app.services.llm import (
    extract_concepts_from_note,
    generate_flashcards_from_concepts,
    client
)
from app.services.llm import classify_concept_role, assign_card_budget
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
    
    

    # 1️⃣ Extract concepts
    concepts = await extract_concepts_from_note(text)
    
    enriched_concepts = []

    for c in concepts:
        pitfall_resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": "List one common exam mistake students make with this concept. One short sentence."
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
            "confidence": float(c.get("confidence", 0.5))
        })
        
    # CREATE NOTE RECORD
    note = Note(
        user_id=user_id,
        class_id=class_id,
        title=file.filename,
        content_json={"text": text}
    )

    db.add(note)
    await db.flush()  # get note.id
    # 2️⃣ Save concepts AND keep IDs
    saved_concepts = []

    for c in enriched_concepts:
        existing_res = await db.execute(
            select(Concept).where(
                Concept.user_id == user_id,
                Concept.class_id == class_id,
                Concept.name == c["name"]
            )
        )

        existing_concept = existing_res.scalar_one_or_none()

        if existing_concept:
            link_res = await db.execute(
                select(NoteConcept).where(
                    NoteConcept.note_id == note.id,
                    NoteConcept.concept_id == existing_concept.id
                )
            )
            existing_link = link_res.scalar_one_or_none()
            existing_concept.description = c.get("description") or existing_concept.description
            existing_concept.definition = c.get("definition") or existing_concept.definition
            existing_concept.when_to_use = c.get("when_to_use") or existing_concept.when_to_use
            existing_concept.pitfalls = c.get("pitfalls") or existing_concept.pitfalls
            existing_concept.evidence = c.get("evidence") or existing_concept.evidence
            existing_concept.confidence = max(
                float(existing_concept.confidence or 0.5),
                float(c.get("confidence", 0.5))
            )   
            if not existing_link:
                db.add(
                    NoteConcept(
                        note_id=note.id,
                        concept_id=existing_concept.id,
                        weight=float(c.get("confidence", 0.5))
                    )
                )

            saved_concepts.append(existing_concept)
            continue
        
        
        
        concept = Concept(
            user_id=user_id,
            class_id=class_id,
            name=c["name"],
            description=c["description"],
            definition=c.get("definition"),
            when_to_use=c.get("when_to_use"),
            pitfalls=c.get("pitfalls"),
            evidence=c.get("evidence"),
            confidence=float(c.get("confidence", 0.5))
        )

        db.add(concept)
        await db.flush()  # ⭐ get DB id immediately
        saved_concepts.append(concept)
        
        db.add(
            NoteConcept(
                note_id=note.id,
                concept_id=concept.id,
                weight=float(c.get("confidence", 0.5))
            )
        )
        
    # 3️⃣ Generate flashcards FROM ALL concepts at once
    concept_payloads = []
    concept_lookup = {}

    for concept in saved_concepts:
        payload = {
            "name": concept.name,
            "description": concept.description,
            "definition": concept.definition,
            "when_to_use": getattr(concept, "when_to_use", None),
            "pitfalls": getattr(concept, "pitfalls", None),
            "evidence": concept.evidence or concept.description,
            "confidence": float(concept.confidence or 0.5),
        }
        payload["role"] = classify_concept_role(payload)
        payload["card_budget"] = assign_card_budget(payload)
        concept_payloads.append(payload)
        concept_lookup[concept.name] = concept

    generated_flashcards = await generate_flashcards_from_concepts(concept_payloads)

    all_flashcards = []
    for fc in generated_flashcards:
        linked_concept = concept_lookup.get(fc.get("concept_name"))
        if linked_concept:
            all_flashcards.append((fc, linked_concept))
            
    saved_flashcard_count = 0
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
        saved_flashcard_count += 1
        
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
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return {
        "note_id": str(note.id),
        "filename": file.filename,
        "concepts_saved": len(saved_concepts),
        "flashcards_saved": saved_flashcard_count
    }
