from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from app.models import Concept, ChatMemory
from app.db import get_db
from app.services.llm import client, top_k_concepts, grounding_confidence
from app.services.file_extraction import extract_text
from app.services.auth import get_current_user_id
from app.models import Mastery
from app.services.mastery import update_mastery_value
from app.services.file_extraction import split_homework_questions
router = APIRouter(prefix="/homework", tags=["homework"])


class HWIn(BaseModel):
    class_id: str
    question: str


# ----------------------
# TEXT QUESTION
# ----------------------
@router.post("/help")
async def homework_help(
    body: HWIn,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):

    # ✅ Validate class_id
    if not body.class_id:
        raise HTTPException(400, "class_id required")

    try:
        class_uuid = UUID(body.class_id)
    except:
        raise HTTPException(400, "Invalid class_id")
        
    # -------- SAVE USER MESSAGE --------
    db.add(ChatMemory(
        user_id=current_user_id,
        class_id=class_uuid,
        role="user",
        content=body.question
    ))
    # 1) Get concepts
    res = await db.execute(
        select(Concept).where(
            Concept.class_id == class_uuid,
            Concept.user_id == current_user_id
        )
    )

    concepts = res.scalars().all()

    top_concepts = await top_k_concepts(
        body.question,
        concepts,
        k=5
    )

    context = "\n\n".join([
        f"""
    CONCEPT KNOWLEDGE

    Name: {c.name}

    Definition:
    {c.definition or c.description}

    When to use:
    {c.when_to_use or "Apply when this concept appears in relevant problems."}
    
    Common pitfall:
    {c.pitfalls or "Students often misapply this concept."}
    """
        for c in top_concepts
    ])[:4000]
    # -------- MISCONCEPTION DETECTION --------
    mis_resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role":"system","content":
            "Detect if student shows a misconception. \
            Return short phrase or 'none'."},
            {"role":"user","content":body.question}
        ],
        temperature=0
    )

    mis = mis_resp.choices[0].message.content

    # -------- HANDLE MISCONCEPTIONS --------
    if mis.lower().strip() != "none":

        for c in top_concepts:

            m = await db.get(
                Mastery,
                {"user_id": current_user_id, "concept_id": c.id}
            )

            if m:

                # incorrect attempt → update mastery using Bayesian model
                new_mastery = update_mastery_value(
                    mastery=m.mastery_prob,
                    correct=False,
                    difficulty=3,      # neutral difficulty
                    confidence=2,      # low confidence assumption
                    time_spent=30      # placeholder
                )

                m.mastery_prob = new_mastery

        db.add(ChatMemory(
            user_id=current_user_id,
            class_id=class_uuid,
            role="system",
            content=f"Detected misconception: {mis}"
        ))
    
    # -------- LOAD LAST CHATS --------
    mem_res = await db.execute(
        select(ChatMemory.role, ChatMemory.content)
        .where(
            ChatMemory.user_id == current_user_id,
            ChatMemory.class_id == class_uuid
        )
        .order_by(ChatMemory.created_at.desc())
        .limit(6)
    )

    history = mem_res.fetchall()

    history_text = "\n".join(
        [f"{r[0]}: {r[1]}" for r in reversed(history)]
    )
    # -------- LOAD MASTERY --------
    top_ids = [c.id for c in top_concepts]

    mres = await db.execute(
        select(Mastery).where(
            Mastery.user_id == current_user_id,
            Mastery.concept_id.in_(top_ids)
        )
    )

    mrows = mres.scalars().all()

    avg_mastery = (
        sum(m.mastery_prob for m in mrows)/len(mrows)
        if mrows else 0.4
    )
    # 2) LLM call
    resp = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {
                
                 "role":"system",
                 "content":
            f"""You are a patient, expert tutor helping with homework.

            Student estimated mastery level: {avg_mastery}

            If mastery < 0.5:
            - give smaller steps
            - more hints
            - more examples

            If mastery > 0.7:
            - challenge the student
            - ask deeper reasoning questions

            This homework likely reflects exam-style questions.

            Your goal is to prepare the student for exams while helping them understand deeply.

            CORE RULES:
            - You MUST explicitly reference the class concept you are using.

            Before solving, first identify the method or concept required for the problem.

            Structure your reasoning as:

            Step 0: Identify the concept or method needed to solve the problem.
            Step 1: Explain why that concept applies.
            Step 2: Break the solution into logical steps.
            Step 3: Apply formulas, reasoning, or algorithms step-by-step.

            When applying a concept, begin with:

            Concept used: <concept_name>

            Then connect the reasoning to:
    
            1. Definition — what the concept means
            2. When to use — why it applies to this problem
            3. Common pitfall — a mistake students often make

            Example structure:

            Concept used: Law of Total Expectation

            Definition:
            The expected value of a variable computed by conditioning on another variable.

            When to use:
            When a random variable depends on several possible cases.

            Common pitfall:
            Students forget to weight the conditional expectations by their probabilities.

            Then continue guiding the student step-by-step.
            - Help student think step-by-step
            - Ask guiding questions before giving conclusions
            - Do NOT immediately give final answers
            - If math: show reasoning
            - If conceptual: use examples
            - Focus on understanding, not speed
            - Emphasize methods professors test
            - Connect reasoning to definitions and when-to-use rules
            - Warn about common pitfalls
            
            MATH FORMATTING (VERY IMPORTANT):
            - ALWAYS format math using LaTeX
            - Inline math must use $...$
            - Equations must use $$...$$
            - Never write raw LaTeX without $ delimiters
            
            TIMELINES (VERY IMPORTANT):
            When drawing a timeline, ALWAYS render it as a code block.

            Example:
            INTERACTION MODES:
    
            HINT MODE:
            If the student says "hint":
            → Give a SMALL hint only
            → Do NOT solve

            STEP MODE:
            If the student says "next step":
            → Continue from previous reasoning
            → Reveal only 1–2 steps

            DEFAULT:
            → Teach in small steps
            → End with a guiding question
            """
            },
            {
                "role": "user",
                "content":
f"""
Recent chat history:
Use recent chat history to adapt your help.
If student struggled before, slow down.
If they improved, increase challenge.
{history_text}

Student question:
{body.question}

Class concepts:
{context}
"""
            }
        ],
        temperature=0.4
    )

    answer = resp.choices[0].message.content
    # -------- SAVE ASSISTANT MESSAGE --------
    db.add(ChatMemory(
        user_id=current_user_id,
        class_id=class_uuid,
        role="assistant",
        content=answer
    ))

    await db.commit()

    conf = grounding_confidence(answer, top_concepts)
    if conf < 0.2:
        print("⚠️ Tutor response weakly grounded")
    return {
        "help": answer,
        "grounding_confidence": conf
    }


# ----------------------
# FILE UPLOAD
# ----------------------
@router.post("/upload-help")
async def homework_upload_help(
    class_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):

    # ✅ Validate class_id
    if not class_id:
        raise HTTPException(400, "class_id required")

    try:
        UUID(class_id)
    except:
        raise HTTPException(400, "Invalid class_id")

    content = await file.read()
    text = await extract_text(file.filename, content)

    

    questions = split_homework_questions(text)

    
    return {
        "questions": questions,
        "count": len(questions)
    }

@router.delete("/chat-history/{class_id}")
async def clear_chat(
    class_id: str,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    await db.execute(
        ChatMemory.__table__.delete().where(
            ChatMemory.user_id == current_user_id,
            ChatMemory.class_id == UUID(class_id)
        )
    )

    await db.commit()

    return {"status": "cleared"}
