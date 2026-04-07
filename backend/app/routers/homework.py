from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import re
import json
import base64
from sqlalchemy.dialects.postgresql import insert
from app.models import Concept, ChatMemory, StudentPitfall, Mastery
from app.db import get_db
from app.services.llm import client, kimi_client, top_k_concepts, grounding_confidence
from app.services.file_extraction import extract_text
from app.services.auth import get_current_user_id
from app.services.mastery import update_mastery_value

router = APIRouter(prefix="/homework", tags=["homework"])


class HWIn(BaseModel):
    class_id: str
    question: str


def clean_extracted_text(text: str) -> str:
    """
    Clean PDF text WITHOUT destroying line structure.
    This is the key fix.
    """
    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")

    cleaned_lines = []
    for raw_line in text.split("\n"):
        line = raw_line.strip()

        if not line:
            cleaned_lines.append("")
            continue

        # Fix missing spaces between numbers and letters
        line = re.sub(r'(\d)([A-Za-z])', r'\1 \2', line)
        line = re.sub(r'([A-Za-z])(\d)', r'\1 \2', line)

        # Fix punctuation spacing
        line = re.sub(r',([A-Za-z])', r', \1', line)
        line = re.sub(r'\.([A-Za-z])', r'. \1', line)
        line = re.sub(r':([A-Za-z])', r': \1', line)
        line = re.sub(r';([A-Za-z])', r'; \1', line)

        # Collapse repeated spaces INSIDE the line only
        line = re.sub(r'[ \t]+', ' ', line)

        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)

    # Remove obvious page labels
    text = re.sub(r'(?im)^\s*Page\s+\d+\s*$', '', text)

    # Collapse too many blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def split_homework_questions(text: str) -> list[str]:
    """
    Split homework safely.
    Primary rule:
    - split only at start-of-line question numbers like '1.' '2.' etc.

    Fallback:
    - if the PDF came in as one huge paragraph, inject newlines before likely
      question starts, then split again.
    """
    if not text or not text.strip():
        return []

    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()

    # Remove header junk before first numbered question
    first_q = re.search(r'(?m)^\s*1\.\s+', text)
    if first_q:
        text = text[first_q.start():]

    # Primary split: start-of-line numbered questions only
    parts = re.split(r'(?m)^\s*(\d+)\.\s+', text)

    questions = []
    if len(parts) >= 3:
        # Format: ["", "1", "question...", "2", "question...", ...]
        for i in range(1, len(parts), 2):
            if i + 1 >= len(parts):
                break

            q_num = parts[i].strip()
            q_text = parts[i + 1].strip()

            # Remove trailing page markers inside block
            q_text = re.sub(r'(?im)\bPage\s+\d+\b', '', q_text)
            q_text = re.sub(r'\n{3,}', '\n\n', q_text).strip()

            if q_text:
                questions.append(f"{q_num}. {q_text}")

    # Fallback if nothing found or only one giant block found
    if len(questions) <= 1:
        block = re.sub(r'\s+', ' ', text).strip()

        # Inject probable question boundaries only for small numbers at sentence boundaries.
        # This avoids splitting on math like (3n + 1).
        block = re.sub(r'(?<!\S)(\d{1,2})\.\s+', r'\n\1. ', block)

        parts = re.split(r'(?m)^\s*(\d+)\.\s+', block)

        fallback_questions = []
        if len(parts) >= 3:
            for i in range(1, len(parts), 2):
                if i + 1 >= len(parts):
                    break

                q_num = parts[i].strip()
                q_text = parts[i + 1].strip()

                q_text = re.sub(r'\bPage\s+\d+\b', '', q_text).strip()
                if q_text:
                    fallback_questions.append(f"{q_num}. {q_text}")

        if fallback_questions:
            questions = fallback_questions

    return questions


# ----------------------
# TEXT QUESTION
# ----------------------
@router.post("/help")
async def homework_help(
    body: HWIn,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    print("\n📨 Incoming Question:", body.question)
    # ✅ Validate class_id
    if not body.class_id:
        raise HTTPException(400, "class_id required")

    try:
        class_uuid = UUID(body.class_id)
    except:
        raise HTTPException(400, "Invalid class_id")

    # ----------------------
    # ANALYZE WORK MODE
    # ----------------------
    if body.question and "analyze my work" in body.question.lower():
        print("\n🧠 ANALYZE MODE TRIGGERED")
        db.add(ChatMemory(
            user_id=current_user_id,
            class_id=class_uuid,
            role="user",
            content=body.question
        ))
        # Load recent chat history
        res = await db.execute(
            select(ChatMemory.role, ChatMemory.content)
            .where(
                ChatMemory.user_id == current_user_id,
                ChatMemory.class_id == class_uuid
            )
            .order_by(ChatMemory.created_at.desc())
            .limit(8)
        )

        history = res.fetchall()

        history_text = "\n".join(
            [f"{r[0]}: {r[1]}" for r in reversed(history)]
        )
        print("\n📜 Chat History Used for Analysis:")
        print(history_text)

        resp = kimi_client.chat.completions.create(
            model="kimi-k2.5",
            messages=[
                {
                    "role": "system",
                    "content": """
    Analyze the student's reasoning in the conversation.

    Return JSON only:

    {
    "strengths":[ "..."],
    "pitfalls":[
    {
        "tag":"timeline_construction",
        "explanation":"student struggles placing values on timeline"
    }
    ]
    }

    Pitfall tags must be short snake_case skills.

    Prefer FM-relevant tags when applicable, such as:
timeline_construction
focal_date_selection
annuity_due_vs_immediate
rate_conversion
period_matching
equation_of_value_setup
loan_balance_timing
bond_valuation_structure
yield_reasoning
deferred_cash_flow_setup
replacement_of_payments
cash_flow_classification
    """
                },
                {
                    "role": "user",
                    "content": history_text
                }
            ],
        )

        import json

        raw = resp.choices[0].message.content
        raw = raw.replace("```json", "").replace("```", "").strip()
        print("\n🤖 RAW LLM RESPONSE:")
        print(raw)
        try:
            data = json.loads(raw)
        except Exception as e:
            print("❌ JSON PARSE ERROR:", e)
            print("RAW:", raw)
            return {"help": "Error parsing analysis response"}

        strengths = data.get("strengths", [])
        pitfalls = data.get("pitfalls", [])
        print("\n🧠 Generating NATURAL explanation...")

        natural_resp = kimi_client.chat.completions.create(
            model="kimi-k2.5",
            messages=[
                {
                    "role": "system",
                    "content": """
You are a natural, conversational tutor.

You are reviewing a student's reasoning.

Explain:
• what they did well
• where they went wrong
• why the mistake happened

DO NOT sound like a report.
DO NOT mention JSON or tags.
DO NOT say "pitfall tag".

Speak like a real tutor helping a student improve.

Be specific to THEIR reasoning.
Be clear and slightly concise.
"""
                },
                {
                    "role": "user",
                    "content": f"""
Student conversation:
{history_text}

Structured analysis:
Strengths: {strengths}
Pitfalls: {pitfalls}

Explain this naturally to the student.
"""
                }
            ],
        )

        natural_answer = natural_resp.choices[0].message.content

        print("\n🗣 NATURAL RESPONSE:")
        print(natural_answer)
        print("\n💾 Saving Pitfalls:")
        for p in pitfalls:
            stmt = insert(StudentPitfall).values(
                user_id=current_user_id,
                class_id=class_uuid,
                pitfall=p["tag"],
                explanation=p.get("explanation")
            ).on_conflict_do_update(
                index_elements=["user_id", "class_id", "pitfall"],
                set_={
                    "explanation": p.get("explanation")
                }
            )

            await db.execute(stmt)
            print("Saving:", p)

        # ✅ THEN QUERY
        res = await db.execute(
            select(StudentPitfall).where(
                StudentPitfall.user_id == current_user_id,
                StudentPitfall.class_id == class_uuid
            )
        )

        rows = res.scalars().all()
        print("📊 Total pitfalls now:", len(rows))
        print("✅ Pitfalls committed to DB")

        answer = natural_answer

        db.add(ChatMemory(
            user_id=current_user_id,
            class_id=class_uuid,
            role="assistant",
            content=answer
        ))

        await db.commit()

        return {"help": answer}

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

    # Retrieve concepts with scores
    scored_concepts = await top_k_concepts(
        body.question,
        concepts,
        k=6
    )

    # Separate concepts from scores
    top_concepts = [c for score, c in scored_concepts]
    print("\nTOTAL CONCEPTS IN CLASS:", len(concepts))

    missing = sum(1 for c in concepts if c.embedding is None)
    print("CONCEPTS WITH MISSING EMBEDDINGS:", missing)
    print("\n===== RAG CONCEPT RETRIEVAL =====")

    for i, (score, c) in enumerate(scored_concepts, 1):
        print(f"\n[Concept {i}]")
        print(f"Score: {round(score,4)}")
        print(f"Name: {c.name}")

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
            {
            "role": "system",
            "content": """
You are detecting likely student misconceptions in an SOA Exam FM problem.

Return ONLY one short snake_case label or 'none'.

Prefer one of these if relevant:
timeline_construction
focal_date_confusion
annuity_due_vs_immediate
rate_period_mismatch
discount_vs_interest_confusion
present_vs_accumulated_value_confusion
deferred_annuity_confusion
loan_balance_timing_error
bond_coupon_redemption_confusion
equation_of_value_setup_error
replacement_of_payments_timing_error
yield_interpretation_error
duration_immunization_confusion
general_algebra_error

Return the single most likely misconception shown by the student.
"""
        },
        {
            "role": "user",
            "content": body.question
        }
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
        sum(m.mastery_prob for m in mrows) / len(mrows)
        if mrows else 0.4
    )

    # -------- DETECT CONFUSION STATE --------
    question_lower = body.question.lower()

    confused = any(
        phrase in question_lower
        for phrase in [
            "confused", "lost", "dont get", "don't get",
            "stuck", "no idea", "what do i do", "i'm lost",
            "which formula", "what formula", "when do i use",
            "annuity due or immediate", "due or immediate",
            "what timeline", "how do i set it up",
            "what rate do i use", "which rate", "how do i convert",
            "where do i value it", "focal date", "valuation date"
        ]
    )

    strong_signals = any(
        phrase in question_lower
        for phrase in [
            "check my setup",
            "is my timeline right",
            "is my equation right",
            "i think this is",
            "would this be an annuity due",
            "my focal date is",
            "can i use",
            "verify this"
        ]
    )

    if confused:
        student_state = "confused"
    elif avg_mastery >= 0.75 or strong_signals:
        student_state = "strong"
    else:
        student_state = "normal"
    print("🧠 Student state:", student_state)
    
    fm_keywords = [
    "annuity", "present value", "accumulated value", "future value",
    "discount", "effective rate", "nominal rate", "force of interest",
    "loan", "amortization", "sinking fund", "bond", "yield",
    "duration", "immunization", "spot rate", "forward rate",
    "coupon", "redemption", "equation of value"
    ]

    is_fm_problem = any(k in question_lower for k in fm_keywords)
    system_prompt = """
You are an elite beginner-first SOA Exam FM tutor.

Your job is to teach FM to a student who may be extremely weak at setup, timelines, recognition, and translating words into math.

Assume the student may NOT yet know:
- how to identify the problem type
- how to build a timeline
- how to choose a focal date
- how to match the rate period to the payment period
- how to tell what cash flows exist
- how to tell whether a formula fits

Your job is not to sound smart.
Your job is to make FM finally feel understandable.

Student state: __STUDENT_STATE__
Student mastery: __AVG_MASTERY__

------------------------------------------------
CORE MISSION
------------------------------------------------

Teach the student to think in this exact order:

1. What is happening in the story?
2. What cash flows exist?
3. When do they happen?
4. What date do we care about?
5. Do the interest period and payment period match?
6. What equation represents this?
7. Only then solve.

The student must learn this pipeline:

words -> story -> cash flows -> timeline -> focal date -> equation -> solve

Do not skip steps.

------------------------------------------------
ABSOLUTE BEGINNER PRIORITY
------------------------------------------------

Always prioritize these in order:

1. plain-English story
2. identifying cash flows
3. timeline
4. focal date
5. period matching
6. setup
7. calculation

If the student does not clearly understand the story or timeline, do NOT move to formulas.

------------------------------------------------
BEGINNER-FIRST RULE
------------------------------------------------

Assume confusion unless the student clearly demonstrates structure.

If the student asks a raw FM problem, seems unsure, asks about the timeline, asks which formula to use, or has not shown setup, teach as if they are a beginner.

For beginners:
- explain in plain English first
- use short sentences
- one idea at a time
- one representation at a time
- do not jump to shorthand notation
- do not give multiple methods
- do not compress reasoning

If a response would impress an instructor but confuse a weak student, it is a bad response.

------------------------------------------------
WHAT TO DO FIRST ON EVERY FM PROBLEM
------------------------------------------------

Before using any formula, always do these things:

A. Restate the story in simple words
B. Identify the cash flows
C. Show when they happen
D. Identify the focal date
E. Check whether the rate period matches the payment period
F. Only then write a setup equation

Never jump straight into formula substitution.

------------------------------------------------
TIMELINE TEACHING RULE
------------------------------------------------

For FM problems involving money at different times, you MUST show a timeline before meaningful computation.

Use a plain-text fenced code block.

Example:

```text
Time:        0      1      2      3
             |------|------|------|
Cash flows:  1000   -      -      -
Value date:                      *

Label clearly:
    •    what happens at time 0
    •    when the first payment occurs
    •    when the last payment occurs
    •    where the value date is
    •    whether payments are beginning or end of period
    •    any rate changes

If the student is weak at timelines, slow down and explain each mark on the timeline.

⸻

PLAIN-ENGLISH STORY RULE

Before formal math, explain the problem as a money story.

Examples of good beginner phrasing:
    •    “Money starts here.”
    •    “This payment happens at the end of each year.”
    •    “All of these amounts must be compared at the same date.”
    •    “This deposit grows forward to year 10.”
    •    “This payment is discounted back to time 0.”

Examples of bad beginner phrasing:
    •    “This is a varying annuity-immediate.”
    •    “Use the arithmetic accumulation formula.”
    •    “Apply the standard identity.”

Formal terms may be introduced later, but only after the student understands the story.

⸻

NOTATION DELAY RULE

Do NOT introduce compact actuarial notation too early.

Unless the student is clearly strong or explicitly asks for formal notation:
    •    do not use increasing/decreasing annuity shortcuts
    •    do not use advanced annuity symbols prematurely
    •    do not use multiple equivalent formulas
    •    do not use notation just because it is shorter

For weak students, prefer:
plain English -> timeline -> explicit cash-flow sum -> formula name later

Explicit sums are better than compressed formulas when the student is confused.

⸻

ONE-REPRESENTATION RULE

At each teaching step, use only one main representation:
    •    plain English
    •    timeline
    •    explicit cash-flow list
    •    equation
    •    compact notation

Do NOT switch across multiple representations in one response unless the student is stable.

For beginners, prefer:
plain English -> timeline -> explicit sum

⸻

FOCAL DATE RULE

Always identify the focal date clearly.

Say it in plain English, like:
    •    “We want the value at time 0.”
    •    “We want the accumulated value at the end of year 10.”
    •    “So every cash flow must be moved to year 10.”

If the student seems lost, repeat the focal date before writing the equation.

⸻

RATE MATCHING RULE

Always check whether the interest period matches the cash-flow period.

Explain this plainly.

Examples:
    •    “The payments are yearly, and the rate is annual effective, so they already match.”
    •    “The payments are monthly, but the rate is annual, so we need a monthly rate first.”

Never silently use a mismatched rate.

⸻

PROBLEM RECOGNITION RULE

When useful, briefly identify the problem type, but only after explaining the story.

Possible FM types include:
    •    single payment
    •    present value / future value
    •    annuity-immediate
    •    annuity-due
    •    deferred annuity
    •    amortization
    •    sinking fund
    •    bond
    •    yield / equation of value
    •    replacement of payments
    •    varying cash flow
    •    spot / forward rate
    •    duration / immunization

But for weak students, do NOT lead with category names alone.
Lead with what is happening.

⸻

SOCRATIC RULE

For weak students, do not ask broad open-ended questions.

Bad:
    •    “What do you think?”
    •    “Can you solve this?”
    •    “Any ideas?”

Good:
    •    “At what time does the first payment happen?”
    •    “Are we valuing everything at time 0 or time 10?”
    •    “Does this cash flow move forward or backward?”
    •    “How many years does the first deposit grow?”
    •    “Is this payment at the beginning or end of the year?”

Ask only one focused question at a time.

⸻

CONFUSED-STUDENT SAFETY RULE

If student_state = confused, or the student shows no setup skill yet:

You MUST teach at the lowest useful level.

In confused mode, do NOT:
    •    introduce advanced notation
    •    give multiple methods
    •    jump to shortcut formulas
    •    compress several reasoning steps together
    •    end by saying “now calculate it” if the student still does not understand the setup

Instead, always do this:
    1.    restate the story
    2.    identify the cash flows
    3.    build the timeline slowly
    4.    identify the focal date
    5.    write only the next setup step
    6.    explain why that step makes sense
    7.    ask one tiny check question

The goal is for the next step to feel obvious.

⸻

HARD STOP POLICY

Unless the student explicitly asks for the full solution, do NOT fully solve the entire problem.

Default behavior:
    1.    explain the story
    2.    show the timeline
    3.    identify the focal date
    4.    do only the first useful setup step
    5.    stop
    6.    ask one small check question

If the student explicitly says:
    •    solve it
    •    give the full solution
    •    finish it
    •    just do it

then you may give the full solution.

⸻

COMMON BEGINNER FM MISTAKES TO WATCH FOR

Actively watch for and correct these:
    •    not knowing what the cash flows are
    •    not knowing when each cash flow happens
    •    drawing no timeline
    •    wrong first payment timing
    •    beginning vs end confusion
    •    wrong focal date
    •    present value vs accumulated value confusion
    •    rate period mismatch
    •    using a formula before understanding the setup
    •    moving values to inconsistent dates
    •    answering the wrong question

If one of these appears, name it simply and fix it simply.

⸻

TEACHING STYLE

Your tone should be:
    •    calm
    •    clear
    •    direct
    •    patient
    •    intelligent
    •    never robotic
    •    never showy
    •    never lecture-like

Use short paragraphs.
Use simple words.
Avoid filler.

Do not praise excessively.
Do not sound like a textbook.
Do not sound like a report.

⸻

OUTPUT FORMAT

Use clean Markdown.

Use these headings when helpful:
    •    Story
    •    Cash Flows
    •    Timeline
    •    Focal Date
    •    Rate Check
    •    First Step
    •    Why
    •    Your Turn

For timelines, use fenced plain-text code blocks only.

For formulas:
    •    inline math: $…$
    •    display math: $$…$$

Do not use tables.

⸻

DEFAULT RESPONSE BLUEPRINT

For a weak or beginner student, use this structure:

Story
    •    explain what is happening in plain English

Cash Flows
    •    identify what money appears and where

Timeline
    •    draw the timeline simply

Focal Date
    •    say what date we care about

Rate Check
    •    say whether the rate matches the payment spacing

First Step
    •    do only the first setup step

Why
    •    explain why that step is correct in simple language

Your Turn
    •    ask one very small, concrete question

⸻

FINAL GOAL

The student should leave understanding:
    •    what is happening
    •    what the timeline means
    •    what date matters
    •    what equation should be written
    •    why that setup is correct

Do not optimize for elegance.
Optimize for beginner clarity, transfer, and confidence in setup.
"""


    system_prompt = system_prompt.replace("__STUDENT_STATE__", str(student_state))
    system_prompt = system_prompt.replace("__AVG_MASTERY__", str(avg_mastery))

    # 2) LLM call
    resp = kimi_client.chat.completions.create(
        model="kimi-k2.5",
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": f"""
STUDENT QUESTION
{body.question}

RECENT CHAT HISTORY
{history_text}

DETECTED MISCONCEPTION
{mis if mis.lower().strip() != "none" else "No clear misconception detected"}

RELEVANT CLASS CONCEPTS
{context}

INSTRUCTION
Teach this like an elite beginner-first FM tutor.

Use the student's likely level and confusion state.
Ground your teaching in the provided concepts when relevant.

If the student has not shown setup skill yet:
- explain the story first
- identify cash flows first
- draw the timeline slowly
- state the focal date clearly
- avoid advanced notation
- use only one representation at a time
- do only one small step
- ask one tiny concrete question

Prioritize beginner clarity over compactness.
"""
        }
    ],
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
    text = clean_extracted_text(text)

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


# ----------------------
# REVIEW STUDENT WORK (VISION)
# ----------------------
@router.post("/review-work")
async def review_student_work(
    class_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):

    if not class_id:
        raise HTTPException(400, "class_id required")

    class_uuid = UUID(class_id)

    # -------- LOAD CLASS CONCEPTS --------
    res = await db.execute(
        select(Concept).where(
            Concept.class_id == class_uuid,
            Concept.user_id == current_user_id
        )
    )

    concepts = res.scalars().all()

    # -------- RETRIEVE RELEVANT CONCEPTS --------
    query = "student handwritten math solution"

    scored_concepts = await top_k_concepts(
        query,
        concepts,
        k=6
    )

    top_concepts = [c for score, c in scored_concepts]

    print("\n===== REVIEW CONCEPT RETRIEVAL =====")

    for i, (score, c) in enumerate(scored_concepts, 1):
        print(f"\n[Concept {i}]")
        print(f"Score: {round(score,4)}")
        print(f"Name: {c.name}")

    content = await file.read()

    import base64
    img_b64 = base64.b64encode(content).decode()

    # -------- BUILD CONCEPT CONTEXT --------
    context = "\n\n".join([
        f"""
    CONCEPT KNOWLEDGE

    Name: {c.name}

    Definition:
    {c.definition or c.description}

    When to use:
    {c.when_to_use or "Use this concept when solving relevant problems."}
    
    Common pitfall:
    {c.pitfalls or "Students often misuse this concept."}
    """
        for c in top_concepts
    ])[:3000]

    resp = kimi_client.chat.completions.create(
        model="kimi-k2.5",
        messages=[
            {
                "role": "system",
                "content": f"""
            You are an expert actuarial science and mathematics tutor reviewing a student's solution.

            Relevant class concepts:

            {context}

            When analyzing the student's work:
            • Identify which concept the student is trying to apply
            • If a mistake occurs, explain which concept is misused
            • Reference concept names when appropriate

            The student uploaded an image showing their handwritten work on a problem.

            Your job is NOT to immediately solve the problem.

            Your job is to carefully evaluate the student's reasoning so far and guide them toward the correct solution.

            The student uploaded an image showing their handwritten work on a problem.

            Your job is NOT to immediately solve the problem.
    
            Your job is to carefully evaluate the student's reasoning so far and guide them toward the correct solution.

------------------------------------------------

YOUR OBJECTIVES

1. Identify what the student is doing correctly
2. Detect mistakes in reasoning, formulas, or structure
3. Determine whether the student's overall approach is valid
4. Explain why any mistakes occur
5. Guide the student toward the next correct step

Your goal is to help the student learn from their current work.

------------------------------------------------

ANALYSIS METHOD

Carefully examine the student's work step-by-step.

Look for:

• incorrect formulas  
• incorrect substitutions  
• incorrect interest rate conversions  
• missing timelines or structure  
• algebra mistakes  
• incorrect probability reasoning  
• misinterpreting the problem  

Focus on the reasoning behind each step.

------------------------------------------------

IMPORTANT RULES

• Do NOT solve the entire problem immediately
• Do NOT jump to the final answer
• Focus on evaluating the student's current steps
• Guide the student toward the next correct step
• Encourage correct reasoning when it appears

If the student is on the right path, clearly say so.

------------------------------------------------

STRUCTURE YOUR RESPONSE USING THESE SECTIONS

## What You Did Correctly

Identify steps the student handled properly.

Explain why those steps are correct.

------------------------------------------------

## Issues Detected

Identify mistakes or potential mistakes.

For each issue explain:

• what the student did  
• why it may be incorrect  
• what concept is being misapplied  

------------------------------------------------

## Is the Approach Valid?

Explain whether the student's general strategy is correct.

Example:

• Correct method but calculation mistake  
• Correct structure but wrong formula  
• Incorrect method entirely  

------------------------------------------------

## Next Step

Tell the student the next logical step they should take.

Give a hint or guidance rather than solving the entire problem.

Example:

• what to compute next  
• what formula to use  
• what structure to build (timeline, cases, etc.)

------------------------------------------------

CLARITY RULES

• Use short explanations
• Use bullet points where helpful
• Avoid long paragraphs
• Focus on teaching

------------------------------------------------

MATH FORMATTING

Use LaTeX for formulas.

Inline math: $...$

Equations: $$...$$
"""
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Here is my work so far on the problem. Please review it."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{img_b64}"
                        }
                    }
                ]
            }
        ],
    )

    return {
        "review": resp.choices[0].message.content
    }


# ----------------------
# GET STORED PITFALLS
# ----------------------
@router.get("/pitfalls/{class_id}")
async def get_pitfalls(
    class_id: str,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):

    res = await db.execute(
        select(StudentPitfall).where(
            StudentPitfall.user_id == current_user_id,
            StudentPitfall.class_id == UUID(class_id)
        )
    )

    rows = res.scalars().all()

    return [
        {
            "pitfall": r.pitfall,
            "explanation": r.explanation
        }
        for r in rows
    ]


# ----------------------
# PRACTICE FROM PITFALL
# ----------------------
@router.post("/practice-pitfall")
async def practice_pitfall(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    pitfall = body.get("pitfall")
    class_id = body.get("class_id")

    if not pitfall or not class_id:
        raise HTTPException(400, "pitfall and class_id required")

    class_uuid = UUID(class_id)

    print("\n🎯 PRACTICE MODE:", pitfall)

    # -------- LOAD CONCEPTS --------
    res = await db.execute(
        select(Concept).where(
            Concept.class_id == class_uuid,
            Concept.user_id == current_user_id
        )
    )
    concepts = res.scalars().all()

    # -------- FILTER RELEVANT CONCEPTS --------
    relevant = [
        c for c in concepts
        if pitfall in (c.pitfalls or "").lower()
    ]

    if not relevant:
        relevant = concepts[:3]

    concept_context = "\n\n".join([
        f"""
Concept: {c.name}
Definition: {c.definition or c.description}
When to use: {c.when_to_use}
Common mistake: {c.pitfalls}
"""
        for c in relevant
    ])[:3000]

    print("\n🧠 USING CONCEPTS:\n", concept_context)

    # -------- GENERATE QUESTIONS --------
    resp = kimi_client.chat.completions.create(
        model="kimi-k2.5",
        messages=[
            {
                "role": "system",
                "content": f"""
You are an expert tutor generating targeted practice problems.

The student has a specific weakness:

{pitfall}

Your goal:
Generate 3 high-quality practice questions that directly train this weakness.

MPORTANT:
Every question MUST specifically target this pitfall.
Do NOT include unrelated skills.

You are NOT limited to any subject.
Use the provided concepts as the source of truth.

---------------------

HOW TO DESIGN QUESTIONS

Each question must:
• require applying a concept (not memorization)
• force the student to confront the weakness
• reflect realistic exam or homework problems
• involve reasoning, not just recall

---------------------

ADAPT TO THE PITFALL

- If the pitfall is about structure (e.g., timelines, setup):
  → require building structure

- If the pitfall is about concept confusion:
  → require choosing the correct method

- If the pitfall is about calculation mistakes:
  → require careful multi-step reasoning

---------------------

RULES

• Do NOT solve the questions
• Do NOT give hints
• Do NOT explain answers
• Keep wording clear and concise
• Avoid trivial or overly simple questions

---------------------

FORMAT

Question 1:
...

Question 2:
...

Question 3:
...
"""
            },
            {
                "role": "user",
                "content": f"""
Relevant concepts:
{concept_context}
"""
            }
        ]
    )

    questions = resp.choices[0].message.content

    print("\n🧪 GENERATED QUESTIONS:\n", questions)

    return {"questions": questions}


@router.delete("/pitfalls/{class_id}")
async def clear_pitfalls(
    class_id: str,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    if not class_id:
        raise HTTPException(400, "class_id required")

    class_uuid = UUID(class_id)

    await db.execute(
        StudentPitfall.__table__.delete().where(
            StudentPitfall.user_id == current_user_id,
            StudentPitfall.class_id == class_uuid
        )
    )

    await db.commit()

    return {"status": "pitfalls cleared"}


@router.get("/chat-history/{class_id}")
async def get_chat_history(
    class_id: str,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    res = await db.execute(
        select(ChatMemory.role, ChatMemory.content)
        .where(
            ChatMemory.user_id == current_user_id,
            ChatMemory.class_id == UUID(class_id)
        )
        .order_by(ChatMemory.created_at.asc())
    )

    rows = res.fetchall()

    return [
        {"role": r[0], "content": r[1]}
        for r in rows
    ]
