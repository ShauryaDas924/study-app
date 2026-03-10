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
        k=3
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

            # try to load mastery row
            m = await db.get(
                Mastery,
                {"user_id": current_user_id, "concept_id": c.id}
            )
        
            # create if it doesn't exist
            if not m:
                m = Mastery(
                    user_id=current_user_id,
                    concept_id=c.id,
                    mastery_prob=0.35
                )
                db.add(m)
                await db.flush()

            # update mastery using Bayesian model
            new_mastery = update_mastery_value(
                mastery=m.mastery_prob,
                correct=False,
                difficulty=3,
                confidence=2,
                time_spent=30
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

            TEACHING FLOW:

            Think like a great professor helping a student understand.

            Your reasoning should be structured internally,
            but your explanation should feel natural and conversational.

            When solving a problem, generally follow this flow:

            1. Identify the key concept or idea involved.
            2. Explain the intuition behind the idea in simple language.
            3. Show the structure of the problem (timeline, cases, diagram, etc.).
            4. Introduce the formula or rule being used.
            5. Apply the reasoning step-by-step.

            IMPORTANT:

            Do NOT always label steps like "Step 1", "Step 2".

            Only use explicit steps when it genuinely helps clarity.

            Prefer a natural explanation style:
            idea → structure → formula → reasoning.

            CONCEPT USAGE:

            When a concept is relevant, briefly mention it and connect it to the reasoning.

            You may explain:
            • what the concept means
            • why it applies here
            • a common mistake students make

            Do not force a rigid "Definition / When to use / Pitfall" structure.
            Explain concepts naturally as part of the reasoning.

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
           
            CLARITY RULES (VERY IMPORTANT):

            Explain ideas in the simplest possible way.
            Never introduce more than ONE formula at a time.
            
            - Prefer short sentences.
            - Avoid long paragraphs.
            - Introduce only ONE idea at a time.
            - Do NOT show many formulas at once.

            For math problems:
            1. First show the structure of the problem.
            2. Use a timeline or list of payments when possible.
            3. Then introduce the formula.
            4. Then substitute numbers.

            Whenever possible, explain the intuition behind the formula.

            If the explanation becomes long, pause and ask the student a short guiding question.
            
            INTUITION FIRST RULE:

            Always explain the idea behind the method BEFORE introducing formulas.

            Students understand formulas much better when they first understand the intuition.
            
            MISCONCEPTION HANDLING:

            If a misconception is detected, explain:

            1. Why the misconception is tempting
            2. Why it is incorrect
            3. What the correct reasoning is
            

            Use bullet points when listing payments or reasoning.
            
            EXPLANATION LIMIT:

            Avoid explanations longer than 6–8 lines before pausing.

            Teach incrementally instead of giving everything at once.
            
            MATH FORMATTING (VERY IMPORTANT):
            - ALWAYS format math using LaTeX
            - Inline math must use $...$
            - Equations must use $$...$$
            - Never write raw LaTeX without $ delimiters
            
            MATH VERIFICATION RULE:

            Always verify numeric calculations before presenting a final answer.
            Double check formulas, interest rates, and number of periods.
            If a calculation involves multiple steps, mentally recompute the result once before responding.
            
            TIMELINES (VERY IMPORTANT):

            If the problem involves payments, interest, or time periods,
            ALWAYS draw a timeline BEFORE using formulas.
            Example format:
            
            t=0      t=1      t=2      t=3
            |––––|––––|––––|
            Today     …      …    Payment

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
            
            SOCRATIC TUTORING:

            Whenever possible, guide the student through the reasoning using short questions.

            Rather than immediately giving the full solution, encourage the student to think through key steps of the problem.

            Ask natural reasoning questions such as:

            • "What concept might apply here?"
            • "What would the timeline look like?"
            • "How many payments are there?"
            • "What is the interest rate per period?"

            After the student responds, acknowledge their reasoning and guide them toward the next step.

            If the student seems stuck, confused, or explicitly asks for the answer, gradually reveal more of the solution.
            Prefer questions that test understanding of the next logical step
            rather than asking abstract questions.
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
Possible misconception detected:
{mis if mis.lower().strip() != "none" else "No clear misconception detected"}
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
