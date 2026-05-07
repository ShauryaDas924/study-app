
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, select
from pydantic import BaseModel
from uuid import UUID
from sqlalchemy import delete

from app.db import get_db

from app.services.auth import get_current_user_id

from app.models import (
    Note,
    Concept,
    Mastery,
    NoteConcept,
    Flashcard,
    FlashcardState,
    FlashcardSession,
    Class,
    Attempt,
    MistakeLog,
    Question,
    PracticeSet,
    TutorMemory,
    ConceptDependency,
    ChatMemory,
    StudentPitfall,
    WorkReviewSession,
    StepReview,
    Exam,
    ExamInsight,
    ExamSession,
    ExamPrepPlan,
    ExamPrepSyllabus,
    ExamPrepTask,
    ExamPrepTopicPrediction,
    MasteryHistory,
)
router = APIRouter(prefix="/classes", tags=["classes"])

class ClassIn(BaseModel):
    name: str
    term: str | None = None

@router.post("")
async def create_class(payload: ClassIn, db: AsyncSession = Depends(get_db), user_id: UUID = Depends(get_current_user_id)):
    obj = Class(user_id=user_id, name=payload.name, term=payload.term)
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return {"id": str(obj.id), "name": obj.name, "term": obj.term}

@router.get("")
async def list_classes(db: AsyncSession = Depends(get_db), user_id: UUID = Depends(get_current_user_id)):
    res = await db.execute(select(Class).where(Class.user_id == user_id))
    rows = res.scalars().all()
    return [{"id": str(c.id), "name": c.name, "term": c.term} for c in rows]

@router.delete("/{class_id}/clear")
async def clear_class_data(
    class_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    class_res = await db.execute(
        select(Class.id).where(Class.id == class_id, Class.user_id == user_id)
    )
    if not class_res.scalar_one_or_none():
        raise HTTPException(404, "Class not found")

    # -----------------------------
    # 0. Get concept IDs
    # -----------------------------
    res = await db.execute(
        select(Concept.id).where(
            Concept.user_id == user_id,
            Concept.class_id == class_id
        )
    )
    concept_ids = [r[0] for r in res.fetchall()]

    # -----------------------------
    # 1. Delete FlashcardState
    # -----------------------------
    await db.execute(
        delete(FlashcardState).where(
            FlashcardState.user_id == user_id,
            FlashcardState.concept_id.in_(concept_ids)
        )
    )

    # -----------------------------
    # 2. Delete Flashcards
    # -----------------------------
    await db.execute(
        delete(Flashcard).where(
            Flashcard.user_id == user_id,
            Flashcard.concept_id.in_(concept_ids)
        )
    )

    # -----------------------------
    # 3. Delete Mastery
    # -----------------------------
    await db.execute(
        delete(Mastery).where(
            Mastery.user_id == user_id,
            Mastery.concept_id.in_(concept_ids)
        )
    )

    # -----------------------------
    # 4. Delete Attempts
    # -----------------------------
    await db.execute(
        delete(Attempt).where(
            Attempt.user_id == user_id,
            Attempt.concept_id.in_(concept_ids)
        )
    )

    # -----------------------------
    # 5. Delete Mistake Logs
    # -----------------------------
    await db.execute(
        delete(MistakeLog).where(
            MistakeLog.user_id == user_id,
            MistakeLog.concept_id.in_(concept_ids)
        )
    )

    # -----------------------------
    # 6. Delete Questions
    # -----------------------------
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

    # -----------------------------
    # 7. Delete TutorMemory
    # -----------------------------
    await db.execute(
        delete(TutorMemory).where(
            TutorMemory.user_id == user_id,
            TutorMemory.concept_id.in_(concept_ids)
        )
    )
    
    # -----------------------------
    # 7.5 Delete ChatMemory
    # -----------------------------
    await db.execute(
        delete(ChatMemory).where(
            ChatMemory.user_id == user_id,
            ChatMemory.class_id == class_id
        )
    )

    # -----------------------------
    # 7.6 Delete Student Pitfalls
    # -----------------------------
    await db.execute(
        delete(StudentPitfall).where(
            StudentPitfall.user_id == user_id,
            StudentPitfall.class_id == class_id
        )
    )

    # -----------------------------
    # 7.7 Delete Step Reviews
    #-----------------------------
    await db.execute(
        delete(StepReview).where(
            StepReview.user_id == user_id,
            StepReview.class_id == class_id
        )
    )

    # -----------------------------
    # 7.8 Delete Work Review Sessions
    # -----------------------------
    await db.execute(
        delete(WorkReviewSession).where(
            WorkReviewSession.user_id == user_id,
            WorkReviewSession.class_id == class_id
        )
    )

    # -----------------------------
    # 7.9 Delete Exam Prep Planner data
    # -----------------------------
    await db.execute(
        delete(ExamPrepTask).where(
            ExamPrepTask.user_id == user_id,
            ExamPrepTask.class_id == class_id
        )
    )
    await db.execute(
        delete(ExamPrepTopicPrediction).where(
            ExamPrepTopicPrediction.user_id == user_id,
            ExamPrepTopicPrediction.class_id == class_id
        )
    )
    await db.execute(
        delete(ExamPrepPlan).where(
            ExamPrepPlan.user_id == user_id,
            ExamPrepPlan.class_id == class_id
        )
    )
    await db.execute(
        delete(ExamPrepSyllabus).where(
            ExamPrepSyllabus.user_id == user_id,
            ExamPrepSyllabus.class_id == class_id
        )
    )
    
    # -----------------------------
    # 8. Delete Concept Dependencies
    # -----------------------------
    await db.execute(
        delete(ConceptDependency).where(
            ConceptDependency.concept_id.in_(concept_ids)
        )
    )

    # -----------------------------
    # 9. Delete NoteConcept links
    # -----------------------------
    await db.execute(
        delete(NoteConcept).where(
            NoteConcept.concept_id.in_(concept_ids)
        )
    )

    # -----------------------------
    # 10. Delete Concepts
    # -----------------------------
    await db.execute(
        delete(Concept).where(
            Concept.user_id == user_id,
            Concept.class_id == class_id
        )
    )

    # -----------------------------
    # 11. Delete Notes
    # -----------------------------
    await db.execute(
        delete(Note).where(
            Note.user_id == user_id,
            Note.class_id == class_id
        )
    )

    await db.commit()

    return {"message": "Class data cleared"}


@router.delete("/{class_id}")
async def delete_class(
    class_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    class_res = await db.execute(
        select(Class.id).where(Class.id == class_id, Class.user_id == user_id)
    )
    if not class_res.scalar_one_or_none():
        raise HTTPException(404, "Class not found")

    note_res = await db.execute(
        select(Note.id).where(Note.user_id == user_id, Note.class_id == class_id)
    )
    note_ids = [r[0] for r in note_res.fetchall()]

    concept_res = await db.execute(
        select(Concept.id).where(Concept.user_id == user_id, Concept.class_id == class_id)
    )
    concept_ids = [r[0] for r in concept_res.fetchall()]

    question_res = await db.execute(
        select(Question.id).where(Question.user_id == user_id, Question.class_id == class_id)
    )
    question_ids = [r[0] for r in question_res.fetchall()]

    exam_session_res = await db.execute(
        select(ExamSession.id).where(
            ExamSession.user_id == user_id,
            ExamSession.class_id == class_id,
        )
    )
    exam_session_ids = [r[0] for r in exam_session_res.fetchall()]

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
        delete(TutorMemory).where(
            TutorMemory.user_id == user_id,
            TutorMemory.concept_id.in_(concept_ids),
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
        delete(ExamInsight).where(
            ExamInsight.user_id == user_id,
            ExamInsight.class_id == class_id,
        )
    )
    await db.execute(
        delete(Exam).where(
            Exam.user_id == user_id,
            Exam.class_id == class_id,
        )
    )
    await db.execute(
        delete(ExamSession).where(
            ExamSession.user_id == user_id,
            ExamSession.class_id == class_id,
        )
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
        delete(Concept).where(
            Concept.user_id == user_id,
            Concept.class_id == class_id,
        )
    )
    await db.execute(
        delete(Note).where(
            Note.user_id == user_id,
            Note.class_id == class_id,
        )
    )
    await db.execute(delete(Class).where(Class.id == class_id, Class.user_id == user_id))

    await db.commit()

    return {"message": "Class deleted"}
