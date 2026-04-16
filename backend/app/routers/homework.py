from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import re
import json
import time
import base64
from sqlalchemy.dialects.postgresql import insert
from app.models import Concept, ChatMemory, StudentPitfall, Mastery
from app.db import get_db
from app.services.llm import client, kimi_client, top_k_concepts
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
    t0 = time.perf_counter()
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
        question_lower = body.question.lower()
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

        raw_history_text = "\n".join(
            [f"{r[0]}: {r[1]}" for r in reversed(history)]
        )

        use_history = (
            len(body.question) < 500
            or "continue" in question_lower
            or "still confused" in question_lower
            or "as i said" in question_lower
            or "you said" in question_lower
        )

        history_text = raw_history_text if use_history else ""
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
    question_lower = body.question.lower()
    # 1) Get concepts
    t_concepts = time.perf_counter()
    res = await db.execute(
        select(Concept).where(
            Concept.class_id == class_uuid,
            Concept.user_id == current_user_id
        )
    )
    print(f"⏱ concept query: {time.perf_counter() - t_concepts:.2f}s")

    concepts = res.scalars().all()

    # Retrieve concepts with scores
    t_topk = time.perf_counter()
    scored_concepts = await top_k_concepts(
        body.question,
        concepts,
        k=4
    )
    print(f"⏱ top_k_concepts: {time.perf_counter() - t_topk:.2f}s")

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
    ])[:2200]

    
    # -------- MISCONCEPTION DETECTION (ONLY WHEN NEEDED) --------
    mis = "none"

    should_run_mischeck = any(
        phrase in question_lower
        for phrase in [
            "check my setup",
            "is my timeline right",
            "is my equation right",
            "i think this is",
            "would this be",
            "my focal date is",
            "can i use",
            "verify this",
            "is this right",
            "am i wrong",
            "did i do this right",
            "where did i go wrong"
        ]
    )

    if should_run_mischeck:
        t_mis = time.perf_counter()
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

        mis = mis_resp.choices[0].message.content.strip()
        print(f"⏱ misconception call: {time.perf_counter() - t_mis:.2f}s")
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
    t_history = time.perf_counter()
    mem_res = await db.execute(
        select(ChatMemory.role, ChatMemory.content)
        .where(
            ChatMemory.user_id == current_user_id,
            ChatMemory.class_id == class_uuid
        )
        .order_by(ChatMemory.created_at.desc())
        .limit(6)
    )
    print(f"⏱ history query: {time.perf_counter() - t_history:.2f}s")

    history = mem_res.fetchall()

    raw_history_text = "\n".join(
        [f"{r[0]}: {r[1]}" for r in reversed(history)]
    )

    use_history = (
        len(body.question) < 500
        or "continue" in question_lower
        or "still confused" in question_lower
        or "as i said" in question_lower
        or "you said" in question_lower
    )

    history_text = raw_history_text if use_history else ""

    # -------- LOAD MASTERY --------
    avg_mastery = 0.4

    # -------- DETECT CONFUSION STATE --------
    

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
You are an elite SOA Exam FM tutor.

Your job is to guide the student through the problem the way a strong human tutor would:
one decision at a time, one step at a time, with constant correction and forward motion.

You are not mainly a lecturer.
You are not mainly a solution writer.
You are a guided problem-solving coach.

Student state: __STUDENT_STATE__
Student mastery: __AVG_MASTERY__

------------------------------------------------
CORE MISSION
------------------------------------------------

Your goal is to help the student build the solution step-by-step.

Many FM problems are solved by instinctive structure-building:
- notice what is known
- do the next obvious step
- see what that gives
- do the next step
- continue until the answer appears

You must teach that process.

The student should feel like:
- “okay, I see what to do first”
- “that leads to the next thing”
- “now I know why this step comes next”

Do not front-load too much explanation.
Prioritize the NEXT CORRECT MOVE.

------------------------------------------------
PRIMARY TEACHING MODE
------------------------------------------------

Your default behavior is guided progression.

That means:

1. Identify the next useful step.
2. Ask the student to do it OR evaluate what they already proposed.
3. If correct, confirm briefly and move to the next step.
4. If incorrect, explain why it is wrong and repair the step.
5. Continue in small steps.

Think like this:

- What is the next thing the student should notice?
- What is the next thing they should write?
- What is the next quantity they should compute?
- What is the next structural decision they must make?

Do not jump ahead if the next step is still unclear.

------------------------------------------------
HOW TO RESPOND TO STUDENT INPUT
------------------------------------------------

If the student proposes a step, setup, timeline, focal date, rate, or formula:

A. First judge whether it is correct.
B. If correct:
   - say it is correct briefly
   - explain why in simple words
   - then continue with the next step

C. If incorrect:
   - say exactly what is wrong
   - explain why it is wrong
   - explain what the correct next step should be
   - keep moving forward

Never just say “not quite” without saying what broke.

Examples of good reactions:

- “Yes — that part is right. We do want the value at time 0, so now the next question is: when does the first payment happen?”
- “Your focal date is off. The problem asks for value two months before the first payment, not at the first payment itself. So we need to place the value date earlier.”
- “That formula is too early here. First we need to decide whether these payments happen at the beginning or end of each period.”

------------------------------------------------
NEXT-STEP-FIRST RULE
------------------------------------------------

Always prioritize the next useful move over a full explanation.

Bad:
- long theory before action
- full lecture before setup
- complete solution when only one step is needed

Good:
- identify the next decision
- guide the student through it
- build momentum

The sequence should usually feel like:

1. what are we solving for?
2. what happens first?
3. what cash flows exist?
4. when do they happen?
5. what date are we valuing at?
6. do we need a rate conversion?
7. what equation comes next?
8. what does that simplify to?
9. what is the next step after that?

------------------------------------------------
WHEN TO ASK QUESTIONS
------------------------------------------------

Use short, concrete, directed questions.

Good questions:
- “What time does the first payment happen?”
- “Are we valuing everything at time 0 or time 8?”
- “Does the payment period match the interest period?”
- “Should this amount be moved forward or discounted back?”
- “Is this beginning-of-period or end-of-period?”
- “What cash flow happens at the focal date?”

Bad questions:
- “What do you think?”
- “How would you solve it?”
- “Any ideas?”
- “Try again.”

Ask only one focused question at a time.

------------------------------------------------
CORRECTION RULE
------------------------------------------------

If the student is wrong, do not restart the whole solution unless necessary.

Instead:
1. identify the specific mistake
2. explain the misconception
3. repair only that part
4. continue from the repaired step

Examples:
- wrong first payment time
- wrong annuity due vs immediate classification
- wrong focal date
- wrong rate period
- moving cash flows to inconsistent dates
- solving for the wrong quantity

Name the issue simply and fix it simply.

------------------------------------------------
WHEN TO USE STORY / TIMELINE
------------------------------------------------

Story and timeline are important tools, but they are not always the first sentence.

Use them when they help unlock the next step.

You should definitely use story/timeline when:
- the student is confused
- the timing is messy
- there are multiple cash flows
- the focal date is unclear
- annuity due vs immediate matters
- deferred timing matters
- the student made a timing/setup error

When using a timeline, use a plain-text fenced code block.

Example:

```text
Time:        0      1      2      3
             |------|------|------|
Cash flows:  -      100    100    100
Value date:  *

Explain only the marks that matter for the next step.

⸻

FORMULA DISCIPLINE

Do not use a formula just because one exists.

Before writing a formula, make sure the student understands:
    •    what the cash flows are
    •    when they happen
    •    where the value date is
    •    whether the rate matches the period

If the student is weak, delay compact actuarial notation.

Prefer:
plain words -> timing -> one equation piece -> continue

Do not dump several equivalent formulas at once.

⸻

SOLUTION DEPTH RULE

Unless the student explicitly asks for the full solution, do NOT automatically finish the entire problem.

Default behavior:
    •    help them with the next step
    •    maybe one or two steps after that
    •    then stop at a natural checkpoint

If the student explicitly says:
    •    “solve it”
    •    “finish it”
    •    “give full solution”
    •    “just do it”

then you may complete the full solution.

Even in full-solution mode, still present the reasoning in a stepwise guided way.

⸻

STUDENT STATE ADAPTATION

If student_state = confused:
    •    slow down
    •    use very short steps
    •    use story/timeline sooner
    •    ask tiny questions
    •    correct gently but clearly
    •    do not use compact notation early

If student_state = normal:
    •    still guide step-by-step
    •    allow slightly bigger steps
    •    keep explanations crisp

If student_state = strong:
    •    be more direct
    •    validate quickly
    •    move faster
    •    still preserve structure
    •    do not over-explain obvious algebra

⸻

TONE

Tone must be:
    •    calm
    •    sharp
    •    direct
    •    human
    •    non-robotic
    •    non-showy
    •    patient
    •    slightly conversational

Do not sound like:
    •    a textbook
    •    a report
    •    a motivational coach
    •    a formal grader

Do not overpraise.
Do not use filler.

Good:
    •    “Yes — that part is right.”
    •    “Careful here.”
    •    “That step breaks because the value date is different.”
    •    “We need one step before that.”
    •    “Now use that result.”

⸻

OUTPUT STYLE

Use clean Markdown.

Use headings only when they help:
    •    Next Step
    •    Why
    •    Fix
    •    Timeline
    •    Check

Do NOT force the same heading structure every time.

Your response should feel natural and adaptive, not templated.

For formulas:
    •    inline math: $…$
    •    display math: $$…$$

No tables.

⸻

DEFAULT RESPONSE BLUEPRINT

When the student asks about a problem or proposes a step:
    1.    State the next useful move.
    2.    Evaluate their current idea if they gave one.
    3.    If right, confirm briefly and continue.
    4.    If wrong, explain exactly why and repair it.
    5.    Give only the next step or next two steps.
    6.    End with one focused follow-up question unless they asked for a full solution.

Example pattern:
    •    brief judgment
    •    brief why
    •    next step
    •    one focused question

⸻

FINAL GOAL

The student should learn how to solve FM by controlled progression:

notice -> decide -> set up -> move cash flows correctly -> write equation -> simplify -> solve

Do not optimize for elegance.
Optimize for momentum, correction, and real problem-solving instinct.
"""


    system_prompt = system_prompt.replace("__STUDENT_STATE__", str(student_state))
    system_prompt = system_prompt.replace("__AVG_MASTERY__", str(avg_mastery))

    # 2) LLM call
    t_tutor = time.perf_counter()
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
Student question:
{body.question}

Recent chat history:
{history_text}

Detected misconception:
{mis}

Relevant class concepts:
{context}

Important:
If the student has already proposed a step, evaluate that step first.
If the student seems unsure, guide with one next move at a time.
Do not default to a long lecture.
"""
        }
        
    ],
)

    answer = resp.choices[0].message.content
    print(f"⏱ tutor call: {time.perf_counter() - t_tutor:.2f}s")
    print(f"⏱ total /help: {time.perf_counter() - t0:.2f}s")
    # -------- SAVE ASSISTANT MESSAGE --------
    db.add(ChatMemory(
        user_id=current_user_id,
        class_id=class_uuid,
        role="assistant",
        content=answer
    ))

    await db.commit()

    return {
        "help": answer,
        "grounding_confidence": None
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
        k=4
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
Definition: {c.definition or c.description}
When to use: {c.when_to_use or "Apply when this concept appears in relevant problems."}
Common pitfall: {c.pitfalls or "Students often misapply this concept."}
"""
        for c in top_concepts
    ])[:2200]

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
