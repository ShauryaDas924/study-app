

from sqlalchemy import Column, Text, DateTime, ForeignKey, Float, Integer, Boolean, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func, text
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.db import Base


# ----------------------
# CLASSES
# ----------------------
class Class(Base):
    __tablename__ = "classes"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(Text, nullable=False)
    term = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


# ----------------------
# NOTES
# ----------------------
class Note(Base):
    __tablename__ = "notes"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id"), nullable=False, index=True)

    title = Column(Text, nullable=False)
    content_json = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    
    extraction_status = Column(Text, nullable=False, server_default=text("'idle'"))
    extraction_progress = Column(Integer, nullable=False, server_default=text("0"))
    extraction_mode = Column(Text, nullable=True)
    extraction_error = Column(Text, nullable=True)
    extraction_started_at = Column(DateTime(timezone=True), nullable=True)
    extraction_finished_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    concepts = relationship("NoteConcept", back_populates="note", cascade="all, delete-orphan")


# ----------------------
# CONCEPTS
# ----------------------
class Concept(Base):
    __tablename__ = "concepts"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id"), nullable=False, index=True)

    name = Column(Text, nullable=False)

    # NEW GROUNDING FIELDS
    description = Column(Text, nullable=True)
    definition = Column(Text, nullable=True)
    when_to_use = Column(Text, nullable=True)
    pitfalls = Column(Text, nullable=True)
    confidence = Column(Float, nullable=False, server_default=text("0.5"))
    evidence = Column(Text, nullable=True)
    type = Column(Text, nullable=True)
    related_concepts = Column(JSONB, nullable=True)
    embedding = Column(Vector(1536), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    notes = relationship("NoteConcept", back_populates="concept", cascade="all, delete-orphan")
    worked_example = Column(Text, nullable=True)
    intuition = Column(Text, nullable=True)


# ----------------------
# NOTE ↔ CONCEPT LINK
# ----------------------
class NoteConcept(Base):
    __tablename__ = "note_concepts"

    note_id = Column(UUID(as_uuid=True), ForeignKey("notes.id"), primary_key=True)
    concept_id = Column(UUID(as_uuid=True), ForeignKey("concepts.id"), primary_key=True)

    weight = Column(Float, nullable=False, server_default=text("1.0"))

    note = relationship("Note", back_populates="concepts")
    concept = relationship("Concept", back_populates="notes")


# ----------------------
# PRACTICE SETS
# ----------------------
class PracticeSet(Base):
    __tablename__ = "practice_sets"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id"), nullable=False, index=True)

    settings_json = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    source = Column(Text, nullable=False, server_default=text("'notes'"))

    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ----------------------
# QUESTIONS
# ----------------------
class Question(Base):
    __tablename__ = "questions"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    practice_set_id = Column(UUID(as_uuid=True), ForeignKey("practice_sets.id"), nullable=False, index=True)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    concept_id = Column(UUID(as_uuid=True), ForeignKey("concepts.id"), nullable=True, index=True)

    qtype = Column(Text, nullable=False)  # "mcq" | "short"
    prompt = Column(Text, nullable=False)
    

    choices_json = Column(JSONB, nullable=True)
    answer_key_json = Column(JSONB, nullable=True)
    solution = Column(Text, nullable=False)
    
    difficulty = Column(Integer, nullable=False, server_default=text("3"))
    question_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ----------------------
# ATTEMPTS
# ----------------------
class Attempt(Base):
    __tablename__ = "attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("exam_sessions.id"), nullable=True, index=True)
    concept_id = Column(UUID(as_uuid=True), ForeignKey("concepts.id"), nullable=True, index=True)

    user_answer_json = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    is_correct = Column(Boolean, nullable=False)
    confidence = Column(Integer, nullable=False, server_default=text("3"))
    time_spent_sec = Column(Integer, nullable=False, server_default=text("0"))

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MistakeLog(Base):
    __tablename__ = "mistake_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    concept_id = Column(UUID(as_uuid=True), ForeignKey("concepts.id"), nullable=True, index=True)

    tag = Column(Text, nullable=True, index=True)
    mistake_text = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ----------------------
# STUDENT PITFALL MEMORY
# ----------------------
class StudentPitfall(Base):
    __tablename__ = "student_pitfalls"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))

    user_id = Column(UUID(as_uuid=True), index=True)
    class_id = Column(UUID(as_uuid=True), index=True)

    pitfall = Column(Text, nullable=False)        # e.g. timeline_construction
    explanation = Column(Text, nullable=True)     # explanation text

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    
    
class WorkReviewSession(Base):
    __tablename__ = "work_review_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))

    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    class_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    filename = Column(Text, nullable=True)
    extracted_text = Column(Text, nullable=True)
    image_base64 = Column(Text, nullable=True)   # MVP storage, can move later
    source_type = Column(Text, nullable=False, server_default=text("'image'"))  # image | pdf | text

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    
class StepReview(Base):
    __tablename__ = "step_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))

    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    class_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("work_review_sessions.id"), nullable=False, index=True)

    user_prompt = Column(Text, nullable=True)          # "I'm confused at step 3"
    selected_step = Column(Text, nullable=True)        # raw text or user step description
    selected_region = Column(JSONB, nullable=True)     # future: x/y/width/height if you add selection box

    concept_name = Column(Text, nullable=True)
    step_verdict = Column(Text, nullable=True)         # correct | correct_but_incomplete | wrong_concept | algebra_slip | etc.
    error_type = Column(Text, nullable=True)
    root_cause_step = Column(Text, nullable=True)

    correct_parts = Column(JSONB, nullable=True)
    issues = Column(JSONB, nullable=True)

    next_step = Column(Text, nullable=True)
    next_time_rule = Column(Text, nullable=True)
    pitfall_tag = Column(Text, nullable=True)

    confidence = Column(Float, nullable=True)
    raw_feedback = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
# ----------------------
# MASTERY
# ----------------------
class Mastery(Base):
    __tablename__ = "mastery"

    user_id = Column(UUID(as_uuid=True), primary_key=True)
    concept_id = Column(UUID(as_uuid=True), ForeignKey("concepts.id"), primary_key=True)

    mastery_prob = Column(Float, nullable=False, server_default=text("0.35"))
    last_practiced_at = Column(DateTime(timezone=True), nullable=True)
    last_updated_at = Column(DateTime(timezone=True), server_default=func.now())
    next_review_at = Column(DateTime(timezone=True), nullable=True)


# ----------------------
# EXAMS
# ----------------------
class Exam(Base):
    __tablename__ = "exams"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id"), nullable=False, index=True)

    title = Column(Text, nullable=False)
    exam_date = Column(DateTime(timezone=True), nullable=False)
    weight = Column(Integer, nullable=False, server_default=text("3"))

    topics_json = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    

class ExamInsight(Base):
    __tablename__ = "exam_insights"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))

    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id"), nullable=False, index=True)

    filename = Column(Text, nullable=False)

    extracted_text = Column(Text, nullable=True)
    analysis = Column(Text, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ----------------------
# EXAM PREP PLANNER
# ----------------------
class ExamPrepSyllabus(Base):
    __tablename__ = "exam_prep_syllabi"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id"), nullable=False, index=True)

    filename = Column(Text, nullable=False)
    mime_type = Column(Text, nullable=True)
    raw_text = Column(Text, nullable=False)
    parsed_json = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    parse_status = Column(Text, nullable=False, server_default=text("'pending'"))
    parse_error = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class ExamPrepPlan(Base):
    __tablename__ = "exam_prep_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id"), nullable=False, index=True)
    syllabus_id = Column(UUID(as_uuid=True), ForeignKey("exam_prep_syllabi.id"), nullable=True, index=True)

    title = Column(Text, nullable=False)
    exam_title = Column(Text, nullable=False)
    exam_date = Column(DateTime(timezone=True), nullable=False, index=True)
    available_minutes_per_day = Column(Integer, nullable=False, server_default=text("60"))
    intensity = Column(Text, nullable=False, server_default=text("'balanced'"))
    starts_on = Column(DateTime(timezone=True), nullable=False)
    ends_on = Column(DateTime(timezone=True), nullable=False)
    plan_json = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    status = Column(Text, nullable=False, server_default=text("'active'"))
    target_score = Column(Numeric, nullable=True)
    target_grade = Column(Text, nullable=True)
    current_scores_json = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    weak_topics_json = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    selected_material_ids = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    active = Column(Boolean, nullable=False, server_default=text("true"))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class ExamPrepTopicPrediction(Base):
    __tablename__ = "exam_prep_topic_predictions"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id"), nullable=False, index=True)
    syllabus_id = Column(UUID(as_uuid=True), ForeignKey("exam_prep_syllabi.id"), nullable=True, index=True)
    exam_prep_plan_id = Column(UUID(as_uuid=True), ForeignKey("exam_prep_plans.id"), nullable=True, index=True)

    topic_name = Column(Text, nullable=False)
    matched_concept_ids = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    exam_likelihood_score = Column(Float, nullable=False, server_default=text("0"))
    student_priority_score = Column(Float, nullable=False, server_default=text("0"))
    confidence = Column(Text, nullable=False, server_default=text("'low'"))
    evidence = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    missing_data = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    recommended_study_action = Column(Text, nullable=False)
    scoring_json = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ExamPrepTask(Base):
    __tablename__ = "exam_prep_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id"), nullable=False, index=True)
    exam_prep_plan_id = Column(UUID(as_uuid=True), ForeignKey("exam_prep_plans.id"), nullable=False, index=True)
    exam_topic_prediction_id = Column(UUID(as_uuid=True), ForeignKey("exam_prep_topic_predictions.id"), nullable=True, index=True)
    concept_id = Column(UUID(as_uuid=True), ForeignKey("concepts.id"), nullable=True, index=True)

    planned_for = Column(DateTime(timezone=True), nullable=False, index=True)
    task_type = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    minutes = Column(Integer, nullable=False, server_default=text("0"))
    rationale = Column(Text, nullable=True)
    status = Column(Text, nullable=False, server_default=text("'pending'"), index=True)
    source_json = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)


class ExamPrepMaterial(Base):
    __tablename__ = "exam_prep_materials"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)

    filename = Column(Text, nullable=False)
    mime_type = Column(Text, nullable=True)
    material_type = Column(Text, nullable=False)
    raw_text = Column(Text, nullable=True)
    extraction_status = Column(Text, nullable=False, server_default=text("'pending'"))
    parse_error = Column(Text, nullable=True)
    metadata_json = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class ExamPrepExtractedQuestion(Base):
    __tablename__ = "exam_prep_extracted_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    material_id = Column(UUID(as_uuid=True), ForeignKey("exam_prep_materials.id", ondelete="CASCADE"), nullable=False, index=True)

    problem_number = Column(Text, nullable=True)
    prompt_text = Column(Text, nullable=False)
    answer_text = Column(Text, nullable=True)
    solution_text = Column(Text, nullable=True)
    topic_name = Column(Text, nullable=True, index=True)
    concept_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    source_ref_json = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    confidence = Column(Numeric, nullable=True)
    extraction_json = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    status = Column(Text, nullable=False, server_default=text("'active'"), index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ExamPrepRecommendedQuestion(Base):
    __tablename__ = "exam_prep_recommended_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("exam_prep_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    extracted_question_id = Column(UUID(as_uuid=True), ForeignKey("exam_prep_extracted_questions.id", ondelete="CASCADE"), nullable=False, index=True)

    topic_prediction_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    rank = Column(Integer, nullable=False, server_default=text("0"))
    why_selected = Column(Text, nullable=True)
    evidence_json = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    confidence = Column(Numeric, nullable=True)
    status = Column(Text, nullable=False, server_default=text("'recommended'"), index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ExamLockdownSession(Base):
    __tablename__ = "exam_lockdown_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("exam_prep_plans.id", ondelete="CASCADE"), nullable=False, index=True)

    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(Text, nullable=False, server_default=text("'active'"), index=True)


class ExamLockdownAttempt(Base):
    __tablename__ = "exam_lockdown_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("exam_lockdown_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("exam_prep_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    recommended_question_id = Column(UUID(as_uuid=True), ForeignKey("exam_prep_recommended_questions.id", ondelete="CASCADE"), nullable=False, index=True)

    user_answer_text = Column(Text, nullable=True)
    confidence = Column(Integer, nullable=True)
    time_spent_sec = Column(Integer, nullable=True)
    tutor_feedback_json = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    status = Column(Text, nullable=False, server_default=text("'attempted'"), index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ExamLockdownPitfall(Base):
    __tablename__ = "exam_lockdown_pitfalls"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    attempt_id = Column(UUID(as_uuid=True), ForeignKey("exam_lockdown_attempts.id", ondelete="CASCADE"), nullable=True, index=True)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("exam_prep_plans.id", ondelete="CASCADE"), nullable=False, index=True)

    topic_name = Column(Text, nullable=True, index=True)
    category = Column(Text, nullable=False, index=True)
    tag = Column(Text, nullable=True)
    explanation = Column(Text, nullable=True)
    evidence_json = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    created_at = Column(DateTime(timezone=True), server_default=func.now())

# ----------------------
# EXAM SESSIONS
# ----------------------
class ExamSession(Base):
    __tablename__ = "exam_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id"), nullable=False)

    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)

    time_limit_min = Column(Integer, nullable=False)
    
class ConceptDependency(Base):
    __tablename__ = "concept_dependencies"

    concept_id = Column(UUID(as_uuid=True), ForeignKey("concepts.id"), primary_key=True)
    depends_on_concept_id = Column(UUID(as_uuid=True), ForeignKey("concepts.id"), primary_key=True)

    weight = Column(Float, nullable=False, server_default=text("1.0"))
    
class MasteryHistory(Base):
    __tablename__ = "mastery_history"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True))
    concept_id = Column(UUID(as_uuid=True))
    mastery_prob = Column(Float)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())

class TutorMemory(Base):
    __tablename__ = "tutor_memory"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True))
    concept_id = Column(UUID(as_uuid=True))
    note = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ----------------------
# CHAT MEMORY (HOMEWORK)
# ----------------------
class ChatMemory(Base):
    __tablename__ = "chat_memories"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))

    user_id = Column(UUID(as_uuid=True), index=True)
    class_id = Column(UUID(as_uuid=True), index=True)
  

    role = Column(Text)   # "user" or "assistant"
    content = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ----------------------
# FLASHCARDS
# ----------------------
# ----------------------
# FLASHCARDS
# ----------------------
class Flashcard(Base):
    __tablename__ = "flashcards"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))

    user_id = Column(UUID(as_uuid=True), index=True)
    class_id = Column(UUID(as_uuid=True), index=True)

    # ✅ ADD THIS (safe + backwards compatible)
    note_id = Column(UUID(as_uuid=True), ForeignKey("notes.id"), nullable=True, index=True)

    concept_id = Column(UUID(as_uuid=True), ForeignKey("concepts.id"), nullable=True)

    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False, server_default=text("0.5"))
    next_review = Column(DateTime(timezone=True), server_default=func.now())
    card_type = Column(Text, nullable=True)
    source_evidence = Column(Text, nullable=True)
    why_this_card_matters = Column(Text, nullable=True)
    interval_days = Column(Integer, server_default=text("1"))
    review_count = Column(Integer, server_default=text("0"))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
# ----------------------
# FLASHCARD SRS
# ----------------------
class FlashcardState(Base):
    __tablename__ = "flashcard_states"

    user_id = Column(UUID(as_uuid=True), primary_key=True)
    concept_id = Column(UUID(as_uuid=True), ForeignKey("concepts.id"), primary_key=True)

    ease = Column(Float, server_default=text("2.5"))
    interval_days = Column(Integer, server_default=text("1"))

    last_reviewed_at = Column(DateTime(timezone=True), nullable=True)
    due_at = Column(DateTime(timezone=True), nullable=True)


class FlashcardSession(Base):
    __tablename__ = "flashcard_sessions"

    user_id = Column(UUID(as_uuid=True), primary_key=True)
    note_id = Column(UUID(as_uuid=True), primary_key=True)

    current_index = Column(Integer, nullable=False, server_default=text("0"))

    mode = Column(Text, nullable=True)

    # exact deck order currently being studied
    deck_ids = Column(JSONB, nullable=True)
    all_deck_ids = Column(JSONB, nullable=True)
    # piles
    hard_ids = Column(JSONB, nullable=True)
    medium_ids = Column(JSONB, nullable=True)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
