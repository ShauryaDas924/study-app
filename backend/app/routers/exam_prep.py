from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import (
    Class,
    Concept,
    ExamPrepPlan,
    ExamPrepSyllabus,
    ExamPrepTask,
    ExamPrepTopicPrediction,
    Mastery,
)
from app.services.auth import get_current_user_id
from app.services.exam_prep import (
    VALID_INTENSITIES,
    VALID_TASK_STATUSES,
    apply_prediction_ids_to_plan,
    build_plan_days,
    build_task_rows_from_plan,
    build_topic_predictions,
    extract_syllabus_text,
    parse_exam_datetime,
    parse_syllabus,
    parsed_summary,
)

router = APIRouter(prefix="/plan/exam-prep", tags=["exam-prep"])


class GenerateExamPrepIn(BaseModel):
    class_id: UUID
    syllabus_id: UUID
    exam_title: str
    exam_date_iso: str
    available_minutes_per_day: int = 60
    intensity: str = "balanced"


class CreateTasksIn(BaseModel):
    overwrite_existing: bool = False


class UpdateTaskStatusIn(BaseModel):
    status: str


async def ensure_class_owned(db: AsyncSession, user_id: UUID, class_id: UUID):
    res = await db.execute(
        select(Class.id).where(Class.id == class_id, Class.user_id == user_id)
    )
    if not res.scalar_one_or_none():
        raise HTTPException(404, "Class not found")


def serialize_topic(topic: ExamPrepTopicPrediction) -> dict:
    return {
        "id": str(topic.id),
        "topic_name": topic.topic_name,
        "matched_concept_ids": topic.matched_concept_ids or [],
        "exam_likelihood_score": float(topic.exam_likelihood_score or 0),
        "student_priority_score": float(topic.student_priority_score or 0),
        "confidence": topic.confidence,
        "evidence": topic.evidence or [],
        "missing_data": topic.missing_data or [],
        "recommended_study_action": topic.recommended_study_action,
        "scoring_json": topic.scoring_json or {},
        "created_at": topic.created_at.isoformat() if topic.created_at else None,
    }


def serialize_task(task: ExamPrepTask) -> dict:
    return {
        "id": str(task.id),
        "exam_prep_plan_id": str(task.exam_prep_plan_id),
        "exam_topic_prediction_id": str(task.exam_topic_prediction_id) if task.exam_topic_prediction_id else None,
        "concept_id": str(task.concept_id) if task.concept_id else None,
        "planned_for": task.planned_for.isoformat() if task.planned_for else None,
        "task_type": task.task_type,
        "title": task.title,
        "description": task.description,
        "minutes": int(task.minutes or 0),
        "rationale": task.rationale,
        "status": task.status,
        "source_json": task.source_json or {},
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


def serialize_plan_summary(plan: ExamPrepPlan) -> dict:
    plan_json = plan.plan_json or {}
    warnings = plan_json.get("warnings") or []
    topics = plan_json.get("topics") or []
    return {
        "id": str(plan.id),
        "class_id": str(plan.class_id),
        "syllabus_id": str(plan.syllabus_id),
        "title": plan.title,
        "exam_title": plan.exam_title,
        "exam_date": plan.exam_date.isoformat() if plan.exam_date else None,
        "available_minutes_per_day": int(plan.available_minutes_per_day or 0),
        "intensity": plan.intensity,
        "status": plan.status,
        "topic_count": len(topics),
        "warning_count": len(warnings),
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
    }


async def get_owned_syllabus(db: AsyncSession, user_id: UUID, class_id: UUID, syllabus_id: UUID) -> ExamPrepSyllabus:
    res = await db.execute(
        select(ExamPrepSyllabus).where(
            ExamPrepSyllabus.id == syllabus_id,
            ExamPrepSyllabus.user_id == user_id,
            ExamPrepSyllabus.class_id == class_id,
        )
    )
    syllabus = res.scalar_one_or_none()
    if not syllabus:
        raise HTTPException(404, "Syllabus not found")
    return syllabus


async def get_owned_plan(db: AsyncSession, user_id: UUID, plan_id: UUID) -> ExamPrepPlan:
    res = await db.execute(
        select(ExamPrepPlan).where(
            ExamPrepPlan.id == plan_id,
            ExamPrepPlan.user_id == user_id,
        )
    )
    plan = res.scalar_one_or_none()
    if not plan:
        raise HTTPException(404, "Plan not found")
    await ensure_class_owned(db, user_id, plan.class_id)
    return plan


@router.post("/syllabi")
async def upload_syllabus(
    class_id: UUID = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    await ensure_class_owned(db, user_id, class_id)

    content = await file.read()
    if not content:
        raise HTTPException(400, "Missing file content")

    try:
        raw_text, warnings = await extract_syllabus_text(file.filename or "syllabus", content)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, "Syllabus text extraction failed") from exc

    parsed_json, parse_status, parse_error = await parse_syllabus(raw_text)
    parsed_warnings = parsed_json.get("warnings") or []
    for warning in warnings:
        if warning not in parsed_warnings:
            parsed_warnings.append(warning)
    parsed_json["warnings"] = parsed_warnings

    syllabus = ExamPrepSyllabus(
        user_id=user_id,
        class_id=class_id,
        filename=file.filename or "syllabus",
        mime_type=file.content_type,
        raw_text=raw_text,
        parsed_json=parsed_json,
        parse_status=parse_status,
        parse_error=parse_error,
    )
    db.add(syllabus)
    await db.commit()
    await db.refresh(syllabus)

    return {
        "syllabus_id": str(syllabus.id),
        "filename": syllabus.filename,
        "parsed_summary": parsed_summary(parsed_json),
        "warnings": parsed_json.get("warnings") or [],
    }


@router.get("/syllabi")
async def list_syllabi(
    class_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    await ensure_class_owned(db, user_id, class_id)
    res = await db.execute(
        select(ExamPrepSyllabus)
        .where(
            ExamPrepSyllabus.user_id == user_id,
            ExamPrepSyllabus.class_id == class_id,
        )
        .order_by(ExamPrepSyllabus.created_at.desc())
    )
    rows = res.scalars().all()
    return [
        {
            "id": str(row.id),
            "filename": row.filename,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "parse_status": row.parse_status,
            "parsed_summary": parsed_summary(row.parsed_json or {}),
            "warnings": (row.parsed_json or {}).get("warnings") or [],
        }
        for row in rows
    ]


@router.post("/generate")
async def generate_exam_prep_plan(
    payload: GenerateExamPrepIn,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    await ensure_class_owned(db, user_id, payload.class_id)
    syllabus = await get_owned_syllabus(db, user_id, payload.class_id, payload.syllabus_id)

    if payload.intensity not in VALID_INTENSITIES:
        raise HTTPException(400, "Intensity must be light, balanced, or aggressive")

    if payload.available_minutes_per_day < 10:
        raise HTTPException(400, "available_minutes_per_day must be at least 10")

    if payload.available_minutes_per_day > 480:
        raise HTTPException(400, "available_minutes_per_day is too high")

    exam_title = payload.exam_title.strip() or "Exam"

    try:
        exam_date = parse_exam_datetime(payload.exam_date_iso)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    if exam_date <= datetime.now(timezone.utc):
        raise HTTPException(400, "Exam date must be in the future")

    cres = await db.execute(
        select(Concept).where(
            Concept.user_id == user_id,
            Concept.class_id == payload.class_id,
        )
    )
    concepts = cres.scalars().all()

    mastery_map = {}
    concept_ids = [c.id for c in concepts]
    if concept_ids:
        mres = await db.execute(
            select(Mastery).where(
                Mastery.user_id == user_id,
                Mastery.concept_id.in_(concept_ids),
            )
        )
        mastery_map = {m.concept_id: float(m.mastery_prob) for m in mres.scalars().all()}

    topics, topic_warnings = build_topic_predictions(
        parsed_json=syllabus.parsed_json or {},
        raw_text=syllabus.raw_text,
        concepts=concepts,
        mastery_map=mastery_map,
    )

    plan_days, plan_warnings, starts_on, ends_on = build_plan_days(
        exam_date=exam_date,
        topics=topics,
        available_minutes_per_day=payload.available_minutes_per_day,
        intensity=payload.intensity,
    )

    all_warnings = []
    for source in [
        (syllabus.parsed_json or {}).get("warnings") or [],
        topic_warnings,
        plan_warnings,
    ]:
        for warning in source:
            if warning and warning not in all_warnings:
                all_warnings.append(warning)

    plan = ExamPrepPlan(
        user_id=user_id,
        class_id=payload.class_id,
        syllabus_id=syllabus.id,
        title=f"{exam_title} prep plan",
        exam_title=exam_title,
        exam_date=exam_date,
        available_minutes_per_day=payload.available_minutes_per_day,
        intensity=payload.intensity,
        starts_on=starts_on,
        ends_on=ends_on,
        plan_json={"topics": topics, "plan_days": plan_days, "warnings": all_warnings},
        status="active",
    )
    db.add(plan)
    await db.flush()

    valid_concept_ids = {str(c.id) for c in concepts}
    for topic in topics:
        matched_concept_ids = [
            cid for cid in topic.get("matched_concept_ids", [])
            if cid in valid_concept_ids
        ]
        prediction = ExamPrepTopicPrediction(
            user_id=user_id,
            class_id=payload.class_id,
            syllabus_id=syllabus.id,
            exam_prep_plan_id=plan.id,
            topic_name=topic["topic_name"],
            matched_concept_ids=matched_concept_ids,
            exam_likelihood_score=topic["exam_likelihood_score"],
            student_priority_score=topic["student_priority_score"],
            confidence=topic["confidence"],
            evidence=topic["evidence"],
            missing_data=topic["missing_data"],
            recommended_study_action=topic["recommended_study_action"],
            scoring_json=topic["scoring_json"],
        )
        db.add(prediction)
        await db.flush()
        topic["id"] = str(prediction.id)
        topic["matched_concept_ids"] = matched_concept_ids

    plan_days = apply_prediction_ids_to_plan(plan_days, topics)
    plan.plan_json = {"topics": topics, "plan_days": plan_days, "warnings": all_warnings}
    await db.commit()
    await db.refresh(plan)

    return {
        "exam_prep_plan_id": str(plan.id),
        "topics": topics,
        "plan_days": plan_days,
        "warnings": all_warnings,
    }


@router.get("/plans")
async def list_plans(
    class_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    await ensure_class_owned(db, user_id, class_id)
    res = await db.execute(
        select(ExamPrepPlan)
        .where(
            ExamPrepPlan.user_id == user_id,
            ExamPrepPlan.class_id == class_id,
        )
        .order_by(ExamPrepPlan.created_at.desc())
        .limit(30)
    )
    plans = res.scalars().all()
    return [serialize_plan_summary(plan) for plan in plans]


@router.get("/plans/{plan_id}")
async def get_plan(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    plan = await get_owned_plan(db, user_id, plan_id)

    topic_res = await db.execute(
        select(ExamPrepTopicPrediction)
        .where(
            ExamPrepTopicPrediction.user_id == user_id,
            ExamPrepTopicPrediction.class_id == plan.class_id,
            ExamPrepTopicPrediction.exam_prep_plan_id == plan.id,
        )
        .order_by(ExamPrepTopicPrediction.student_priority_score.desc())
    )
    topics = [serialize_topic(topic) for topic in topic_res.scalars().all()]

    task_res = await db.execute(
        select(ExamPrepTask)
        .where(
            ExamPrepTask.user_id == user_id,
            ExamPrepTask.class_id == plan.class_id,
            ExamPrepTask.exam_prep_plan_id == plan.id,
        )
        .order_by(ExamPrepTask.planned_for.asc(), ExamPrepTask.created_at.asc())
    )
    tasks = [serialize_task(task) for task in task_res.scalars().all()]

    return {
        **serialize_plan_summary(plan),
        "topics": topics or (plan.plan_json or {}).get("topics") or [],
        "plan_days": (plan.plan_json or {}).get("plan_days") or [],
        "warnings": (plan.plan_json or {}).get("warnings") or [],
        "tasks": tasks,
    }


@router.post("/plans/{plan_id}/tasks")
async def create_plan_tasks(
    plan_id: UUID,
    payload: CreateTasksIn,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    plan = await get_owned_plan(db, user_id, plan_id)

    existing_res = await db.execute(
        select(ExamPrepTask).where(
            ExamPrepTask.user_id == user_id,
            ExamPrepTask.class_id == plan.class_id,
            ExamPrepTask.exam_prep_plan_id == plan.id,
        )
    )
    existing_tasks = existing_res.scalars().all()

    if existing_tasks and not payload.overwrite_existing:
        return {"created_count": 0, "tasks": [serialize_task(task) for task in existing_tasks]}

    if payload.overwrite_existing:
        await db.execute(
            delete(ExamPrepTask).where(
                ExamPrepTask.user_id == user_id,
                ExamPrepTask.class_id == plan.class_id,
                ExamPrepTask.exam_prep_plan_id == plan.id,
            )
        )

    prediction_res = await db.execute(
        select(ExamPrepTopicPrediction.id).where(
            ExamPrepTopicPrediction.user_id == user_id,
            ExamPrepTopicPrediction.class_id == plan.class_id,
            ExamPrepTopicPrediction.exam_prep_plan_id == plan.id,
        )
    )
    valid_prediction_ids = {str(row[0]) for row in prediction_res.fetchall()}

    concept_res = await db.execute(
        select(Concept.id).where(
            Concept.user_id == user_id,
            Concept.class_id == plan.class_id,
        )
    )
    valid_concept_ids = {str(row[0]) for row in concept_res.fetchall()}

    task_payloads = build_task_rows_from_plan(plan.plan_json or {})
    created = []

    for item in task_payloads:
        concept_id = item.get("concept_id")
        prediction_id = item.get("exam_topic_prediction_id")

        if concept_id and str(concept_id) not in valid_concept_ids:
            concept_id = None
        if prediction_id and str(prediction_id) not in valid_prediction_ids:
            prediction_id = None

        task = ExamPrepTask(
            user_id=user_id,
            class_id=plan.class_id,
            exam_prep_plan_id=plan.id,
            exam_topic_prediction_id=UUID(str(prediction_id)) if prediction_id else None,
            concept_id=UUID(str(concept_id)) if concept_id else None,
            planned_for=item["planned_for"],
            task_type=item["task_type"],
            title=item["title"],
            description=item["description"],
            minutes=item["minutes"],
            rationale=item["rationale"],
            status="pending",
            source_json=item["source_json"],
        )
        db.add(task)
        created.append(task)

    await db.commit()
    print("[exam_prep] task_creation", {"plan_id": str(plan.id), "created_count": len(created)})

    task_res = await db.execute(
        select(ExamPrepTask)
        .where(
            ExamPrepTask.user_id == user_id,
            ExamPrepTask.class_id == plan.class_id,
            ExamPrepTask.exam_prep_plan_id == plan.id,
        )
        .order_by(ExamPrepTask.planned_for.asc(), ExamPrepTask.created_at.asc())
    )
    tasks = [serialize_task(task) for task in task_res.scalars().all()]
    return {"created_count": len(created), "tasks": tasks}


@router.patch("/tasks/{task_id}")
async def update_task_status(
    task_id: UUID,
    payload: UpdateTaskStatusIn,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    if payload.status not in VALID_TASK_STATUSES:
        raise HTTPException(400, "Invalid task status")

    res = await db.execute(
        select(ExamPrepTask).where(
            ExamPrepTask.id == task_id,
            ExamPrepTask.user_id == user_id,
        )
    )
    task = res.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found")

    await ensure_class_owned(db, user_id, task.class_id)

    task.status = payload.status
    task.completed_at = datetime.now(timezone.utc) if payload.status == "done" else None
    await db.commit()
    await db.refresh(task)

    return serialize_task(task)
