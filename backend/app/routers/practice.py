
import random
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field, field_validator
from typing import Annotated, Literal
from uuid import UUID
import json
from app.services.llm import client
from app.services.llm import generate_mcq
from app.services.llm import propose_dependencies
from app.db import get_db
from app.models import Concept, PracticeSet, Question, Attempt, Mastery
from app.services.auth import get_current_user_id
from app.services.attempts import (
    public_question_json,
    resolve_attempt_correctness,
    resolve_practice_difficulty,
)
from app.services.llm import generate_one_question
from app.services.mastery import update_mastery_value, apply_forgetting, days_since
from datetime import datetime, timezone
from datetime import timedelta
from app.models import ExamSession
from sqlalchemy import select, text
from datetime import datetime, timezone, timedelta
from app.models import TutorMemory, MasteryHistory
from app.models import MistakeLog, ConceptDependency
from app.models import Flashcard
from sqlalchemy import text
from sqlalchemy import func
from app.models import ConceptDependency
router = APIRouter(prefix="/practice", tags=["practice"])


async def get_concept_cluster(
    db: AsyncSession,
    base_concept: Concept,
    concept_map: dict,
    max_size: int = 5
):
    """
    Build a cluster of related concepts using dependency graph.
    """

    cluster = [base_concept]

    # fetch dependencies
    res = await db.execute(
        select(ConceptDependency.depends_on_concept_id)
        .where(ConceptDependency.concept_id == base_concept.id)
    )

    dep_ids = res.scalars().all()

    for did in dep_ids:
        c = concept_map.get(did)
        if c:
            cluster.append(c)

    # limit cluster size
    return cluster[:max_size]
    
class GenerateIn(BaseModel):
    class_id: UUID
    difficulty: int | None = Field(default=3, ge=1, le=5)
    n: int = Field(default=5, ge=1, le=20)
    subject_tag: str = Field(default="general", min_length=1, max_length=80)
    question_type: Literal["open", "mcq"] = "open"
    
class RemedialIn(BaseModel):
    class_id: UUID
    n: int = Field(default=8, ge=1, le=20)
    difficulty: int = Field(default=2, ge=1, le=5)
    subject_tag: str = Field(default="remedial", min_length=1, max_length=80)
    lookback_days: int = Field(default=14, ge=1, le=365)
    top_tags: int = Field(default=5, ge=1, le=20)
    include_dependencies: bool = True
    
BoundedStep = Annotated[str, Field(min_length=1, max_length=4000)]


class StepGradeIn(BaseModel):
    steps: list[BoundedStep] = Field(min_length=1, max_length=50)

class TutorAskIn(BaseModel):
    question: str = Field(min_length=1, max_length=4000)

async def _select_remedial_concepts(
    db: AsyncSession,
    user_id: UUID,
    class_id: UUID,
    lookback_days: int = 14,
    top_tags: int = 5,
    include_dependencies: bool = True
) -> list[Concept]:
    """
    Picks concepts to remediate based on recent mistakes and (optionally) prerequisite dependencies.
    Strategy:
      1) Find top mistake tags recently.
      2) Map those mistake logs to concepts.
      3) Add prerequisite concepts via dependency graph.
      4) Return unique concepts within this class.
    """

    since = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    # 1) Find recent mistake logs for this user
    mres = await db.execute(
        select(MistakeLog)
        .join(Concept, Concept.id == MistakeLog.concept_id)
        .where(
            MistakeLog.user_id == user_id,
            MistakeLog.created_at >= since,
            Concept.user_id == user_id,
            Concept.class_id == class_id,
        )
        .order_by(MistakeLog.created_at.desc())
        .limit(200)
    )
    logs = mres.scalars().all()

    # If no logs, fall back to weakest mastery
    if not logs:
        cres = await db.execute(
            select(Concept).where(Concept.user_id == user_id, Concept.class_id == class_id)
        )
        return cres.scalars().all()

    # 2) Count tags
    tag_counts: dict[str, int] = {}
    concept_ids: set[UUID] = set()

    for log in logs:
        if log.concept_id:
            concept_ids.add(log.concept_id)
        if log.tag:
            tag_counts[log.tag] = tag_counts.get(log.tag, 0) + 1

    # Keep top tags (optional diagnostic use)
    top = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:top_tags]
    top_tag_set = {t for t, _ in top}

    # 3) Filter logs by top tags if we have tags
    if top_tag_set:
        concept_ids = {log.concept_id for log in logs if log.concept_id and (log.tag in top_tag_set)}

    # 4) Pull concepts (only in this class)
    if not concept_ids:
        cres = await db.execute(
            select(Concept).where(Concept.user_id == user_id, Concept.class_id == class_id)
        )
        base_concepts = cres.scalars().all()
    else:
        cres = await db.execute(
            select(Concept).where(
                Concept.user_id == user_id,
                Concept.class_id == class_id,
                Concept.id.in_(list(concept_ids))
            )
        )
        base_concepts = cres.scalars().all()

    # 5) Add dependencies (prerequisites)
    if include_dependencies and base_concepts:
        base_ids = [c.id for c in base_concepts]

        dres = await db.execute(
            select(ConceptDependency.depends_on_concept_id)
            .where(ConceptDependency.concept_id.in_(base_ids))
        )
        dep_ids = set(dres.scalars().all())

        if dep_ids:
            dep_concepts_res = await db.execute(
                select(Concept).where(
                    Concept.user_id == user_id,
                    Concept.class_id == class_id,
                    Concept.id.in_(list(dep_ids))
                )
            )
            dep_concepts = dep_concepts_res.scalars().all()
        else:
            dep_concepts = []
    else:
        dep_concepts = []

    # 6) Unique by id
    out_map = {c.id: c for c in base_concepts}
    for c in dep_concepts:
        out_map[c.id] = c

    return list(out_map.values())


async def _cross_concept_weakness(
    db: AsyncSession,
    user_id: UUID,
    class_id: UUID,
    lookback_days: int = 14,
    top_tags: int = 5,
    top_concepts_per_tag: int = 5,
):
    """
    Cross-concept weakness detector.
    Finds mistake tags that repeat across multiple concepts, then ranks concepts per tag.
    """

    since = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    # 1) Tag frequency for this class (join concepts -> class_id)
    tag_rows = (await db.execute(
        select(MistakeLog.tag, func.count().label("cnt"))
        .join(Concept, Concept.id == MistakeLog.concept_id)
        .where(
            MistakeLog.user_id == user_id,
            MistakeLog.created_at >= since,
            Concept.class_id == class_id,
            MistakeLog.tag.isnot(None)
        )
        .group_by(MistakeLog.tag)
        .order_by(text("cnt DESC"))
        .limit(top_tags)
    )).all()

    if not tag_rows:
        return {"since_days": lookback_days, "tags": []}

    tags_out = []

    # 2) For each top tag, rank concepts it appears in
    for tag, cnt in tag_rows:
        concept_rows = (await db.execute(
            select(
                MistakeLog.concept_id,
                func.count().label("cnt")
            )
            .join(Concept, Concept.id == MistakeLog.concept_id)
            .where(
                MistakeLog.user_id == user_id,
                MistakeLog.created_at >= since,
                Concept.class_id == class_id,
                MistakeLog.tag == tag
            )
            .group_by(MistakeLog.concept_id)
            .order_by(text("cnt DESC"))
            .limit(top_concepts_per_tag)
        )).all()

        concept_ids = [r[0] for r in concept_rows if r[0] is not None]

        # names
        concepts = []
        if concept_ids:
            cres = await db.execute(
                select(Concept).where(
                    Concept.user_id == user_id,
                    Concept.class_id == class_id,
                    Concept.id.in_(concept_ids),
                )
            )
            c_map = {c.id: c for c in cres.scalars().all()}
            for cid, ccount in concept_rows:
                cobj = c_map.get(cid)
                if cobj:
                    concepts.append({
                        "concept_id": str(cid),
                        "concept_name": cobj.name,
                        "count": int(ccount)
                    })

        tags_out.append({
            "tag": tag,
            "count": int(cnt),
            "top_concepts": concepts
        })

    return {"since_days": lookback_days, "tags": tags_out}

@router.post("/generate")
async def generate_practice(
    payload: GenerateIn,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):

    # 1) Fetch concepts for class
    cres = await db.execute(
        select(Concept).where(
            Concept.user_id == user_id,
            Concept.class_id == payload.class_id
        )
    )
    concepts = cres.scalars().all()
    concept_map = {c.id: c for c in concepts}
    if not concepts:
        raise HTTPException(400, "No concepts found. Extract concepts first.")

    # 2) Pull mastery values
    mres = await db.execute(
        select(Mastery).where(
            Mastery.user_id == user_id,
            Mastery.concept_id.in_([c.id for c in concepts])
        )
    )

    mastery_rows = mres.scalars().all()
    m_map = {m.concept_id: m.mastery_prob for m in mastery_rows}

    # 3) Sort weakest first
    concepts.sort(key=lambda c: m_map.get(c.id, 0.35))
    difficulty = resolve_practice_difficulty(
        payload.difficulty,
        [float(m.mastery_prob) for m in mastery_rows],
    )
            
    concept_payload = [
    {
        "name": c.name,
        "definition": c.definition,
        "when_to_use": c.when_to_use,
        "pitfalls": c.pitfalls
    }
    for c in concepts
]

    # 4) Create practice set
    ps = PracticeSet(
        user_id=user_id,
        class_id=payload.class_id,
        settings_json={"difficulty": difficulty, "n": payload.n},
        source="notes"
    )

    db.add(ps)
    await db.flush()

    created_questions = []

    # 5) Generate questions
    for _ in range(payload.n):

        
        # ----- Adaptive concept selection -----

        if payload.subject_tag == "exam":

            # mix of weak + random for coverage
            weak_pool = concepts[:max(3, len(concepts)//3)]

            if random.random() < 0.7:
                base_concept = random.choice(weak_pool)
            else:
                base_concept = random.choice(concepts)

        else:

            # practice focuses more on weak concepts
            weak_pool = concepts[:max(3, len(concepts)//2)]
            base_concept = random.choice(weak_pool)

        cluster = await get_concept_cluster(
            db,
            base_concept,
            concept_map
        )

        sampled = [
            {
                "name": c.name,
                "definition": c.definition,
                "when_to_use": c.when_to_use,
                "pitfalls": c.pitfalls
            }
            for c in cluster
        ]

        # names for LLM concept list
        names = [c["name"] for c in sampled]

        if payload.question_type == "mcq":
            qobj = await generate_mcq(
                concepts=names,
                difficulty=difficulty,
                subject_tag=payload.subject_tag
            )
        else:
            qobj = await generate_one_question(
                concepts=names,
                difficulty=difficulty,
                subject_tag=payload.subject_tag,
                concept_details=sampled
            )

        # match concept
        chosen_concept_id = base_concept.id if payload.question_type == "mcq" else None
        if payload.question_type != "mcq" and qobj.get("metadata", {}).get("concepts"):
            name0 = qobj["metadata"]["concepts"][0]
            match = next((c for c in concepts if c.name == name0), None)
            if match:
                chosen_concept_id = match.id

        # decide qtype
        qtype = "mcq" if payload.question_type == "mcq" else "short"

        # solution logic
        if qtype == "mcq":
            solution_text = qobj.get("explanation", "")
            difficulty_val = difficulty
        else:
            solution_text = (
                "\n".join(qobj["solution"]["steps"])
                + f"\n\nFinal: {qobj['solution']['final_answer']}"
            )
            difficulty_val = qobj["metadata"]["difficulty"]

        q = Question(
            practice_set_id=ps.id,
            class_id=payload.class_id,
            user_id=user_id,
            concept_id=chosen_concept_id,
            qtype=qtype,
            prompt=qobj["prompt"],
            question_json=qobj,
            solution=solution_text,
            difficulty=difficulty_val,
        )

        db.add(q)
        await db.flush()

        created_questions.append({
            "id": str(q.id),
            "prompt": q.prompt,
            "question_json": public_question_json(
                question_type=q.qtype,
                question_json=q.question_json,
            ),
        })

    await db.commit()
    return {
        "practice_set_id": str(ps.id),
        "questions": created_questions
    }
    

@router.post("/remedial/generate")
async def generate_remedial_practice(
    payload: RemedialIn,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):
    # 1) select remedial concepts
    concepts = await _select_remedial_concepts(
        db=db,
        user_id=user_id,
        class_id=payload.class_id,
        lookback_days=payload.lookback_days,
        top_tags=payload.top_tags,
        include_dependencies=payload.include_dependencies
    )

    if not concepts:
        raise HTTPException(400, "No concepts found for remedial generation.")

    # 2) build grounded payload for LLM (same grounding format you already use)
    concept_payload = [
        {
            "name": c.name,
            "definition": c.definition,
            "when_to_use": c.when_to_use,
            "pitfalls": c.pitfalls
        }
        for c in concepts
    ]

    # 3) create practice set
    ps = PracticeSet(
        user_id=user_id,
        class_id=payload.class_id,
        settings_json={
            "difficulty": payload.difficulty,
            "n": payload.n,
            "lookback_days": payload.lookback_days,
            "top_tags": payload.top_tags,
            "include_dependencies": payload.include_dependencies,
            "mode": "remedial",
        },
        source="remedial"
    )
    db.add(ps)
    await db.flush()

    created_questions = []

    # 4) generate targeted questions
    for _ in range(payload.n):
        sampled = random.sample(concept_payload, min(5, len(concept_payload)))
        names = [c["name"] for c in sampled]

        qobj = await generate_one_question(
            concepts=names,
            difficulty=payload.difficulty,
            subject_tag=payload.subject_tag,
            concept_details=sampled
        )

        chosen_concept_id = None
        if qobj.get("metadata", {}).get("concepts"):
            name0 = qobj["metadata"]["concepts"][0]
            match = next((c for c in concepts if c.name == name0), None)
            if match:
                chosen_concept_id = match.id

        qtype = "short"  # remedial still open-ended

        q = Question(
            practice_set_id=ps.id,
            class_id=payload.class_id,
            user_id=user_id,
            concept_id=chosen_concept_id,
            qtype=qtype,
            prompt=qobj["prompt"],
            question_json=qobj,
            solution="\n".join(qobj["solution"]["steps"]) +
                    f"\n\nFinal: {qobj['solution']['final_answer']}",
            difficulty=qobj["metadata"]["difficulty"],
        )
        db.add(q)
        await db.flush()

        created_questions.append({"id": str(q.id), "prompt": q.prompt})

    await db.commit()

    return {"practice_set_id": str(ps.id), "questions": created_questions}


class StartExamIn(BaseModel):
    class_id: UUID
    time_limit_min: int = Field(default=60, ge=1, le=480)
    n_questions: int = Field(default=20, ge=1, le=20)
    question_type: Literal["open", "mcq"] = "open"

@router.post("/exam/start")
async def start_exam(
    payload: StartExamIn,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):

    session = ExamSession(
        user_id=user_id,
        class_id=payload.class_id,
        time_limit_min=payload.time_limit_min
    )

    db.add(session)
    await db.flush()

    # reuse your practice generation logic
    gen = GenerateIn(
        class_id=payload.class_id,
        difficulty=None,
        n=payload.n_questions,
        subject_tag="exam",
        question_type=payload.question_type
    )

    result = await generate_practice(gen, db, user_id)

    await db.commit()

    return {
        "exam_session_id": str(session.id),
        "questions": result["questions"]
    }

class AttemptIn(BaseModel):
    user_answer_json: dict
    is_correct: bool
    confidence: int = Field(default=3, ge=1, le=5)
    time_spent_sec: int = Field(default=0, ge=0, le=86400)
    session_id: UUID | None = None

    @field_validator("user_answer_json")
    @classmethod
    def bound_answer_json(cls, value: dict) -> dict:
        if len(json.dumps(value, ensure_ascii=False)) > 20_000:
            raise ValueError("user_answer_json exceeds the 20,000-character limit")
        return value

@router.post("/questions/{question_id}/attempt")
async def submit_attempt(question_id: UUID, payload: AttemptIn, db: AsyncSession = Depends(get_db), user_id: UUID = Depends(get_current_user_id)):
    qres = await db.execute(select(Question).where(Question.id == question_id, Question.user_id == user_id))
    q = qres.scalar_one_or_none()
    if not q:
        raise HTTPException(404, "Question not found")

    if payload.session_id:
        session_res = await db.execute(
            select(ExamSession).where(
                ExamSession.id == payload.session_id,
                ExamSession.user_id == user_id,
                ExamSession.class_id == q.class_id,
            )
        )
        if not session_res.scalar_one_or_none():
            raise HTTPException(404, "Exam session not found")

    is_correct = resolve_attempt_correctness(
        question_type=q.qtype,
        question_json=q.question_json,
        user_answer_json=payload.user_answer_json,
        self_reported=payload.is_correct,
    )

    attempt = Attempt(
        user_id=user_id,
        question_id=q.id,
        concept_id=q.concept_id,
        user_answer_json=payload.user_answer_json,
        is_correct=is_correct,
        confidence=payload.confidence,
        time_spent_sec=payload.time_spent_sec,
        session_id=payload.session_id
    )
    db.add(attempt)
    # --- Structured misconception logging ---
    feedback = None
    weakness = None
    if q.question_json and not is_correct:
        mistakes = q.question_json.get("common_mistakes", [])

        if mistakes:
            chosen = random.choice(mistakes)

            feedback = {
                "message": "Watch out for this:",
                "mistake": chosen["description"],
                "why": chosen["why_wrong"]
            }
            weakness = None
            if q.concept_id:
                # Cross-concept tag pattern
                weakness = await _cross_concept_weakness(
                    db=db,
                    user_id=user_id,
                    class_id=q.class_id,
                    lookback_days=14,
                    top_tags=5,
                    top_concepts_per_tag=5
                )

                # Prereq spillover for THIS missed concept
                dres = await db.execute(
                    select(ConceptDependency.depends_on_concept_id)
                    .where(ConceptDependency.concept_id == q.concept_id)
                )
                deps = dres.scalars().all()

                weakness["prerequisites_for_this_concept"] = [str(x) for x in deps]
            if q.concept_id:
                db.add(
                    TutorMemory(
                        user_id=user_id,
                        concept_id=q.concept_id,
                        note=feedback["mistake"]
                    )
                )

        

    if feedback and q.concept_id:
        db.add(
            MistakeLog(
                user_id=user_id,
                concept_id=q.concept_id,
                tag=chosen.get("tag"),
                mistake_text=feedback["mistake"]
            )
        )
    # -------- AUTO-REMEDIAL TRIGGER --------

    recent_failures = 0
    if q.concept_id:
        fail_res = await db.execute(
            select(MistakeLog)
            .where(
                MistakeLog.user_id == user_id,
                MistakeLog.concept_id == q.concept_id
            )
        )
        recent_failures = len(fail_res.scalars().all())

    auto_remedial_created = False
    # Mastery update if concept exists
    if q.concept_id:
        mres = await db.execute(select(Mastery).where(Mastery.user_id == user_id, Mastery.concept_id == q.concept_id))
        m = mres.scalar_one_or_none()
        if not m:
            m = Mastery(user_id=user_id, concept_id=q.concept_id, mastery_prob=0.35)
            db.add(m)
            await db.flush()

        # forgetting since last practice
        days = days_since(m.last_practiced_at)
        decayed = apply_forgetting(m.mastery_prob, days, lam=0.05)
        updated = update_mastery_value(
            decayed,
            is_correct,
            q.difficulty,
            payload.confidence,
            payload.time_spent_sec,
        )

        m.mastery_prob = updated
        db.add(
            MasteryHistory(
                user_id=user_id,
                concept_id=q.concept_id,
                mastery_prob=updated
            )
        )
        m.last_practiced_at = datetime.now(timezone.utc)
        m.last_updated_at = datetime.now(timezone.utc)

        # -------- INTELLIGENT SCHEDULING --------

        res = await db.execute(
            select(MistakeLog)
            .where(
                MistakeLog.user_id == user_id,
                MistakeLog.concept_id == q.concept_id
            )
        )

        recent_mistakes = len(res.scalars().all())

        # simple adaptive spacing
        if recent_mistakes >= 5:
            days = 1
        elif updated < 0.6:
            days = 2
        elif updated < 0.8:
            days = 4
        else:
            days = 7

        m.next_review_at = datetime.now(timezone.utc) + timedelta(days=days)
        # Auto-generate remedial if repeated failures
        if recent_failures >= 3 and q.concept_id:

            weak_concept_res = await db.execute(
                select(Concept).where(
                    Concept.id == q.concept_id,
                    Concept.user_id == user_id,
                )
            )
            weak_concept = weak_concept_res.scalar_one_or_none()

            if weak_concept:
                concept_payload = [{
                    "name": weak_concept.name,
                    "definition": weak_concept.definition,
                    "when_to_use": weak_concept.when_to_use,
                    "pitfalls": weak_concept.pitfalls
                }]

                ps = PracticeSet(
                    user_id=user_id,
                    class_id=weak_concept.class_id,
                    settings_json={"difficulty": 2, "n": 3, "auto": True},
                    source="auto-remedial"
                )

                db.add(ps)
                await db.flush()
    
                for _ in range(3):
                    qobj = await generate_one_question(
                        concepts=[weak_concept.name],
                        difficulty=2,
                        subject_tag="auto-remedial",
                        concept_details=concept_payload
                    )

                    qnew = Question(
                        practice_set_id=ps.id,
                        class_id=weak_concept.class_id,
                        user_id=user_id,
                        concept_id=weak_concept.id,
                        qtype="short",
                        prompt=qobj["prompt"],
                        question_json=qobj,
                        solution="\n".join(qobj["solution"]["steps"]),
                        difficulty=2,
                    )
    
                    db.add(qnew)

                auto_remedial_created = True
        # --- Dependency diagnosis ---
        if not is_correct and q.concept_id:
            dres = await db.execute(
                select(ConceptDependency.depends_on_concept_id)
                .where(ConceptDependency.concept_id == q.concept_id)
            )
            deps = dres.scalars().all()

            if deps:
                m.last_updated_at = datetime.now(timezone.utc)
        
            
    await db.commit()
            
    return {
        "ok": True,
        "is_correct": is_correct,
        "feedback": feedback,
        "auto_remedial_created": auto_remedial_created,
        "weakness": weakness
    }

@router.get("/classes/{class_id}/readiness")
async def readiness(class_id: UUID, db: AsyncSession = Depends(get_db), user_id: UUID = Depends(get_current_user_id)):
    cres = await db.execute(select(Concept).where(Concept.user_id == user_id, Concept.class_id == class_id))
    concepts = cres.scalars().all()
    if not concepts:
        return {"readiness_percent": 0, "weak_concepts": []}

    mids = [c.id for c in concepts]
    mres = await db.execute(select(Mastery).where(Mastery.user_id == user_id, Mastery.concept_id.in_(mids)))
    mastery_rows = mres.scalars().all()

    m_map = {m.concept_id: m.mastery_prob for m in mastery_rows}
    probs = [m_map.get(c.id, 0.35) for c in concepts]
    avg = sum(probs) / max(1, len(probs))

    weak = sorted(
        [{"concept_id": str(c.id), "name": c.name, "mastery_prob": m_map.get(c.id, 0.35)} for c in concepts],
        key=lambda r: r["mastery_prob"]
    )[:6]

    return {"readiness_percent": int(round(avg * 100)), "weak_concepts": weak}
    

@router.get("/exam/{session_id}/report")
async def exam_report(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):

    res = await db.execute(
        select(Attempt).where(
            Attempt.user_id == user_id,
            Attempt.session_id == session_id
        )
    )
    attempts = res.scalars().all()

    if not attempts:
        return {"accuracy":0}

    correct = sum(1 for a in attempts if a.is_correct)
    acc = correct / len(attempts)

    avg_time = sum(a.time_spent_sec for a in attempts)/len(attempts)

    return {
        "accuracy": round(acc*100),
        "avg_time_sec": int(avg_time),
        "attempts": len(attempts)
    }
    

@router.post("/questions/{question_id}/grade-steps")
async def grade_steps(
    question_id: UUID,
    payload: StepGradeIn,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):

    qres = await db.execute(select(Question).where(Question.id == question_id, Question.user_id == user_id))
    q = qres.scalar_one_or_none()
    if not q or not q.question_json:
        raise HTTPException(404,"Question not found")

    expected = q.question_json.get("reasoning_path", [])

    resp = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role":"system","content":"Grade reasoning fairly."},
            {"role":"user","content":f"""
Expected reasoning:
{expected}

Student steps:
{payload.steps}

Score from 0 to 1 and give short feedback JSON:
{{"score":0.0,"feedback":"..."}}
"""}
        ],
        temperature=0.2
    )

    return json.loads(resp.choices[0].message.content)


@router.post("/questions/{question_id}/ask")
async def tutor_ask(
    question_id: UUID,
    payload: TutorAskIn,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):
    qres = await db.execute(select(Question).where(Question.id == question_id, Question.user_id == user_id))
    q = qres.scalar_one_or_none()

    if not q or not q.question_json:
        raise HTTPException(404, "Question not found")

    memres = await db.execute(
        select(TutorMemory.note)
        .join(Concept, Concept.id == TutorMemory.concept_id)
        .where(
            TutorMemory.user_id == user_id,
            Concept.user_id == user_id,
            Concept.class_id == q.class_id,
        )
        .order_by(TutorMemory.created_at.desc())
        .limit(5)
    )
    memories = [r[0] for r in memres.fetchall()]
    
    weakness = await _cross_concept_weakness(
        db=db,
        user_id=user_id,
        class_id=q.class_id,
        lookback_days=14,
        top_tags=5,
        top_concepts_per_tag=5
    )

    resp = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": "You are a calm tutor. Guide thinking, do not give answers."},
            {"role": "user", "content": f"""
Question:
{q.prompt}

Correct reasoning path:
{q.question_json.get("reasoning_path")}

Student past struggles:
{memories}

Cross-concept weakness patterns (last 14 days):
{weakness}

Student asked:
{payload.question}

Give a hint, not the answer.
"""}
        ],
        temperature=0.4
    )

    return {"hint": resp.choices[0].message.content}
    
@router.get("/analytics/mistake-heatmap/{class_id}")
async def mistake_heatmap(
    class_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):

    res = await db.execute(
        text("""
        SELECT concept_id, COUNT(*) as cnt
        FROM mistake_logs ml
        JOIN concepts c ON c.id = ml.concept_id
        WHERE c.class_id = :cid
        AND c.user_id = :uid
        AND ml.user_id = :uid
        GROUP BY concept_id
        ORDER BY cnt DESC
        """),
        {"cid": class_id, "uid": user_id}
    )

    rows = res.fetchall()

    return [{"concept_id": str(r[0]), "mistakes": r[1]} for r in rows]
    
@router.get("/analytics/weakness-map/{class_id}")
async def weakness_map(
    class_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):
    return await _cross_concept_weakness(
        db=db,
        user_id=user_id,
        class_id=class_id,
        lookback_days=14,
        top_tags=6,
        top_concepts_per_tag=6
    )
    
@router.get("/analytics/tag-frequency")
async def tag_frequency(
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):

    res = await db.execute(
        text("""
        SELECT tag, COUNT(*)
        FROM mistake_logs
        WHERE user_id=:u
        GROUP BY tag
        ORDER BY COUNT(*) DESC
        """),
        {"u": user_id}
    )

    return [{"tag": r[0], "count": r[1]} for r in res.fetchall()]
    
@router.get("/questions/{question_id}/next-step")
async def next_step(
    question_id: UUID,
    step_index: int = Query(ge=0, le=1000),
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):
    q = (await db.execute(
        select(Question).where(Question.id == question_id, Question.user_id == user_id)
    )).scalar_one_or_none()

    if not q:
        raise HTTPException(404, "Question not found")

    path = (q.question_json or {}).get("reasoning_path", [])

    if step_index >= len(path):
        return {"message":"Done"}

    return {"next_step": path[step_index]}
    
class CheckStepIn(BaseModel):
    step: BoundedStep
    step_index: int = Field(ge=0, le=1000)


@router.post("/questions/{question_id}/check-step")
async def check_step(
    question_id: UUID,
    payload: CheckStepIn,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    q = (await db.execute(
        select(Question).where(Question.id == question_id, Question.user_id == user_id)
    )).scalar_one_or_none()

    if not q:
        raise HTTPException(404, "Question not found")

    expected = (q.question_json or {}).get("reasoning_path", [])

    if payload.step_index >= len(expected):
        return {"result": "done"}

    target = expected[payload.step_index]

    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role":"system","content":"Evaluate if the student step matches the expected reasoning."},
            {"role":"user","content":f"""
Expected step:
{target}

Student step:
{payload.step}

Return JSON:
{{"correct":true/false,"feedback":"short hint"}}
"""}
        ],
        temperature=0.2
    )

    return json.loads(resp.choices[0].message.content)
    
class WhyWrongIn(BaseModel):
    step: BoundedStep


@router.post("/questions/{question_id}/why-wrong")
async def why_wrong(
    question_id: UUID,
    payload: WhyWrongIn,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    q = (await db.execute(
        select(Question).where(Question.id == question_id, Question.user_id == user_id)
    )).scalar_one_or_none()

    if not q:
        raise HTTPException(404, "Question not found")

    mistakes = (q.question_json or {}).get("common_mistakes", [])

    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role":"system","content":"Explain misconceptions simply."},
            {"role":"user","content":f"""
Question:
{q.prompt}

Common mistakes:
{mistakes}

Student step:
{payload.step}

Explain why the step may be wrong and guide correction.
"""}
        ],
        temperature=0.3
    )

    return {"explanation": resp.choices[0].message.content}
    
@router.get("/questions/{question_id}/next-hint")
async def next_hint(
    question_id: UUID,
    hint_level: int = Query(default=1, ge=1, le=3),
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    q = (await db.execute(
        select(Question).where(Question.id == question_id, Question.user_id == user_id)
    )).scalar_one_or_none()

    if not q:
        raise HTTPException(404, "Question not found")

    reasoning = (q.question_json or {}).get("reasoning_path", [])

    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role":"system","content":"Give subtle hints, not answers."},
            {"role":"user","content":f"""
Question:
{q.prompt}

Reasoning path:
{reasoning}

Hint level:
{hint_level} (1=subtle, 3=strong)

Give a helpful hint only.
"""}
        ],
        temperature=0.5
    )

    return {"hint": resp.choices[0].message.content}
    
@router.get("/analytics/knowledge-graph/{class_id}")
async def knowledge_graph(
    class_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):
    # 1) Concepts in class
    cres = await db.execute(
        select(Concept).where(
            Concept.user_id == user_id,
            Concept.class_id == class_id
        )
    )
    concepts = cres.scalars().all()
    if not concepts:
        return {"nodes": [], "edges": []}

    concept_ids = [c.id for c in concepts]

    # 2) Mastery map
    mres = await db.execute(
        select(Mastery).where(
            Mastery.user_id == user_id,
            Mastery.concept_id.in_(concept_ids)
        )
    )
    mastery_rows = mres.scalars().all()
    mastery_map = {m.concept_id: float(m.mastery_prob) for m in mastery_rows}

    # 3) Mistake counts per concept
    misres = await db.execute(
        text("""
        SELECT concept_id, COUNT(*)::int AS cnt
        FROM mistake_logs ml
        JOIN concepts c ON c.id = ml.concept_id
        WHERE ml.user_id = :u
          AND c.user_id = :u
          AND c.class_id = :cid
          AND ml.concept_id IS NOT NULL
        GROUP BY concept_id
        """),
        {"u": user_id, "cid": class_id}
    )
    mistake_count_map = {row[0]: int(row[1]) for row in misres.fetchall()}

    # 4) Mistake tag counts per concept (for tag nodes + edges)
    tagres = await db.execute(
        text("""
        SELECT concept_id, tag, COUNT(*)::int AS cnt
        FROM mistake_logs ml
        JOIN concepts c ON c.id = ml.concept_id
        WHERE ml.user_id = :u
          AND c.user_id = :u
          AND c.class_id = :cid
          AND ml.concept_id IS NOT NULL
          AND ml.tag IS NOT NULL
        GROUP BY concept_id, tag
        """),
        {"u": user_id, "cid": class_id}
    )
    tag_rows = tagres.fetchall()

    # 5) Dependency edges (prereq -> concept)
    dres = await db.execute(
        select(ConceptDependency)
        .where(ConceptDependency.concept_id.in_(concept_ids))
    )
    deps = dres.scalars().all()

    # ----- Build graph payload -----
    nodes = []
    edges = []

    # concept nodes
    for c in concepts:
        nodes.append({
            "id": str(c.id),
            "label": c.name,
            "type": "concept",
            "mastery_prob": mastery_map.get(c.id, 0.35),
            "mistake_count": mistake_count_map.get(c.id, 0)
        })

    # prereq edges
    # edge: depends_on -> concept
    for d in deps:
        edges.append({
            "source": str(d.depends_on_concept_id),
            "target": str(d.concept_id),
            "type": "prereq",
            "weight": float(d.weight)
        })

    # tag nodes + edges
    seen_tags = set()
    for concept_id, tag, cnt in tag_rows:
        tag_id = f"tag:{tag}"
        if tag_id not in seen_tags:
            nodes.append({
                "id": tag_id,
                "label": tag,
                "type": "tag"
            })
            seen_tags.add(tag_id)

        edges.append({
            "source": str(concept_id),
            "target": tag_id,
            "type": "mistake_tag",
            "weight": int(cnt)
        })

    return {"nodes": nodes, "edges": edges}
    
@router.post("/dependencies/auto-build/{class_id}")
async def auto_build_dependencies(
    class_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):

    # 1️⃣ Fetch concepts
    res = await db.execute(
        select(Concept).where(
            Concept.user_id == user_id,
            Concept.class_id == class_id
        )
    )

    concepts = res.scalars().all()

    if len(concepts) < 2:
        return {"message":"Not enough concepts"}

    concept_payload = [
        {"name":c.name,"definition":c.definition}
        for c in concepts
    ]

    # 2️⃣ Ask LLM
    edges = await propose_dependencies(concept_payload)

    name_to_id = {c.name:c.id for c in concepts}

    saved = 0

    # 3️⃣ Save edges
    for e in edges:
        a = name_to_id.get(e["concept"])
        b = name_to_id.get(e["depends_on"])

        if not a or not b or a==b:
            continue

        await db.execute(
            text("""
            INSERT INTO concept_dependencies
            (concept_id, depends_on_concept_id)
            VALUES (:a,:b)
            ON CONFLICT DO NOTHING
            """),
            {"a":a,"b":b}
        )

        saved += 1

    await db.commit()

    return {
        "edges_created": saved,
        "edges": edges
    }


@router.get("/latest/{class_id}")
async def get_latest_practice(
    class_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):
    # latest practice set
    ps_res = await db.execute(
        select(PracticeSet)
        .where(
            PracticeSet.user_id == user_id,
            PracticeSet.class_id == class_id
        )
        .order_by(PracticeSet.created_at.desc())
        .limit(1)
    )

    ps = ps_res.scalar_one_or_none()

    if not ps:
        return {"questions": []}

    # fetch questions
    qres = await db.execute(
        select(Question)
        .where(Question.practice_set_id == ps.id, Question.user_id == user_id)
    )

    qs = qres.scalars().all()

    return {
        "practice_set_id": str(ps.id),
        "questions": [
            {
                "id": str(q.id),
                "prompt": q.prompt,
                "question_json": public_question_json(
                    question_type=q.qtype,
                    question_json=q.question_json,
                ),
            }
            for q in qs
        ]
    }

@router.get("/flashcards/due/{class_id}")
async def due_flashcards(
    class_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):
    now = datetime.utcnow()

    res = await db.execute(
        select(Flashcard).where(
            Flashcard.user_id == user_id,
            Flashcard.class_id == class_id,
            Flashcard.next_review <= now
        ).limit(50)
    )

    cards = res.scalars().all()

    return [
        {
            "id": str(c.id),
            "question": c.question,
            "answer": c.answer
        }
        for c in cards
    ]


@router.post("/flashcards/grade")
async def grade_flashcard(
    data: dict,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):

    card_res = await db.execute(
        select(Flashcard).where(
            Flashcard.id == data["flashcard_id"],
            Flashcard.user_id == user_id,
        )
    )
    card = card_res.scalar_one_or_none()

    if not card:
        raise HTTPException(404, "Card not found")

    grade = data["grade"]

    if grade == "hard":
        days = 1
    elif grade == "medium":
        days = 3
    else:
        days = 7

    card.review_count += 1
    card.interval_days = days
    card.next_review = datetime.utcnow() + timedelta(days=days)

    await db.commit()

    return {"ok": True}
