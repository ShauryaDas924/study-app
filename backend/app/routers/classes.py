from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import (
    Attempt,
    ChatMemory,
    Class,
    Concept,
    ConceptDependency,
    Exam,
    ExamInsight,
    ExamLockdownAttempt,
    ExamLockdownPitfall,
    ExamLockdownSession,
    ExamPrepExtractedQuestion,
    ExamPrepMaterial,
    ExamPrepPlan,
    ExamPrepRecommendedQuestion,
    ExamPrepSyllabus,
    ExamPrepTask,
    ExamPrepTopicPrediction,
    ExamSession,
    Flashcard,
    FlashcardSession,
    FlashcardState,
    Mastery,
    MasteryHistory,
    MistakeLog,
    Note,
    NoteConcept,
    PracticeSet,
    Question,
    StepReview,
    StudentPitfall,
    TutorMemory,
    WorkReviewSession,
)
from app.services.auth import get_current_user_id


router = APIRouter(prefix="/classes", tags=["classes"])


class ClassIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    term: str | None = Field(default=None, max_length=120)


async def _owned_class_or_404(
    db: AsyncSession,
    *,
    class_id: UUID,
    user_id: UUID,
) -> None:
    result = await db.execute(
        select(Class.id).where(Class.id == class_id, Class.user_id == user_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(404, "Class not found")


async def _purge_class_data(
    db: AsyncSession,
    *,
    class_id: UUID,
    user_id: UUID,
) -> None:
    """Delete user-owned class data in foreign-key-safe order, preserving the class row."""
    note_rows = await db.execute(
        select(Note.id).where(Note.user_id == user_id, Note.class_id == class_id)
    )
    note_ids = list(note_rows.scalars().all())

    concept_rows = await db.execute(
        select(Concept.id).where(Concept.user_id == user_id, Concept.class_id == class_id)
    )
    concept_ids = list(concept_rows.scalars().all())

    question_rows = await db.execute(
        select(Question.id).where(Question.user_id == user_id, Question.class_id == class_id)
    )
    question_ids = list(question_rows.scalars().all())

    exam_session_rows = await db.execute(
        select(ExamSession.id).where(
            ExamSession.user_id == user_id,
            ExamSession.class_id == class_id,
        )
    )
    exam_session_ids = list(exam_session_rows.scalars().all())

    await db.execute(
        delete(FlashcardSession).where(
            FlashcardSession.user_id == user_id,
            FlashcardSession.note_id.in_(note_ids),
        )
    )
    await db.execute(
        delete(FlashcardState).where(
            FlashcardState.user_id == user_id,
            FlashcardState.concept_id.in_(concept_ids),
        )
    )
    await db.execute(
        delete(Flashcard).where(
            Flashcard.user_id == user_id,
            or_(
                Flashcard.class_id == class_id,
                Flashcard.note_id.in_(note_ids),
                Flashcard.concept_id.in_(concept_ids),
            ),
        )
    )
    await db.execute(
        delete(Mastery).where(
            Mastery.user_id == user_id,
            Mastery.concept_id.in_(concept_ids),
        )
    )
    await db.execute(
        delete(MasteryHistory).where(
            MasteryHistory.user_id == user_id,
            MasteryHistory.concept_id.in_(concept_ids),
        )
    )

    await db.execute(
        delete(Attempt).where(
            Attempt.user_id == user_id,
            or_(
                Attempt.question_id.in_(question_ids),
                Attempt.session_id.in_(exam_session_ids),
                Attempt.concept_id.in_(concept_ids),
            ),
        )
    )
    await db.execute(
        delete(MistakeLog).where(
            MistakeLog.user_id == user_id,
            MistakeLog.concept_id.in_(concept_ids),
        )
    )
    await db.execute(
        delete(TutorMemory).where(
            TutorMemory.user_id == user_id,
            TutorMemory.concept_id.in_(concept_ids),
        )
    )
    await db.execute(
        delete(Question).where(
            Question.user_id == user_id,
            Question.class_id == class_id,
        )
    )
    await db.execute(
        delete(PracticeSet).where(
            PracticeSet.user_id == user_id,
            PracticeSet.class_id == class_id,
        )
    )
    await db.execute(
        delete(ExamSession).where(
            ExamSession.user_id == user_id,
            ExamSession.class_id == class_id,
        )
    )

    await db.execute(
        delete(ChatMemory).where(
            ChatMemory.user_id == user_id,
            ChatMemory.class_id == class_id,
        )
    )
    await db.execute(
        delete(StudentPitfall).where(
            StudentPitfall.user_id == user_id,
            StudentPitfall.class_id == class_id,
        )
    )
    await db.execute(
        delete(StepReview).where(
            StepReview.user_id == user_id,
            StepReview.class_id == class_id,
        )
    )
    await db.execute(
        delete(WorkReviewSession).where(
            WorkReviewSession.user_id == user_id,
            WorkReviewSession.class_id == class_id,
        )
    )

    await db.execute(
        delete(ExamLockdownPitfall).where(
            ExamLockdownPitfall.user_id == user_id,
            ExamLockdownPitfall.class_id == class_id,
        )
    )
    await db.execute(
        delete(ExamLockdownAttempt).where(
            ExamLockdownAttempt.user_id == user_id,
            ExamLockdownAttempt.class_id == class_id,
        )
    )
    await db.execute(
        delete(ExamLockdownSession).where(
            ExamLockdownSession.user_id == user_id,
            ExamLockdownSession.class_id == class_id,
        )
    )
    await db.execute(
        delete(ExamPrepRecommendedQuestion).where(
            ExamPrepRecommendedQuestion.user_id == user_id,
            ExamPrepRecommendedQuestion.class_id == class_id,
        )
    )
    await db.execute(
        delete(ExamPrepTask).where(
            ExamPrepTask.user_id == user_id,
            ExamPrepTask.class_id == class_id,
        )
    )
    await db.execute(
        delete(ExamPrepTopicPrediction).where(
            ExamPrepTopicPrediction.user_id == user_id,
            ExamPrepTopicPrediction.class_id == class_id,
        )
    )
    await db.execute(
        delete(ExamPrepPlan).where(
            ExamPrepPlan.user_id == user_id,
            ExamPrepPlan.class_id == class_id,
        )
    )
    await db.execute(
        delete(ExamPrepSyllabus).where(
            ExamPrepSyllabus.user_id == user_id,
            ExamPrepSyllabus.class_id == class_id,
        )
    )
    await db.execute(
        delete(ExamPrepExtractedQuestion).where(
            ExamPrepExtractedQuestion.user_id == user_id,
            ExamPrepExtractedQuestion.class_id == class_id,
        )
    )
    await db.execute(
        delete(ExamPrepMaterial).where(
            ExamPrepMaterial.user_id == user_id,
            ExamPrepMaterial.class_id == class_id,
        )
    )

    await db.execute(
        delete(ExamInsight).where(
            ExamInsight.user_id == user_id,
            ExamInsight.class_id == class_id,
        )
    )
    await db.execute(
        delete(Exam).where(Exam.user_id == user_id, Exam.class_id == class_id)
    )
    await db.execute(
        delete(ConceptDependency).where(
            or_(
                ConceptDependency.concept_id.in_(concept_ids),
                ConceptDependency.depends_on_concept_id.in_(concept_ids),
            )
        )
    )
    await db.execute(
        delete(NoteConcept).where(
            or_(
                NoteConcept.note_id.in_(note_ids),
                NoteConcept.concept_id.in_(concept_ids),
            )
        )
    )
    await db.execute(
        delete(Concept).where(Concept.user_id == user_id, Concept.class_id == class_id)
    )
    await db.execute(
        delete(Note).where(Note.user_id == user_id, Note.class_id == class_id)
    )


@router.post("")
async def create_class(
    payload: ClassIn,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    obj = Class(user_id=user_id, name=payload.name.strip(), term=payload.term)
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return {"id": str(obj.id), "name": obj.name, "term": obj.term}


@router.get("")
async def list_classes(
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    result = await db.execute(select(Class).where(Class.user_id == user_id))
    return [
        {"id": str(item.id), "name": item.name, "term": item.term}
        for item in result.scalars().all()
    ]


@router.delete("/{class_id}/clear")
async def clear_class_data(
    class_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    await _owned_class_or_404(db, class_id=class_id, user_id=user_id)
    await _purge_class_data(db, class_id=class_id, user_id=user_id)
    await db.commit()
    return {"message": "Class data cleared"}


@router.delete("/{class_id}")
async def delete_class(
    class_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    await _owned_class_or_404(db, class_id=class_id, user_id=user_id)
    await _purge_class_data(db, class_id=class_id, user_id=user_id)
    await db.execute(delete(Class).where(Class.id == class_id, Class.user_id == user_id))
    await db.commit()
    return {"message": "Class deleted"}
