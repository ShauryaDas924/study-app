from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import (
    Class,
    ExamLockdownAttempt,
    ExamLockdownPitfall,
    ExamLockdownSession,
    ExamPrepExtractedQuestion,
    ExamPrepMaterial,
    ExamPrepPlan,
    ExamPrepRecommendedQuestion,
    StudentPitfall,
)
from app.services.auth import get_current_user_id
from app.services.exam_lockdown import (
    build_exam_lockdown_tutor_response,
    extract_exam_lockdown_pitfalls,
)

router = APIRouter(prefix="/exam-lockdown", tags=["exam-lockdown"])


class CreateSessionIn(BaseModel):
    class_id: UUID
    plan_id: UUID


class TutorIn(BaseModel):
    class_id: UUID
    plan_id: UUID
    recommended_question_id: UUID
    user_question: str | None = None
    user_attempt: str | None = None


class AttemptIn(BaseModel):
    class_id: UUID
    plan_id: UUID
    recommended_question_id: UUID
    session_id: UUID | None = None
    user_answer_text: str | None = None
    confidence: int | None = None
    time_spent_sec: int | None = None
    tutor_feedback_json: dict | None = None
    status: str = "attempted"


async def ensure_class_owned(db: AsyncSession, user_id: UUID, class_id: UUID):
    res = await db.execute(
        select(Class.id).where(Class.id == class_id, Class.user_id == user_id)
    )
    if not res.scalar_one_or_none():
        raise HTTPException(404, "Class not found")


async def get_owned_plan(db: AsyncSession, user_id: UUID, class_id: UUID, plan_id: UUID) -> ExamPrepPlan:
    await ensure_class_owned(db, user_id, class_id)
    res = await db.execute(
        select(ExamPrepPlan).where(
            ExamPrepPlan.id == plan_id,
            ExamPrepPlan.user_id == user_id,
            ExamPrepPlan.class_id == class_id,
        )
    )
    plan = res.scalar_one_or_none()
    if not plan:
        raise HTTPException(404, "Exam prep plan not found")
    return plan


async def load_recommendation_context(
    db: AsyncSession,
    user_id: UUID,
    class_id: UUID,
    plan_id: UUID,
    recommended_question_id: UUID,
) -> tuple[ExamPrepRecommendedQuestion, ExamPrepExtractedQuestion, ExamPrepMaterial | None]:
    rec_res = await db.execute(
        select(ExamPrepRecommendedQuestion).where(
            ExamPrepRecommendedQuestion.id == recommended_question_id,
            ExamPrepRecommendedQuestion.user_id == user_id,
            ExamPrepRecommendedQuestion.class_id == class_id,
            ExamPrepRecommendedQuestion.plan_id == plan_id,
        )
    )
    rec = rec_res.scalar_one_or_none()
    if not rec:
        raise HTTPException(404, "Recommended question not found")

    q_res = await db.execute(
        select(ExamPrepExtractedQuestion).where(
            ExamPrepExtractedQuestion.id == rec.extracted_question_id,
            ExamPrepExtractedQuestion.user_id == user_id,
            ExamPrepExtractedQuestion.class_id == class_id,
        )
    )
    question = q_res.scalar_one_or_none()
    if not question:
        raise HTTPException(404, "Extracted question not found")

    material_res = await db.execute(
        select(ExamPrepMaterial).where(
            ExamPrepMaterial.id == question.material_id,
            ExamPrepMaterial.user_id == user_id,
            ExamPrepMaterial.class_id == class_id,
        )
    )
    material = material_res.scalar_one_or_none()
    return rec, question, material


def serialize_session(session: ExamLockdownSession) -> dict:
    return {
        "id": str(session.id),
        "class_id": str(session.class_id),
        "plan_id": str(session.plan_id),
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "status": session.status,
    }


def question_dict(question: ExamPrepExtractedQuestion) -> dict:
    return {
        "id": str(question.id),
        "problem_number": question.problem_number,
        "prompt_text": question.prompt_text,
        "answer_text": question.answer_text,
        "solution_text": question.solution_text,
        "topic_name": question.topic_name,
        "source_ref_json": question.source_ref_json or {},
        "confidence": float(question.confidence) if question.confidence is not None else None,
    }


def material_dict(material: ExamPrepMaterial | None) -> dict | None:
    if not material:
        return None
    return {
        "id": str(material.id),
        "filename": material.filename,
        "material_type": material.material_type,
        "mime_type": material.mime_type,
    }


def recommendation_dict(rec: ExamPrepRecommendedQuestion) -> dict:
    return {
        "id": str(rec.id),
        "plan_id": str(rec.plan_id),
        "extracted_question_id": str(rec.extracted_question_id),
        "topic_prediction_id": str(rec.topic_prediction_id) if rec.topic_prediction_id else None,
        "rank": int(rec.rank or 0),
        "why_selected": rec.why_selected,
        "evidence_json": rec.evidence_json or {},
        "confidence": float(rec.confidence) if rec.confidence is not None else None,
        "status": rec.status,
    }


@router.post("/sessions")
async def create_session(
    payload: CreateSessionIn,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    await get_owned_plan(db, user_id, payload.class_id, payload.plan_id)

    res = await db.execute(
        select(ExamLockdownSession).where(
            ExamLockdownSession.user_id == user_id,
            ExamLockdownSession.class_id == payload.class_id,
            ExamLockdownSession.plan_id == payload.plan_id,
            ExamLockdownSession.status == "active",
        )
    )
    session = res.scalar_one_or_none()
    if not session:
        session = ExamLockdownSession(
            user_id=user_id,
            class_id=payload.class_id,
            plan_id=payload.plan_id,
            status="active",
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)

    return serialize_session(session)


@router.get("/progress")
async def get_progress(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    plan_res = await db.execute(
        select(ExamPrepPlan).where(
            ExamPrepPlan.id == plan_id,
            ExamPrepPlan.user_id == user_id,
        )
    )
    plan = plan_res.scalar_one_or_none()
    if not plan:
        raise HTTPException(404, "Exam prep plan not found")
    await ensure_class_owned(db, user_id, plan.class_id)

    rec_count = (await db.execute(
        select(func.count()).select_from(ExamPrepRecommendedQuestion).where(
            ExamPrepRecommendedQuestion.user_id == user_id,
            ExamPrepRecommendedQuestion.class_id == plan.class_id,
            ExamPrepRecommendedQuestion.plan_id == plan.id,
        )
    )).scalar_one()

    attempted_count = (await db.execute(
        select(func.count()).select_from(ExamLockdownAttempt).where(
            ExamLockdownAttempt.user_id == user_id,
            ExamLockdownAttempt.class_id == plan.class_id,
            ExamLockdownAttempt.plan_id == plan.id,
        )
    )).scalar_one()

    completed_count = (await db.execute(
        select(func.count()).select_from(ExamPrepRecommendedQuestion).where(
            ExamPrepRecommendedQuestion.user_id == user_id,
            ExamPrepRecommendedQuestion.class_id == plan.class_id,
            ExamPrepRecommendedQuestion.plan_id == plan.id,
            ExamPrepRecommendedQuestion.status.in_(["completed", "attempted"]),
        )
    )).scalar_one()

    pitfall_rows = (await db.execute(
        select(ExamLockdownPitfall.category, func.count().label("cnt"))
        .where(
            ExamLockdownPitfall.user_id == user_id,
            ExamLockdownPitfall.class_id == plan.class_id,
            ExamLockdownPitfall.plan_id == plan.id,
        )
        .group_by(ExamLockdownPitfall.category)
        .order_by(func.count().desc())
    )).all()

    return {
        "plan_id": str(plan.id),
        "recommended_count": int(rec_count or 0),
        "attempted_count": int(attempted_count or 0),
        "completed_count": int(completed_count or 0),
        "pitfalls": [{"category": row[0], "count": int(row[1])} for row in pitfall_rows],
    }


@router.post("/tutor")
async def tutor(
    payload: TutorIn,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    plan = await get_owned_plan(db, user_id, payload.class_id, payload.plan_id)
    rec, question, material = await load_recommendation_context(
        db,
        user_id,
        payload.class_id,
        payload.plan_id,
        payload.recommended_question_id,
    )

    attempts = (await db.execute(
        select(ExamLockdownAttempt)
        .where(
            ExamLockdownAttempt.user_id == user_id,
            ExamLockdownAttempt.class_id == payload.class_id,
            ExamLockdownAttempt.plan_id == payload.plan_id,
            ExamLockdownAttempt.recommended_question_id == payload.recommended_question_id,
        )
        .order_by(ExamLockdownAttempt.created_at.desc())
        .limit(5)
    )).scalars().all()

    pitfalls = (await db.execute(
        select(ExamLockdownPitfall)
        .where(
            ExamLockdownPitfall.user_id == user_id,
            ExamLockdownPitfall.class_id == payload.class_id,
            ExamLockdownPitfall.plan_id == payload.plan_id,
        )
        .order_by(ExamLockdownPitfall.created_at.desc())
        .limit(8)
    )).scalars().all()

    plan_json = plan.plan_json or {}
    response = await build_exam_lockdown_tutor_response(
        plan={
            **plan_json,
            "exam_title": plan.exam_title,
            "exam_date": plan.exam_date.isoformat() if plan.exam_date else None,
        },
        recommendation=recommendation_dict(rec),
        question=question_dict(question),
        material=material_dict(material),
        recent_attempts=[
            {
                "status": attempt.status,
                "confidence": attempt.confidence,
                "created_at": attempt.created_at.isoformat() if attempt.created_at else None,
            }
            for attempt in attempts
        ],
        recent_pitfalls=[
            {
                "category": pitfall.category,
                "topic_name": pitfall.topic_name,
                "tag": pitfall.tag,
                "explanation": pitfall.explanation,
            }
            for pitfall in pitfalls
        ],
        user_question=payload.user_question,
        user_attempt=payload.user_attempt,
    )

    return {
        "response_markdown": response,
        "recommended_question_id": str(rec.id),
        "question": question_dict(question),
        "material": material_dict(material),
    }


@router.post("/attempts")
async def save_attempt(
    payload: AttemptIn,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    await get_owned_plan(db, user_id, payload.class_id, payload.plan_id)
    rec, question, _material = await load_recommendation_context(
        db,
        user_id,
        payload.class_id,
        payload.plan_id,
        payload.recommended_question_id,
    )

    if payload.session_id:
        session_res = await db.execute(
            select(ExamLockdownSession).where(
                ExamLockdownSession.id == payload.session_id,
                ExamLockdownSession.user_id == user_id,
                ExamLockdownSession.class_id == payload.class_id,
                ExamLockdownSession.plan_id == payload.plan_id,
            )
        )
        if not session_res.scalar_one_or_none():
            raise HTTPException(404, "Exam Lockdown session not found")

    status = payload.status if payload.status in {"attempted", "completed", "skipped"} else "attempted"
    attempt = ExamLockdownAttempt(
        user_id=user_id,
        class_id=payload.class_id,
        session_id=payload.session_id,
        plan_id=payload.plan_id,
        recommended_question_id=payload.recommended_question_id,
        user_answer_text=payload.user_answer_text,
        confidence=payload.confidence,
        time_spent_sec=payload.time_spent_sec,
        tutor_feedback_json=payload.tutor_feedback_json or {},
        status=status,
    )
    db.add(attempt)
    await db.flush()

    rec.status = "completed" if status == "completed" else status

    pitfalls = await extract_exam_lockdown_pitfalls(
        question=question_dict(question),
        user_answer_text=payload.user_answer_text,
        tutor_feedback_json=payload.tutor_feedback_json or {},
    )
    saved_pitfalls = []
    for item in pitfalls:
        pitfall = ExamLockdownPitfall(
            user_id=user_id,
            class_id=payload.class_id,
            attempt_id=attempt.id,
            plan_id=payload.plan_id,
            topic_name=item.get("topic_name"),
            category=item["category"],
            tag=item.get("tag"),
            explanation=item.get("explanation"),
            evidence_json=item.get("evidence") or {},
        )
        db.add(pitfall)
        saved_pitfalls.append(pitfall)

        tag = item.get("tag") or item["category"]
        await db.execute(
            insert(StudentPitfall)
            .values(
                user_id=user_id,
                class_id=payload.class_id,
                pitfall=tag,
                explanation=item.get("explanation"),
            )
            .on_conflict_do_update(
                index_elements=["user_id", "class_id", "pitfall"],
                set_={"explanation": item.get("explanation")},
            )
        )

    await db.commit()
    await db.refresh(attempt)

    return {
        "id": str(attempt.id),
        "status": attempt.status,
        "created_at": attempt.created_at.isoformat() if attempt.created_at else datetime.now(timezone.utc).isoformat(),
        "pitfalls_saved": len(saved_pitfalls),
    }
