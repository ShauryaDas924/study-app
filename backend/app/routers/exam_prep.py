from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import (
    Class,
    Concept,
    ExamPrepExtractedQuestion,
    ExamPrepMaterial,
    ExamPrepPlan,
    ExamPrepRecommendedQuestion,
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
    build_material_topic_predictions,
    build_plan_days,
    build_plan_variants,
    build_task_rows_from_plan,
    build_topic_predictions,
    extract_exam_prep_material_text,
    extract_questions_from_material_text,
    extract_syllabus_text,
    merge_topic_prediction_sets,
    normalize_material_type,
    parse_exam_datetime,
    parse_syllabus,
    parsed_summary,
    select_recommended_questions_for_topics,
)

router = APIRouter(prefix="/plan/exam-prep", tags=["exam-prep"])


class GenerateExamPrepIn(BaseModel):
    class_id: UUID
    syllabus_id: UUID | None = None
    exam_title: str
    exam_date_iso: str | None = None
    exam_date: str | None = None
    available_days: int | None = None
    available_minutes_per_day: int = 60
    minutes_per_day: int | None = None
    intensity: str = "balanced"
    target_score: float | None = None
    target_grade: str | None = None
    current_scores_json: dict | None = None
    weak_topics: list[str] | None = None
    selected_material_ids: list[UUID] | None = None
    active: bool = True


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


def serialize_material(material: ExamPrepMaterial, question_count: int | None = None) -> dict:
    return {
        "id": str(material.id),
        "class_id": str(material.class_id),
        "filename": material.filename,
        "mime_type": material.mime_type,
        "material_type": material.material_type,
        "extraction_status": material.extraction_status,
        "parse_error": material.parse_error,
        "metadata_json": material.metadata_json or {},
        "question_count": int(question_count or 0),
        "created_at": material.created_at.isoformat() if material.created_at else None,
        "updated_at": material.updated_at.isoformat() if material.updated_at else None,
    }


def serialize_question(question: ExamPrepExtractedQuestion, material: ExamPrepMaterial | None = None) -> dict:
    return {
        "id": str(question.id),
        "class_id": str(question.class_id),
        "material_id": str(question.material_id),
        "problem_number": question.problem_number,
        "prompt_text": question.prompt_text,
        "answer_text": question.answer_text,
        "solution_text": question.solution_text,
        "topic_name": question.topic_name,
        "concept_id": str(question.concept_id) if question.concept_id else None,
        "source_ref_json": question.source_ref_json or {},
        "confidence": float(question.confidence) if question.confidence is not None else None,
        "extraction_json": question.extraction_json or {},
        "created_at": question.created_at.isoformat() if question.created_at else None,
        "material": serialize_material(material) if material else None,
    }


def serialize_recommendation(
    rec: ExamPrepRecommendedQuestion,
    question: ExamPrepExtractedQuestion | None = None,
    material: ExamPrepMaterial | None = None,
) -> dict:
    return {
        "id": str(rec.id),
        "class_id": str(rec.class_id),
        "plan_id": str(rec.plan_id),
        "extracted_question_id": str(rec.extracted_question_id),
        "topic_prediction_id": str(rec.topic_prediction_id) if rec.topic_prediction_id else None,
        "rank": int(rec.rank or 0),
        "why_selected": rec.why_selected,
        "evidence_json": rec.evidence_json or {},
        "confidence": float(rec.confidence) if rec.confidence is not None else None,
        "status": rec.status,
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
        "question": serialize_question(question, material) if question else None,
    }


def serialize_plan_summary(plan: ExamPrepPlan) -> dict:
    plan_json = plan.plan_json or {}
    warnings = plan_json.get("warnings") or []
    topics = plan_json.get("topics") or []
    return {
        "id": str(plan.id),
        "class_id": str(plan.class_id),
        "syllabus_id": str(plan.syllabus_id) if plan.syllabus_id else None,
        "title": plan.title,
        "exam_title": plan.exam_title,
        "exam_date": plan.exam_date.isoformat() if plan.exam_date else None,
        "available_minutes_per_day": int(plan.available_minutes_per_day or 0),
        "intensity": plan.intensity,
        "status": plan.status,
        "active": bool(getattr(plan, "active", True)),
        "target_score": float(plan.target_score) if plan.target_score is not None else None,
        "target_grade": plan.target_grade,
        "current_scores_json": plan.current_scores_json or {},
        "weak_topics_json": plan.weak_topics_json or [],
        "selected_material_ids": plan.selected_material_ids or [],
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


async def get_owned_material(db: AsyncSession, user_id: UUID, material_id: UUID) -> ExamPrepMaterial:
    res = await db.execute(
        select(ExamPrepMaterial).where(
            ExamPrepMaterial.id == material_id,
            ExamPrepMaterial.user_id == user_id,
        )
    )
    material = res.scalar_one_or_none()
    if not material:
        raise HTTPException(404, "Material not found")
    await ensure_class_owned(db, user_id, material.class_id)
    return material


async def load_recommendations_for_plan(db: AsyncSession, user_id: UUID, plan: ExamPrepPlan) -> list[dict]:
    rec_res = await db.execute(
        select(ExamPrepRecommendedQuestion)
        .where(
            ExamPrepRecommendedQuestion.user_id == user_id,
            ExamPrepRecommendedQuestion.class_id == plan.class_id,
            ExamPrepRecommendedQuestion.plan_id == plan.id,
        )
        .order_by(ExamPrepRecommendedQuestion.rank.asc(), ExamPrepRecommendedQuestion.created_at.asc())
    )
    recs = rec_res.scalars().all()
    if not recs:
        return []

    question_ids = [rec.extracted_question_id for rec in recs]
    q_res = await db.execute(
        select(ExamPrepExtractedQuestion).where(
            ExamPrepExtractedQuestion.user_id == user_id,
            ExamPrepExtractedQuestion.class_id == plan.class_id,
            ExamPrepExtractedQuestion.id.in_(question_ids),
        )
    )
    questions = {q.id: q for q in q_res.scalars().all()}
    material_ids = [q.material_id for q in questions.values()]
    materials = {}
    if material_ids:
        m_res = await db.execute(
            select(ExamPrepMaterial).where(
                ExamPrepMaterial.user_id == user_id,
                ExamPrepMaterial.class_id == plan.class_id,
                ExamPrepMaterial.id.in_(material_ids),
            )
        )
        materials = {m.id: m for m in m_res.scalars().all()}

    return [
        serialize_recommendation(
            rec,
            questions.get(rec.extracted_question_id),
            materials.get(questions[rec.extracted_question_id].material_id) if rec.extracted_question_id in questions else None,
        )
        for rec in recs
    ]


@router.post("/materials/upload")
async def upload_material(
    class_id: UUID = Form(...),
    material_type: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    await ensure_class_owned(db, user_id, class_id)
    content = await file.read()
    if not content:
        raise HTTPException(400, "Missing file content")

    normalized_type = normalize_material_type(material_type)
    material = ExamPrepMaterial(
        user_id=user_id,
        class_id=class_id,
        filename=file.filename or "exam-prep-material",
        mime_type=file.content_type,
        material_type=normalized_type,
        extraction_status="pending",
        metadata_json={"requested_material_type": material_type},
    )
    db.add(material)
    await db.flush()

    try:
        raw_text, metadata, warnings = await extract_exam_prep_material_text(
            file.filename or "exam-prep-material",
            content,
        )
        material.raw_text = raw_text
        material.extraction_status = "success"
        material.parse_error = None
        material.metadata_json = {
            **(metadata or {}),
            "requested_material_type": material_type,
            "normalized_material_type": normalized_type,
            "warnings": warnings,
        }
    except Exception as exc:
        material.extraction_status = "failed"
        material.parse_error = str(exc)
        material.raw_text = None

    await db.commit()
    await db.refresh(material)

    if material.extraction_status == "failed":
        return {**serialize_material(material), "warnings": [material.parse_error]}

    return serialize_material(material)


@router.get("/materials")
async def list_materials(
    class_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    await ensure_class_owned(db, user_id, class_id)
    res = await db.execute(
        select(ExamPrepMaterial)
        .where(
            ExamPrepMaterial.user_id == user_id,
            ExamPrepMaterial.class_id == class_id,
        )
        .order_by(ExamPrepMaterial.created_at.desc())
    )
    materials = res.scalars().all()
    if not materials:
        return []

    count_res = await db.execute(
        select(ExamPrepExtractedQuestion.material_id, func.count().label("cnt"))
        .where(
            ExamPrepExtractedQuestion.user_id == user_id,
            ExamPrepExtractedQuestion.class_id == class_id,
            ExamPrepExtractedQuestion.material_id.in_([m.id for m in materials]),
        )
        .group_by(ExamPrepExtractedQuestion.material_id)
    )
    counts = {row[0]: row[1] for row in count_res.fetchall()}
    return [serialize_material(material, counts.get(material.id, 0)) for material in materials]


@router.post("/materials/{material_id}/extract-questions")
async def extract_material_questions(
    material_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    material = await get_owned_material(db, user_id, material_id)
    if material.extraction_status != "success" or not material.raw_text:
        raise HTTPException(400, "Material text is not available for question extraction")

    question_payloads, warnings = await extract_questions_from_material_text(
        material.raw_text,
        material.filename,
        material.material_type,
    )

    await db.execute(
        delete(ExamPrepExtractedQuestion).where(
            ExamPrepExtractedQuestion.user_id == user_id,
            ExamPrepExtractedQuestion.class_id == material.class_id,
            ExamPrepExtractedQuestion.material_id == material.id,
        )
    )

    created: list[ExamPrepExtractedQuestion] = []
    for payload in question_payloads:
        question = ExamPrepExtractedQuestion(
            user_id=user_id,
            class_id=material.class_id,
            material_id=material.id,
            problem_number=payload.get("problem_number"),
            prompt_text=payload["prompt_text"],
            answer_text=payload.get("answer_text"),
            solution_text=payload.get("solution_text"),
            topic_name=payload.get("topic_name"),
            source_ref_json=payload.get("source_ref") or {},
            confidence=payload.get("confidence"),
            extraction_json={
                "evidence_quote": payload.get("evidence_quote"),
                "raw_item": payload.get("raw_item"),
                "warnings": warnings,
            },
        )
        db.add(question)
        created.append(question)

    material.metadata_json = {
        **(material.metadata_json or {}),
        "question_extraction_warnings": warnings,
        "question_count": len(created),
    }
    await db.commit()

    q_res = await db.execute(
        select(ExamPrepExtractedQuestion)
        .where(
            ExamPrepExtractedQuestion.user_id == user_id,
            ExamPrepExtractedQuestion.class_id == material.class_id,
            ExamPrepExtractedQuestion.material_id == material.id,
        )
        .order_by(ExamPrepExtractedQuestion.created_at.asc())
    )
    questions = q_res.scalars().all()
    return {
        "material": serialize_material(material, len(questions)),
        "questions": [serialize_question(question, material) for question in questions],
        "warnings": warnings,
    }


@router.get("/materials/{material_id}/questions")
async def list_material_questions(
    material_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    material = await get_owned_material(db, user_id, material_id)
    res = await db.execute(
        select(ExamPrepExtractedQuestion)
        .where(
            ExamPrepExtractedQuestion.user_id == user_id,
            ExamPrepExtractedQuestion.class_id == material.class_id,
            ExamPrepExtractedQuestion.material_id == material.id,
        )
        .order_by(ExamPrepExtractedQuestion.created_at.asc())
    )
    return [serialize_question(question, material) for question in res.scalars().all()]


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
    syllabus = None
    if payload.syllabus_id:
        syllabus = await get_owned_syllabus(db, user_id, payload.class_id, payload.syllabus_id)

    if payload.intensity not in VALID_INTENSITIES:
        raise HTTPException(400, "Intensity must be light, balanced, or aggressive")

    minutes_per_day = payload.minutes_per_day or payload.available_minutes_per_day
    if minutes_per_day < 10:
        raise HTTPException(400, "available_minutes_per_day must be at least 10")

    if minutes_per_day > 480:
        raise HTTPException(400, "available_minutes_per_day is too high")

    exam_title = payload.exam_title.strip() or "Exam"

    exam_date_input = payload.exam_date_iso or payload.exam_date
    if exam_date_input:
        try:
            exam_date = parse_exam_datetime(exam_date_input)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
    elif payload.available_days:
        exam_date = datetime.now(timezone.utc) + timedelta(days=max(1, payload.available_days))
    else:
        raise HTTPException(400, "Provide exam_date_iso, exam_date, or available_days")

    if exam_date <= datetime.now(timezone.utc):
        raise HTTPException(400, "Exam date must be in the future")

    material_query = select(ExamPrepMaterial).where(
        ExamPrepMaterial.user_id == user_id,
        ExamPrepMaterial.class_id == payload.class_id,
    )
    if payload.selected_material_ids:
        material_query = material_query.where(ExamPrepMaterial.id.in_(payload.selected_material_ids))
    materials = (await db.execute(material_query.order_by(ExamPrepMaterial.created_at.desc()))).scalars().all()

    if payload.selected_material_ids and len(materials) != len(set(payload.selected_material_ids)):
        raise HTTPException(404, "One or more selected materials were not found")

    selected_material_ids = [str(material.id) for material in materials]

    questions = []
    if materials:
        q_res = await db.execute(
            select(ExamPrepExtractedQuestion)
            .where(
                ExamPrepExtractedQuestion.user_id == user_id,
                ExamPrepExtractedQuestion.class_id == payload.class_id,
                ExamPrepExtractedQuestion.material_id.in_([m.id for m in materials]),
            )
            .order_by(ExamPrepExtractedQuestion.created_at.asc())
        )
        questions = q_res.scalars().all()

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

    syllabus_topics: list[dict] = []
    topic_warnings: list[str] = []
    if syllabus:
        syllabus_topics, topic_warnings = build_topic_predictions(
            parsed_json=syllabus.parsed_json or {},
            raw_text=syllabus.raw_text,
            concepts=concepts,
            mastery_map=mastery_map,
        )

    material_topics, material_warnings = build_material_topic_predictions(
        materials=materials,
        questions=questions,
        concepts=concepts,
        mastery_map=mastery_map,
        weak_topics=payload.weak_topics or [],
    )
    topics = merge_topic_prediction_sets(material_topics, syllabus_topics)

    plan_days, plan_warnings, starts_on, ends_on = build_plan_days(
        exam_date=exam_date,
        topics=topics,
        available_minutes_per_day=minutes_per_day,
        intensity=payload.intensity,
    )

    all_warnings = []
    for source in [
        (syllabus.parsed_json or {}).get("warnings") if syllabus else [],
        topic_warnings,
        material_warnings,
        plan_warnings,
    ]:
        for warning in (source or []):
            if warning and warning not in all_warnings:
                all_warnings.append(warning)

    if materials and not questions:
        all_warnings.append("Uploaded materials exist, but no extracted questions are available yet.")
    if not materials and not syllabus:
        all_warnings.append("No uploaded materials or syllabus were selected, so evidence is limited.")

    if payload.active:
        await db.execute(
            update(ExamPrepPlan)
            .where(
                ExamPrepPlan.user_id == user_id,
                ExamPrepPlan.class_id == payload.class_id,
            )
            .values(active=False)
        )

    variants = build_plan_variants(plan_days, topics, recommended_count=0, warnings=all_warnings)

    plan = ExamPrepPlan(
        user_id=user_id,
        class_id=payload.class_id,
        syllabus_id=syllabus.id if syllabus else None,
        title=f"{exam_title} prep plan",
        exam_title=exam_title,
        exam_date=exam_date,
        available_minutes_per_day=minutes_per_day,
        intensity=payload.intensity,
        starts_on=starts_on,
        ends_on=ends_on,
        plan_json={
            "topics": topics,
            "plan_days": plan_days,
            "warnings": all_warnings,
            "minimum_plan": variants["minimum_plan"],
            "strong_plan": variants["strong_plan"],
            "evidence_language": "Evidence-based plan based on uploaded materials; not a guaranteed prediction.",
        },
        status="active",
        target_score=payload.target_score,
        target_grade=(payload.target_grade or None),
        current_scores_json=payload.current_scores_json or {},
        weak_topics_json=payload.weak_topics or [],
        selected_material_ids=selected_material_ids,
        active=payload.active,
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
            syllabus_id=syllabus.id if syllabus else None,
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
    recommendation_payloads = select_recommended_questions_for_topics(topics, questions)
    variants = build_plan_variants(
        plan_days,
        topics,
        recommended_count=len(recommendation_payloads),
        warnings=all_warnings,
    )
    plan.plan_json = {
        "topics": topics,
        "plan_days": plan_days,
        "warnings": all_warnings,
        "minimum_plan": variants["minimum_plan"],
        "strong_plan": variants["strong_plan"],
        "evidence_language": "Evidence-based plan based on uploaded materials; not a guaranteed prediction.",
    }

    recommendations: list[ExamPrepRecommendedQuestion] = []
    for payload_rec in recommendation_payloads:
        rec = ExamPrepRecommendedQuestion(
            user_id=user_id,
            class_id=payload.class_id,
            plan_id=plan.id,
            extracted_question_id=UUID(payload_rec["extracted_question_id"]),
            topic_prediction_id=UUID(str(payload_rec["topic_prediction_id"])) if payload_rec.get("topic_prediction_id") else None,
            rank=payload_rec["rank"],
            why_selected=payload_rec["why_selected"],
            evidence_json=payload_rec["evidence_json"],
            confidence=payload_rec["confidence"],
            status="recommended",
        )
        db.add(rec)
        recommendations.append(rec)

    await db.commit()
    await db.refresh(plan)

    recommendation_details = await load_recommendations_for_plan(db, user_id, plan)

    return {
        "exam_prep_plan_id": str(plan.id),
        "topics": topics,
        "plan_days": plan_days,
        "minimum_plan": variants["minimum_plan"],
        "strong_plan": variants["strong_plan"],
        "recommended_questions": recommendation_details,
        "warnings": all_warnings,
    }


@router.get("/plans")
async def list_plans(
    class_id: UUID,
    active: bool | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    await ensure_class_owned(db, user_id, class_id)
    query = select(ExamPrepPlan).where(
        ExamPrepPlan.user_id == user_id,
        ExamPrepPlan.class_id == class_id,
    )
    if active is not None:
        query = query.where(ExamPrepPlan.active == active)
    res = await db.execute(
        query
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
        "minimum_plan": (plan.plan_json or {}).get("minimum_plan"),
        "strong_plan": (plan.plan_json or {}).get("strong_plan"),
        "tasks": tasks,
        "recommended_questions": await load_recommendations_for_plan(db, user_id, plan),
    }


@router.get("/plans/{plan_id}/questions")
async def get_plan_questions(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    plan = await get_owned_plan(db, user_id, plan_id)
    return await load_recommendations_for_plan(db, user_id, plan)


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
