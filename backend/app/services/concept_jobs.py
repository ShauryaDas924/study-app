import asyncio
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select

from app.db import AsyncSessionLocal
from app.models import Note, Concept, NoteConcept, Flashcard
from app.services.llm import (
    extract_concepts_from_note,
    extract_math_concepts_from_note,
    embed_text,
    generate_flashcards_from_concepts,
    generate_math_flashcards_from_concepts,
)


def concept_extraction_job(note_id: str, user_id: str, mode: str | None = None):
    print(f"[WORKER] starting note_id={note_id} mode={mode or 'normal'}")
    asyncio.run(
        run_concept_extraction_async(
            UUID(note_id),
            UUID(user_id),
            mode,
        )
    )
    print(f"[WORKER] finished note_id={note_id} mode={mode or 'normal'}")


async def run_concept_extraction_async(
    note_id: UUID,
    user_id: UUID,
    mode: str | None = None,
):
    async with AsyncSessionLocal() as db:
        note = await db.get(Note, note_id)

        if not note or note.user_id != user_id:
            return

        try:
            note.extraction_status = "running"
            note.extraction_progress = 5
            note.extraction_mode = mode or "normal"
            note.extraction_error = None
            note.extraction_started_at = datetime.now(timezone.utc)
            note.extraction_finished_at = None
            await db.commit()

            note_text = ""
            if isinstance(note.content_json, dict):
                note_text = note.content_json.get("text", "") or ""
            print(f"[WORKER] note title={note.title}")
            print(f"[WORKER] note_text_len={len(note_text)}")
            print(f"[WORKER] note_text_preview={note_text[:300]!r}")
            if not note_text.strip():
                note.extraction_status = "failed"
                note.extraction_progress = 0
                note.extraction_error = "Note text is empty."
                note.extraction_finished_at = datetime.now(timezone.utc)
                await db.commit()
                return

            note.extraction_progress = 15
            await db.commit()

            if mode == "math":
                extracted = await extract_math_concepts_from_note(note_text)
            else:
                extracted = await extract_concepts_from_note(note_text)
                
            print(f"[WORKER] extracted_count={len(extracted)}")
            if extracted:
                print(f"[WORKER] first_concept={extracted[0].get('name')}")
            note.extraction_progress = 55
            await db.commit()

            await db.execute(
                delete(NoteConcept).where(NoteConcept.note_id == note.id)
            )
            await db.execute(
                delete(Flashcard).where(Flashcard.note_id == note.id)
            )
            await db.commit()

            saved_concepts = []

            for item in extracted:
                name = (item.get("name") or "").strip()
                if not name:
                    continue

                existing = await db.execute(
                    select(Concept).where(
                        Concept.user_id == note.user_id,
                        Concept.class_id == note.class_id,
                        Concept.name == name,
                    )
                )
                concept = existing.scalar_one_or_none()

                if concept is None:
                    concept = Concept(
                        user_id=note.user_id,
                        class_id=note.class_id,
                        name=name,
                    )
                    db.add(concept)
                    await db.flush()

                concept.description = item.get("description")
                concept.evidence = item.get("evidence")
                concept.confidence = float(item.get("confidence", 0.5))
                concept.embedding = embed_text(
                    f"{name} {item.get('description', '')}"
                )

                saved_concepts.append(concept)

            await db.commit()
            print(f"[WORKER] saved_concepts_count={len(saved_concepts)}")
            note.extraction_progress = 72
            await db.commit()

            for concept in saved_concepts:
                db.add(
                    NoteConcept(
                        note_id=note.id,
                        concept_id=concept.id,
                        weight=1.0,
                    )
                )

            await db.commit()

            note.extraction_progress = 82
            await db.commit()

            concept_payloads = [
                {
                    "name": c.name,
                    "description": c.description,
                    "definition": c.definition,
                    "when_to_use": c.when_to_use,
                    "pitfalls": c.pitfalls,
                    "evidence": c.evidence,
                    "confidence": c.confidence,
                    "card_budget": 1,
                }
                for c in saved_concepts
            ]

            if mode == "math":
                cards = await generate_math_flashcards_from_concepts(concept_payloads)
            else:
                cards = await generate_flashcards_from_concepts(concept_payloads)
            print(f"[WORKER] cards_generated_count={len(cards)}")
            if cards:
                print(f"[WORKER] first_card_question={cards[0].get('question')}")
            note.extraction_progress = 92
            await db.commit()

            concept_by_name = {c.name: c for c in saved_concepts}

            for card in cards:
                question = (card.get("question") or "").strip()
                answer = (card.get("answer") or "").strip()

                if not question or not answer:
                    continue

                cname = card.get("concept_name")
                linked_concept = concept_by_name.get(cname)

                db.add(
                    Flashcard(
                        user_id=note.user_id,
                        class_id=note.class_id,
                        note_id=note.id,
                        concept_id=linked_concept.id if linked_concept else None,
                        question=question,
                        answer=answer,
                        confidence=float(card.get("confidence", 0.5)),
                    )
                )

            await db.commit()
            print("[WORKER] marking extraction completed")
            note.extraction_status = "completed"
            note.extraction_progress = 100
            note.extraction_error = None
            note.extraction_finished_at = datetime.now(timezone.utc)
            await db.commit()

        except Exception as e:
            note = await db.get(Note, note_id)
            if note:
                note.extraction_status = "failed"
                note.extraction_error = str(e)
                note.extraction_finished_at = datetime.now(timezone.utc)
                await db.commit()
            raise
