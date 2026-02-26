from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

from app.db import get_db
from app.models import Concept, Mastery, Exam
from app.models import MistakeLog
from app.services.auth import get_current_user_id
from app.services.planner import build_study_plan, build_weekly_curriculum
router = APIRouter(prefix="/plan", tags=["plan"])

class PlanIn(BaseModel):
    class_id: UUID
    exam_id: UUID | None = None
    exam_date_iso: str | None = None
    available_minutes_per_day: int = 60

@router.post("/generate")
async def generate_plan(payload: PlanIn, db: AsyncSession = Depends(get_db), user_id: UUID = Depends(get_current_user_id)):
    # resolve exam_date
    if payload.exam_id:
        eres = await db.execute(select(Exam).where(Exam.id == payload.exam_id, Exam.user_id == user_id))
        exam = eres.scalar_one_or_none()
        if not exam:
            raise HTTPException(404, "Exam not found")
        exam_date = exam.exam_date
    elif payload.exam_date_iso:
        exam_date = datetime.fromisoformat(payload.exam_date_iso)
    else:
        raise HTTPException(400, "Provide exam_id or exam_date_iso")

    cres = await db.execute(select(Concept).where(Concept.user_id == user_id, Concept.class_id == payload.class_id))
    concepts = cres.scalars().all()

    if not concepts:
        return {"days_left": 0, "plan": []}

    mids = [c.id for c in concepts]
    mres = await db.execute(select(Mastery).where(Mastery.user_id == user_id, Mastery.concept_id.in_(mids)))
    mastery = mres.scalars().all()

    m_map = {m.concept_id: m.mastery_prob for m in mastery}

    m_map_full = {m.concept_id: m for m in mastery}

    rows = []

    for c in concepts:

        m = m_map_full.get(c.id)
    
        # Count mistakes
        mistake_res = await db.execute(
            select(MistakeLog).where(
                MistakeLog.user_id == user_id,
                MistakeLog.concept_id == c.id
            )
        )

        mistakes = len(mistake_res.scalars().all())

        # Exam importance heuristic
        importance = 0.5
        name = c.name.lower()

        if "definition" in name:
            importance += 0.2

        if "formula" in name:
            importance += 0.3

        if "law" in name:
            importance += 0.2

        if "theorem" in name:
            importance += 0.3

        rows.append({
        "concept_id": c.id,
            "name": c.name,
            "definition": c.definition,
            "when_to_use": c.when_to_use,
            "pitfalls": c.pitfalls,
            "mastery_prob": float(m.mastery_prob) if m else 0.35,
            "next_review_at": m.next_review_at if m else None,
            "mistake_count": mistakes,
            "exam_importance": importance
        })
    return build_study_plan(exam_date=exam_date, mastery_rows=rows, available_minutes_per_day=payload.available_minutes_per_day)
    
@router.post("/weekly-generate")
async def weekly_generate_plan(payload: PlanIn, db: AsyncSession = Depends(get_db), user_id: UUID = Depends(get_current_user_id)):
    # resolve exam_date (same logic you already use)
    if payload.exam_id:
        eres = await db.execute(select(Exam).where(Exam.id == payload.exam_id, Exam.user_id == user_id))
        exam = eres.scalar_one_or_none()
        if not exam:
            raise HTTPException(404, "Exam not found")
        exam_date = exam.exam_date
    elif payload.exam_date_iso:
        exam_date = datetime.fromisoformat(payload.exam_date_iso)
    else:
        raise HTTPException(400, "Provide exam_id or exam_date_iso")

    # pull concepts
    cres = await db.execute(select(Concept).where(Concept.user_id == user_id, Concept.class_id == payload.class_id))
    concepts = cres.scalars().all()
    if not concepts:
        return {"weeks_left": 0, "weekly_plan": []}

    # pull mastery (including next_review_at)
    concept_ids = [c.id for c in concepts]
    mres = await db.execute(select(Mastery).where(Mastery.user_id == user_id, Mastery.concept_id.in_(concept_ids)))
    mastery = mres.scalars().all()
    m_map = {m.concept_id: m for m in mastery}

    rows = []
    for c in concepts:
        m = m_map.get(c.id)
        rows.append({
            "concept_id": c.id,
            "name": c.name,
            "mastery_prob": float(m.mastery_prob) if m else 0.35,
            "next_review_at": m.next_review_at if m else None
        })

    return build_weekly_curriculum(
        exam_date=exam_date,
        mastery_rows=rows,
        available_minutes_per_day=payload.available_minutes_per_day
    )
