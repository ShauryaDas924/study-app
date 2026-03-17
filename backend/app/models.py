

from sqlalchemy import Column, Text, DateTime, ForeignKey, Float, Integer, Boolean
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
