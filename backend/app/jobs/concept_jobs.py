from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.db import AsyncSessionLocal
from app.models import (
    Note,
    Concept,
    NoteConcept,
    Flashcard,
)
from app.services.llm import (
    embed_text,
    client,
    extract_concepts_from_note,
    extract_math_concepts_from_note,
    classify_concept_role,
    assign_card_budget,
    generate_flashcards_from_concepts,
    generate_math_flashcards_from_concepts,
)


async def concept_extraction_job(note_id: str, user_id: str, mode: str | None = None):
    print(f"[concept_job] START note_id={note_id} user_id={user_id} mode={mode}")
    await run_concept_extraction_async(
        UUID(note_id),
        UUID(user_id),
        mode,
    )
    print(f"[concept_job] END note_id={note_id}")


def flatten_note_json(content):
    if isinstance(content, dict):
        parts = [flatten_note_json(v) for v in content.values()]
        return "\n".join(p for p in parts if p)
    if isinstance(content, list):
        parts = [flatten_note_json(v) for v in content]
        return "\n".join(p for p in parts if p)
    return str(content).strip()


async def set_progress(
    db,
    note: Note,
    *,
    status: str | None = None,
    progress: int | None = None,
    error: str | None = None,
    started: bool = False,
    finished: bool = False,
    mode: str | None = None,
):
    if status is not None:
        note.extraction_status = status
    if progress is not None:
        note.extraction_progress = progress
    if error is not None:
        note.extraction_error = error
    if mode is not None:
        note.extraction_mode = mode
    if started:
        note.extraction_started_at = datetime.now(timezone.utc)
        note.extraction_finished_at = None
    if finished:
        note.extraction_finished_at = datetime.now(timezone.utc)

    await db.commit()
    print(
        f"[concept_job] note_id={note.id} status={note.extraction_status} "
        f"progress={note.extraction_progress} mode={note.extraction_mode} "
        f"error={note.extraction_error}"
    )

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
            await set_progress(
                db,
                note,
                status="running",
                progress=5,
                error=None,
                started=True,
                mode=mode or "normal",
            )

            note_text = flatten_note_json(note.content_json)
            if not note_text.strip():
                await set_progress(
                    db,
                    note,
                    status="failed",
                    progress=0,
                    error="Note text is empty.",
                    finished=True,
                )
                return

            await set_progress(db, note, progress=12)

            # 1) base extraction
            if mode == "math":
                concepts = await extract_math_concepts_from_note(note_text)
            else:
                concepts = await extract_concepts_from_note(note_text)

            await set_progress(db, note, progress=28)

            # 2) enrichment (same behavior as old route)
            enriched_concepts = []

            for idx, c in enumerate(concepts):
                pitfall_resp = await run_in_threadpool(
                    client.chat.completions.create,
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
                    temperature=0.2,
                )
                pitfall_text = pitfall_resp.choices[0].message.content.strip()

                when_resp = await run_in_threadpool(
                    client.chat.completions.create,
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
                    temperature=0.2,
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

                # smoothly move 28 -> 48 during enrichment
                if len(concepts) > 0:
                    step_progress = 28 + int(((idx + 1) / len(concepts)) * 20)
                    note.extraction_progress = step_progress
                    await db.commit()

            await set_progress(db, note, progress=50)

            # 3) save / update concepts exactly like old route
            existing_names_res = await db.execute(
                select(Concept.name).where(
                    Concept.user_id == note.user_id,
                    Concept.class_id == note.class_id
                )
            )
            existing_names = {r[0].lower() for r in existing_names_res.fetchall()}

            created = []

            for idx, c in enumerate(enriched_concepts):
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

                        if new_desc and (
                            not concept.description or
                            len(new_desc) > len(concept.description or "")
                        ):
                            concept.description = new_desc
                            concept.definition = new_desc

                        if new_evidence:
                            concept.evidence = new_evidence

                        concept.confidence = max(float(concept.confidence or 0.5), new_conf)
                        concept.pitfalls = c.get("pitfalls")
                        concept.when_to_use = c.get("when_to_use")

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

                    if len(enriched_concepts) > 0:
                        step_progress = 50 + int(((idx + 1) / len(enriched_concepts)) * 20)
                        note.extraction_progress = step_progress
                        await db.commit()
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

                concept.embedding = await run_in_threadpool(embed_text, text)

                db.add(
                    NoteConcept(
                        note_id=note.id,
                        concept_id=concept.id,
                        weight=float(c.get("confidence", 1.0))
                    )
                )

                created.append({"id": str(concept.id), "name": concept.name})

                if len(enriched_concepts) > 0:
                    step_progress = 50 + int(((idx + 1) / len(enriched_concepts)) * 20)
                    note.extraction_progress = step_progress
                    await db.commit()

            await db.commit()
            await set_progress(db, note, progress=72)

            # 4) build concept payloads exactly like old route
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

            concept_payloads = []
            for concept in linked_concepts:
                payload = {
                    "name": concept.name,
                    "description": concept.description,
                    "definition": concept.definition,
                    "when_to_use": concept.when_to_use,
                    "pitfalls": concept.pitfalls,
                    "evidence": concept.evidence,
                    "confidence": float(concept.confidence or 0.5),
                }
                payload["role"] = classify_concept_role(payload)
                payload["card_budget"] = assign_card_budget(payload)
                if payload["card_budget"] > 0:
                    concept_payloads.append(payload)

            concept_payloads.sort(
                key=lambda x: (
                    x.get("card_budget", 0),
                    x.get("confidence", 0.0),
                ),
                reverse=True
            )

            await set_progress(db, note, progress=80)

            # 5) generate flashcards
            if concept_payloads:
                if mode == "math":
                    flashcards = await generate_math_flashcards_from_concepts(concept_payloads)
                else:
                    flashcards = await generate_flashcards_from_concepts(concept_payloads)
            else:
                flashcards = []

            await set_progress(db, note, progress=90)

            # 6) save flashcards exactly like old route
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

            for idx, card in enumerate(flashcards):
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
                    concept_id=matched_concept_id,
                    question=card["question"],
                    answer=card["answer"],
                    confidence=float(card.get("confidence", 0.7)),
                    next_review=datetime.now(timezone.utc)
                )
                db.add(fc)
                existing_flashcard_questions.add(q_key)

                if len(flashcards) > 0:
                    step_progress = 90 + int(((idx + 1) / len(flashcards)) * 9)
                    note.extraction_progress = step_progress
                    await db.commit()

            await db.commit()

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
