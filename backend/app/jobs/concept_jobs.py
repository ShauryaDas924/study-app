import asyncio
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
    extract_concepts_from_note,
    extract_math_concepts_from_note,
    classify_concept_role,
    assign_card_budget,
    generate_flashcards_from_concepts,
    generate_math_flashcards_from_concepts,
    ground_flashcards_against_lecture,
    flashcards_too_similar,
)

CONCEPT_JOBS: dict[str, dict] = {}

# Bulletproof guard: only one heavy extraction job at once.
# Raise to 2 later only if your DB/API can handle it.
CONCEPT_EXTRACTION_SEMAPHORE = asyncio.Semaphore(1)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def set_concept_job_status(note_id: str, patch: dict):
    existing = CONCEPT_JOBS.get(note_id, {})
    existing.update(patch)
    CONCEPT_JOBS[note_id] = existing


def get_concept_job_status(note_id: str) -> dict | None:
    return CONCEPT_JOBS.get(note_id)


async def concept_extraction_job(note_id: str, user_id: str, mode: str | None = None):
    print(f"[concept_job] START note_id={note_id} user_id={user_id} mode={mode}")

    async with CONCEPT_EXTRACTION_SEMAPHORE:
        await run_concept_extraction_async(
            UUID(note_id),
            UUID(user_id),
            mode or "normal",
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

def pitfalls_to_db(value) -> str:
    if value is None:
        return ""

    if isinstance(value, list):
        return "; ".join(str(x).strip() for x in value if str(x).strip())

    return str(value).strip()


def pitfalls_from_db(value) -> list[str]:
    if not value:
        return []

    if isinstance(value, list):
        return value

    return [
        part.strip()
        for part in str(value).split(";")
        if part.strip()
    ]


async def run_concept_extraction_async(
    note_id: UUID,
    user_id: UUID,
    mode: str | None = None,
):
    note_key = str(note_id)
    mode = mode or "normal"

    set_concept_job_status(
        note_key,
        {
            "note_id": note_key,
            "user_id": str(user_id),
            "status": "running",
            "progress": 5,
            "mode": mode,
            "error": None,
            "started_at": now_iso(),
            "finished_at": None,
        },
    )

    try:
        # --------------------------------------------------
        # STEP 1: read note quickly, then close DB session
        # --------------------------------------------------
        async with AsyncSessionLocal() as db:
            res = await db.execute(
                select(Note).where(
                    Note.id == note_id,
                    Note.user_id == user_id,
                )
            )
            note = res.scalar_one_or_none()

            if not note:
                set_concept_job_status(
                    note_key,
                    {
                        "status": "failed",
                        "progress": 100,
                        "error": "Note not found",
                        "finished_at": now_iso(),
                    },
                )
                return

            note_text = flatten_note_json(note.content_json)
            class_id = note.class_id

            note.extraction_status = "running"
            note.extraction_progress = 5
            note.extraction_mode = mode
            note.extraction_error = None
            note.extraction_started_at = datetime.now(timezone.utc)
            note.extraction_finished_at = None
            await db.commit()

        # DB is closed here.

        if not note_text.strip():
            async with AsyncSessionLocal() as db:
                res = await db.execute(
                    select(Note).where(Note.id == note_id, Note.user_id == user_id)
                )
                note = res.scalar_one_or_none()
                if note:
                    note.extraction_status = "failed"
                    note.extraction_progress = 100
                    note.extraction_error = "Note text is empty."
                    note.extraction_finished_at = datetime.now(timezone.utc)
                    await db.commit()

            set_concept_job_status(
                note_key,
                {
                    "status": "failed",
                    "progress": 100,
                    "error": "Note text is empty.",
                    "finished_at": now_iso(),
                },
            )
            return

        # --------------------------------------------------
        # STEP 2: LLM concept extraction with NO DB open
        # --------------------------------------------------
        set_concept_job_status(note_key, {"progress": 15})

        if mode == "math":
            concepts = await extract_math_concepts_from_note(note_text)
        else:
            concepts = await extract_concepts_from_note(note_text)

        set_concept_job_status(note_key, {"progress": 45})

        # --------------------------------------------------
        # STEP 3: enrich without extra LLM calls
        # --------------------------------------------------
        enriched_concepts = []

        for c in concepts:
            pitfalls = c.get("pitfalls") or []
            when_text = c.get("when_to_use") or ""

            enriched_concepts.append({
                "name": c["name"],
                "type": c.get("type", ""),
                "description": c.get("description"),
                "definition": c.get("definition") or c.get("description") or "",
                "when_to_use": when_text,
                "pitfalls": pitfalls,
                "related_concepts": c.get("related_concepts", []),
                "evidence": c.get("evidence"),
                "confidence": float(c.get("confidence", 0.5)),
                "exam_priority_locked": c.get("exam_priority_locked", False),
            })

        # --------------------------------------------------
        # STEP 4: precompute embeddings with NO DB open
        # --------------------------------------------------
        set_concept_job_status(note_key, {"progress": 52})

        embedding_map: dict[str, list[float] | None] = {}

        for c in enriched_concepts:
            text = f"""
            {c.get("name", "")}
            {c.get("description", "") or ""}
            {c.get("definition", "") or ""}
            """

            try:
                embedding_map[c["name"]] = await run_in_threadpool(embed_text, text)
            except Exception as e:
                print(f"⚠️ embedding failed for concept {c.get('name')}: {e}")
                embedding_map[c["name"]] = None

        # --------------------------------------------------
        # STEP 5: write concepts quickly
        # --------------------------------------------------
        set_concept_job_status(note_key, {"progress": 60})

        async with AsyncSessionLocal() as db:
            existing_names_res = await db.execute(
                select(Concept.name).where(
                    Concept.user_id == user_id,
                    Concept.class_id == class_id,
                )
            )
            existing_names = {r[0].lower() for r in existing_names_res.fetchall()}

            for c in enriched_concepts:
                concept = None

                if c["name"].lower() in existing_names:
                    existing_concept_res = await db.execute(
                        select(Concept).where(
                            Concept.name.ilike(c["name"]),
                            Concept.user_id == user_id,
                            Concept.class_id == class_id,
                        )
                    )
                    concept = existing_concept_res.scalars().first()

                    if concept:
                        new_desc = c.get("description")
                        new_evidence = c.get("evidence")
                        new_conf = float(c.get("confidence", concept.confidence or 0.5))

                        if new_desc and (
                            not concept.description
                            or len(new_desc) > len(concept.description or "")
                        ):
                            concept.description = new_desc
                            concept.definition = c.get("definition") or new_desc

                        if new_evidence:
                            concept.evidence = new_evidence

                        concept.confidence = max(float(concept.confidence or 0.5), new_conf)
                        concept.pitfalls = pitfalls_to_db(c.get("pitfalls"))
                        concept.when_to_use = c.get("when_to_use")

                        if hasattr(concept, "type"):
                            concept.type = c.get("type", "") or getattr(concept, "type", "")

                        if hasattr(concept, "related_concepts"):
                            concept.related_concepts = c.get("related_concepts", []) or []

                if not concept:
                    concept_kwargs = dict(
                        user_id=user_id,
                        class_id=class_id,
                        name=c["name"],
                        description=c.get("description"),
                        definition=c.get("definition") or c.get("description") or "",
                        when_to_use=c.get("when_to_use"),
                        pitfalls=pitfalls_to_db(c.get("pitfalls")),
                        confidence=float(c.get("confidence", 0.5)),
                        evidence=c.get("evidence"),
                        embedding=embedding_map.get(c["name"]),
                    )

                    if hasattr(Concept, "type"):
                        concept_kwargs["type"] = c.get("type", "")

                    if hasattr(Concept, "related_concepts"):
                        concept_kwargs["related_concepts"] = c.get("related_concepts", [])

                    concept = Concept(**concept_kwargs)
                    db.add(concept)
                    await db.flush()

                existing_link = await db.execute(
                    select(NoteConcept).where(
                        NoteConcept.note_id == note_id,
                        NoteConcept.concept_id == concept.id,
                    )
                )

                if not existing_link.scalar_one_or_none():
                    db.add(
                        NoteConcept(
                            note_id=note_id,
                            concept_id=concept.id,
                            weight=float(c.get("confidence", 1.0)),
                        )
                    )

            res = await db.execute(
                select(Note).where(Note.id == note_id, Note.user_id == user_id)
            )
            note = res.scalar_one_or_none()
            if note:
                note.extraction_progress = 70

            await db.commit()

        # DB is closed here.

        # --------------------------------------------------
        # STEP 6: build flashcard payloads quickly
        # --------------------------------------------------
        set_concept_job_status(note_key, {"progress": 72})

        async with AsyncSessionLocal() as db:
            concept_rows = await db.execute(
                select(Concept)
                .join(NoteConcept, NoteConcept.concept_id == Concept.id)
                .where(
                    Concept.user_id == user_id,
                    Concept.class_id == class_id,
                    NoteConcept.note_id == note_id,
                )
            )
            linked_concepts = concept_rows.scalars().all()

            concept_payloads = []
            for concept in linked_concepts:
                payload = {
                    "name": concept.name,
                    "type": getattr(concept, "type", "") or "",
                    "description": concept.description or "",
                    "definition": getattr(concept, "definition", "") or "",
                    "when_to_use": getattr(concept, "when_to_use", "") or "",
                    "pitfalls": pitfalls_from_db(getattr(concept, "pitfalls", "")),
                    "related_concepts": getattr(concept, "related_concepts", []) or [],
                    "evidence": concept.evidence or "",
                    "confidence": float(concept.confidence or 0.5),
                }

                payload["role"] = classify_concept_role(payload)
                payload["card_budget"] = assign_card_budget(payload)

                if payload["card_budget"] > 0:
                    concept_payloads.append(payload)

            print(
                "[concept_job] linked_concepts=",
                len(linked_concepts),
                "concept_payloads_for_flashcards=",
                len(concept_payloads),
            )

            print("[concept_job] top flashcard payloads:", [
                {
                    "name": p["name"],
                    "type": p.get("type"),
                    "role": p.get("role"),
                    "budget": p.get("card_budget"),
                    "confidence": p.get("confidence"),
                    "evidence_len": len(p.get("evidence", "")),
                }
                for p in concept_payloads[:20]
            ])

        # DB is closed here.

        concept_payloads.sort(
            key=lambda x: (
                x.get("card_budget", 0),
                x.get("confidence", 0.0),
            ),
            reverse=True,
        )

        # --------------------------------------------------
        # STEP 7: generate flashcards with NO DB open
        # --------------------------------------------------
        set_concept_job_status(note_key, {"progress": 80})

        if concept_payloads:
            if mode == "math":
                flashcards = await generate_math_flashcards_from_concepts(concept_payloads)
            else:
                flashcards = await generate_flashcards_from_concepts(concept_payloads)
        else:
            flashcards = []

        print("[concept_job] generated_flashcards_before_grounding=", len(flashcards))
        print("[concept_job] sample_flashcards_before_grounding=", flashcards[:10])

        # --------------------------------------------------
        # STEP 7.5: ground flashcard answers to original lecture notes
        # --------------------------------------------------
        if flashcards and mode != "math":
            set_concept_job_status(note_key, {"progress": 86})

            flashcards = await ground_flashcards_against_lecture(
                note_text=note_text,
                flashcards=flashcards,
            )

        print("[concept_job] generated_flashcards_after_grounding=", len(flashcards))
        print("[concept_job] sample_flashcards_after_grounding=", flashcards[:10])
        # --------------------------------------------------
        # STEP 8: save flashcards quickly
        # --------------------------------------------------
        set_concept_job_status(note_key, {"progress": 90})

        async with AsyncSessionLocal() as db:
            concept_rows = await db.execute(
                select(Concept)
                .join(NoteConcept, NoteConcept.concept_id == Concept.id)
                .where(
                    Concept.user_id == user_id,
                    Concept.class_id == class_id,
                    NoteConcept.note_id == note_id,
                )
            )
            linked_concepts = concept_rows.scalars().all()

            concept_lookup = {
                concept.name: concept.id
                for concept in linked_concepts
            }

            normalized_concept_lookup = {
                concept.name.lower().replace(" ", "_"): concept.id
                for concept in linked_concepts
            }

            existing_flashcards_res = await db.execute(
                select(Flashcard.question, Flashcard.answer).where(
                    Flashcard.user_id == user_id,
                    Flashcard.note_id == note_id,
                )
            )

            existing_flashcards = [
                {
                    "question": row[0] or "",
                    "answer": row[1] or "",
                }
                for row in existing_flashcards_res.fetchall()
            ]

            existing_flashcard_questions = {
                c["question"].strip().lower()
                for c in existing_flashcards
            }

            saved_count = 0
            skipped_exact_duplicate = 0
            skipped_semantic_duplicate = 0
            skipped_missing_question = 0

            for card in flashcards:
                q_key = card.get("question", "").strip().lower()
                if not q_key:
                    skipped_missing_question += 1
                    continue

                if q_key in existing_flashcard_questions:
                    skipped_exact_duplicate += 1
                    continue

                candidate = {
                    "question": card.get("question", ""),
                    "answer": card.get("answer", ""),
                    "concept_name": card.get("concept_name", ""),
                    "card_type": card.get("card_type", ""),
                    "source_evidence": card.get("source_evidence", ""),
                }

                if any(flashcards_too_similar(candidate, old) for old in existing_flashcards):
                    skipped_semantic_duplicate += 1
                    continue
    
                card_concept_name = (card.get("concept_name") or "").strip()
                matched_concept_id = concept_lookup.get(card_concept_name)

                if not matched_concept_id:
                    matched_concept_id = normalized_concept_lookup.get(
                        card_concept_name.lower().replace(" ", "_")
                    )

                if not matched_concept_id:
                    for name, cid in concept_lookup.items():
                        if name.replace("_", " ") in (
                            (card.get("question", "") + " " + card.get("answer", "")).lower()
                        ):
                            matched_concept_id = cid
                            break

                flashcard_kwargs = dict(
                    user_id=user_id,
                    class_id=class_id,
                    note_id=note_id,
                    concept_id=matched_concept_id,
                    question=card["question"],
                    answer=card["answer"],
                    confidence=float(card.get("confidence", 0.7)),
                    next_review=datetime.now(timezone.utc),
                )

                if hasattr(Flashcard, "card_type"):
                    flashcard_kwargs["card_type"] = card.get("card_type")

                if hasattr(Flashcard, "source_evidence"):
                    flashcard_kwargs["source_evidence"] = card.get("source_evidence")

                if hasattr(Flashcard, "why_this_card_matters"):
                    flashcard_kwargs["why_this_card_matters"] = card.get("why_this_card_matters")

                fc = Flashcard(**flashcard_kwargs)
                db.add(fc)
                saved_count += 1
                existing_flashcard_questions.add(q_key)
                existing_flashcards.append(candidate)

            res = await db.execute(
                select(Note).where(Note.id == note_id, Note.user_id == user_id)
            )
            note = res.scalar_one_or_none()
            if note:
                note.extraction_status = "completed"
                note.extraction_progress = 100
                note.extraction_error = None
                note.extraction_finished_at = datetime.now(timezone.utc)
            
            print(
                "[concept_job] flashcard_save_summary",
                {
                    "generated": len(flashcards),
                    "saved": saved_count,
                    "skipped_missing_question": skipped_missing_question,
                    "skipped_exact_duplicate": skipped_exact_duplicate,
                    "skipped_semantic_duplicate": skipped_semantic_duplicate,
                }
            )
            
            
            await db.commit()

        set_concept_job_status(
            note_key,
            {
                "status": "completed",
                "progress": 100,
                "error": None,
                "finished_at": now_iso(),
            },
        )

    except Exception as e:
        err = str(e)

        set_concept_job_status(
            note_key,
            {
                "status": "failed",
                "progress": 100,
                "error": err,
                "finished_at": now_iso(),
            },
        )

        async with AsyncSessionLocal() as db:
            res = await db.execute(
                select(Note).where(Note.id == note_id, Note.user_id == user_id)
            )
            note = res.scalar_one_or_none()
            if note:
                note.extraction_status = "failed"
                note.extraction_error = err
                note.extraction_finished_at = datetime.now(timezone.utc)
                await db.commit()

        print(f"[concept_job] failed note_id={note_id}: {err}")
        raise
