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
from app.models import (
    Concept,
    Note,
    NoteConcept,
    ChatMemory,
    StudentPitfall,
    Mastery,
    WorkReviewSession,
    StepReview,
)

from app.db import get_db
from app.services.llm import client, kimi_client, top_k_concepts
from app.services.file_extraction import extract_text
from app.services.auth import get_current_user_id
from app.services.mastery import update_mastery_value

router = APIRouter(prefix="/homework", tags=["homework"])


class HWIn(BaseModel):
    class_id: str
    question: str

class StepCheckIn(BaseModel):
    class_id: str
    session_id: str
    user_prompt: str
    selected_step: str | None = None
    selected_region: dict | None = None
    action: str = "check_this_step"
    # check_this_step | help_me_continue | what_did_i_do_right | what_to_watch_next_time
    
class StepCheckOut(BaseModel):
    step_verdict: str | None = None
    concept_name: str | None = None
    correct_parts: list[str] = []
    issues: list[str] = []
    next_step: str | None = None
    next_time_rule: str | None = None
    pitfall_tag: str | None = None
    confidence: float | None = None
    response_markdown: str

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
    
def safe_json_loads(raw: str):
    if not raw:
        return None
    cleaned = raw.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except Exception:
        return None

def flatten_note_json(content):
    if content is None:
        return ""

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, dict):
        parts = [flatten_note_json(v) for v in content.values()]
        return "\n".join(p for p in parts if p)

    if isinstance(content, list):
        parts = [flatten_note_json(v) for v in content]
        return "\n".join(p for p in parts if p)

    return str(content).strip()


def extract_final_answer(resp) -> tuple[str, str | None]:
    """
    Extracts only the student-facing final answer.
    Does NOT expose reasoning_content.
    Returns: (answer, finish_reason)
    """
    if not resp or not resp.choices:
        return "", None

    choice = resp.choices[0]
    message = choice.message
    finish_reason = getattr(choice, "finish_reason", None)

    answer = (getattr(message, "content", None) or "").strip()

    if not answer:
        extra = getattr(message, "model_extra", {}) or {}
        answer = (
            extra.get("text")
            or extra.get("final")
            or extra.get("answer")
            or ""
        ).strip()

    return answer, finish_reason

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

        use_history = any(
            phrase in question_lower
            for phrase in [
                "continue",
                "still confused",
                "as i said",
                "you said",
                "from before",
                "last step",
                "previous step",
                "that step",
                "my setup",
                "is this right",
                "did i do this right",
                "where did i go wrong"
            ]
        )

        history_text = raw_history_text if use_history else ""
        print("\n📜 Chat History Used for Analysis:")
        print(history_text)
        # -------- LOAD GROUNDED CONCEPTS FOR ANALYZE MODE --------
        res = await db.execute(
            select(Concept).where(
                Concept.class_id == class_uuid,
                Concept.user_id == current_user_id
            )
        )

        concepts = res.scalars().all()

        scored_concepts = await top_k_concepts(
            body.question,
            concepts,
            k=5
        )

        MIN_GROUNDING_SCORE = 0.25

        top_concepts = [
            c for score, c in scored_concepts
            if score is not None and score >= MIN_GROUNDING_SCORE
        ]

        concept_context = "\n\n".join([
            f"""
        CONCEPT KNOWLEDGE

        Name: {c.name}
        
        Definition:
        {c.definition or c.description or "No definition stored."}
        
        When to use:
        {c.when_to_use or "No when-to-use guidance stored."}

        Common pitfall:
        {c.pitfalls or "No pitfall stored."}

        Evidence from notes:
        {c.evidence or "No direct note evidence stored."}

        Confidence:
        {float(c.confidence or 0.5)}
        """
            for c in top_concepts
        ])[:3000]
        resp = kimi_client.chat.completions.create(
            model="kimi-k2.5",
            messages=[
                {
                    "role": "system",
                    "content": """
    Analyze the student's reasoning in the conversation.
    Use the provided class concepts and note evidence when available.

    Do not invent a pitfall unless it is supported by the student's conversation or the provided concepts.

    If the evidence is weak, keep the pitfall broad and lower confidence in your wording.
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
                    "content": f"""
                Student conversation:
                {history_text}

                Relevant class concepts and note evidence:
                {concept_context}
                """
                }
            ],
            max_tokens=1800,
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
            max_tokens=2200,
        )

        natural_answer, natural_finish_reason = extract_final_answer(natural_resp)

        if not natural_answer:
            natural_answer = "The analysis model returned an empty answer. Try asking again with the specific work you want reviewed."

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
        k=5
    )
    print(f"⏱ top_k_concepts: {time.perf_counter() - t_topk:.2f}s")

    # Separate concepts from scores
    MIN_GROUNDING_SCORE = 0.25

    top_concepts = [
        c for score, c in scored_concepts
        if score is not None and score >= MIN_GROUNDING_SCORE
    ]

    if not top_concepts:
        return {
            "help": (
               "I could not find enough relevant concepts from your uploaded notes for this question. "
                "Try uploading/extracting more notes, or ask the question with more details from the problem."
            ),
            "grounding_confidence": 0.0
        }
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
    {c.definition or c.description or "No definition stored."}

    When to use:
    {c.when_to_use or "No when-to-use guidance stored."}

    Common pitfall:
    {c.pitfalls or "No pitfall stored."}

    Evidence from notes:
    {c.evidence or "No direct note evidence stored."}

    Confidence:
    {float(c.confidence or 0.5)}
    """
        for c in top_concepts
    ])[:2500]
    
    top_concept_ids = [c.id for c in top_concepts]

    note_res = await db.execute(
        select(Note)
        .join(NoteConcept, NoteConcept.note_id == Note.id)
        .where(
            Note.user_id == current_user_id,
            Note.class_id == class_uuid,
            NoteConcept.concept_id.in_(top_concept_ids)
        )
        .limit(5)
    )

    relevant_notes = note_res.scalars().all()
    
    note_context = "\n\n".join([
        f"""
    NOTE SOURCE

    Title:
    {n.title}

    Text:
    {flatten_note_json(n.content_json)[:800]}
    """
        for n in relevant_notes
    ])[:2500]
    
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
        .limit(4)
    )
    print(f"⏱ history query: {time.perf_counter() - t_history:.2f}s")

    history = mem_res.fetchall()

    raw_history_text = "\n".join(
        [f"{r[0]}: {r[1]}" for r in reversed(history)]
    )

    use_history = any(
        phrase in question_lower
    for phrase in [
        "continue",
        "still confused",
        "as i said",
        "you said",
        "from before",
        "last step",
        "previous step",
        "that step",
        "my setup",
        "is this right",
        "did i do this right",
        "where did i go wrong"
    ]
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

You are an elite beginner-first SOA Exam FM tutor.

You help students learn actuarial mathematics by teaching the setup, not by dumping formulas.

CRITICAL OUTPUT RULE:
Return ONLY the polished tutor response that the student should see.
Do NOT include hidden reasoning.
Do NOT include analysis notes.
Do NOT narrate your thinking process.
Do NOT say “I need to” or “The user is asking”.
Do NOT expose scratch work.
Write directly to the student.

IMPORTANT:
Do not spend many tokens reasoning internally.
Think briefly, then write the final tutor answer.
Your final answer must be placed in message.content.
Do not put the useful answer only in reasoning_content.
Keep internal reasoning short.

GROUNDING RULES:
Use the provided Relevant class concepts as the main source of truth.
If Relevant note snippets are included, use them only as supporting source material.
Do not claim something came from the student's notes unless it appears in the provided context.
You may use basic algebra and arithmetic.
Class-specific formulas, classifications, definitions, and shortcuts should come from the provided concepts/notes when possible.
If the concept context is weak or incomplete, say that briefly and still give a careful general setup when the math is standard.

STUDENT PROFILE:
The student is learning SOA Exam FM.
Assume they may struggle with:
- identifying the problem type
- translating words into cash flows
- building a timeline
- choosing the focal date
- matching rate period to payment period
- knowing when a formula applies

Student state: __STUDENT_STATE__
Student mastery: __AVG_MASTERY__

CORE TEACHING PIPELINE:
For FM money-at-time problems, teach in this order:

1. Plain-English story
2. Cash flows
3. Timeline
4. Focal date
5. Rate/payment-period check
6. Setup equation
7. Calculation only when appropriate

This pipeline matters more than elegance.

BEGINNER-FIRST RULE:
Make the setup feel obvious.
Use short paragraphs.
Use simple language.
Do not lead with compact actuarial notation.
Do not use multiple methods unless the student asks.
Do not over-explain every algebra detail unless it helps the setup.

TIMELINE RULE:
For money-at-time problems, include a plain-text fenced timeline before meaningful computation.

Use this style:

```text
Time:        0      1      2      ...      n
             |------|------|------|--------|
Cash flows:  ...
Value date:  *
```

Label the key dates clearly.

FOCAL DATE RULE:
Always identify the date we care about in plain English.

Examples:

* “We want the value at time 14 because year 15 starts at time 14.”
* “We value the bond right after the coupon date.”
* “All cash flows must be compared at the same date.”

RATE CHECK RULE:
Always check whether the coupon/payment period matches the yield period.
Never silently use a mismatched rate.

BOND RULES:
For bond problems, clearly distinguish:

* coupon amount
* yield rate per coupon period
* book value
* redemption value
* premium or discount
* amortization of premium
* accumulation of discount

For discount bonds:
Accumulation of discount during a period = interest earned on book value - coupon.

For premium bonds:
Amortization of premium during a period = coupon - interest earned on book value.

MULTI-PART PROBLEM RULE:
If the question has parts (a), (b), (c), handle them separately.
Use headings like:

Part (a)

Part (b)

Do not mix the timelines or formulas across parts.

RESPONSE MODE POLICY:
Default mode is TEACHING MODE unless the student explicitly asks for a full solution.

TEACHING MODE:
Use this when the student asks a raw homework problem, asks for help, asks "how do I do this?", asks for a hint, asks for next step, or sends a problem without explicitly requesting the final answer.

In teaching mode:
* do NOT calculate the final answer
* do NOT finish all parts
* teach the story
* identify cash flows
* draw the timeline
* identify the focal date
* check the rate period
* write only the first useful setup equation
* explain why that setup is correct
* end with ONE small check question

FULL SOLUTION MODE:
Use this only when the student explicitly says:
"solve this fully", "full solution", "give final answer", "answer all parts", "calculate all", "complete solution", or similar.

In full solution mode:
* show the setup
* compute the final answer
* briefly explain why the answer makes sense

IMPORTANT:
The words "find", "find the amount", "find the value", or "find the premium" are part of normal homework wording. They do NOT by themselves mean the student wants a full solution.

CONFUSED STUDENT RULE:
If student_state = confused:

* use shorter sentences
* one idea at a time
* no multiple methods
* no shortcut-first explanation
* end with one tiny check question

STYLE:
Calm.
Clear.
Direct.
Beginner-safe.
Not robotic.
Not textbook-like.
No excessive praise.
No tables.

MATH FORMAT:
Use Markdown.
Use LaTeX for math.

Inline math: $…$
Display math:

$$
…
$$

Use plain-text fenced code blocks only for timelines.

DEFAULT RESPONSE STRUCTURE:
Use these headings when helpful:

Part (a)

Story
Cash Flows
Timeline
Focal Date
Rate Check
Setup
Calculation
Answer

Part (b)

Story
Cash Flows
Timeline
Focal Date
Rate Check
Setup
Calculation
Answer

FINAL CHECK BEFORE RESPONDING:
Before sending, make sure the response:

* does not reveal scratch reasoning
* does not talk about “the user”
* does not include hidden analysis
* directly teaches the student
* has clean Markdown
* gives either a clear next step or a final answer, depending on the request
"""


    system_prompt = system_prompt.replace("__STUDENT_STATE__", str(student_state))
    system_prompt = system_prompt.replace("__AVG_MASTERY__", str(avg_mastery))

    should_include_notes = any(
        phrase in question_lower
        for phrase in [
            "based on my notes",
            "from the notes",
            "according to the notes",
            "what did my notes say",
            "use my notes",
            "what concept",
            "which formula",
            "why",
            "explain",
            "definition",
            "where does this come from"
        ]
    )

    wants_full_solution = any(
        phrase in question_lower
        for phrase in [
            "solve it",
            "solve this",
            "solve this question",
            "full solution",
            "finish it",
            "give final answer",
            "calculate all",
            "do the whole problem",
            "complete solution",
            "fully solve",
            "answer all parts",
            "show full solution",
            "step by step answer",
        ]
    )

    max_output_tokens = 6000 if wants_full_solution else 3500
    response_mode = "FULL_SOLUTION" if wants_full_solution else "TEACHING_MODE"
    user_context = f"""
Response mode:
{response_mode}

Student question:
{body.question}

Detected misconception:
{mis}

Relevant class concepts:
{context}
    """

    if history_text.strip():
        user_context += f"""

    Recent chat history:
    {history_text}
    """

    if should_include_notes and note_context.strip():
        user_context += f"""

    Relevant note snippets:
    {note_context}
    """

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
                "content": user_context
            }
        ],
        
        max_tokens=max_output_tokens,
    )

    answer, finish_reason = extract_final_answer(resp)

    print("\n===== KIMI RESPONSE DEBUG =====")
    print("finish_reason:", finish_reason)
    print("answer_preview:", repr(answer[:500]))
    print("answer_length:", len(answer))

    # Retry once if Kimi used all tokens in reasoning_content and returned blank content.
    if not answer:
        print("⚠️ Empty Kimi content. Retrying with final-answer-only prompt...")

        retry_resp = kimi_client.chat.completions.create(
            model="kimi-k2.5",
            messages=[
                {
                    "role": "system",
                    "content": """
You are an SOA Exam FM tutor.

Return ONLY the final student-facing answer.
Do not include hidden reasoning.
Do not include analysis notes.
Do not narrate your thought process.
Do not say "the user".
Use clean Markdown.
Be clear, beginner-friendly, and direct.

For money-at-time problems:
1. Story
2. Cash flows
3. Timeline
4. Focal date
5. Rate check
6. Setup
7. Calculation
8. Answer
    """
                },
                {
                    "role": "user",
                    "content": f"""
Solve this question for the student.

Student question:
{body.question}

Relevant class concepts:
{context}
    """
                }
            ],
            max_tokens=4000,
        )

        answer, retry_finish_reason = extract_final_answer(retry_resp)
    
        print("\n===== KIMI RETRY DEBUG =====")
        print("retry_finish_reason:", retry_finish_reason)
        print("retry_answer_preview:", repr(answer[:500]))
        print("retry_answer_length:", len(answer))

    if not answer:
        answer = (
            "The tutor model returned an empty final answer twice. "
            "Try again, or split the problem into part (a) and part (b)."
        )

    print(f"⏱ tutor call: {time.perf_counter() - t_tutor:.2f}s")
    print(f"⏱ total /help: {time.perf_counter() - t0:.2f}s")
    grounding_confidence = 0.0

    if scored_concepts:
        grounding_confidence = round(
            sum(float(score) for score, _ in scored_concepts[:5]) / min(len(scored_concepts), 5),
            3
        )
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
        "answer": answer,
        "response": answer,
        "message": answer,
        "grounding_confidence": grounding_confidence,
        "grounded_concepts": [
            {
                "name": c.name,
                "score": round(float(score), 3),
                "has_evidence": bool(c.evidence),
                "confidence": float(c.confidence or 0.5)
            }
            for score, c in scored_concepts[:5]
        ]
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


@router.post("/review-work-session")
async def create_review_work_session(
    class_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    if not class_id:
        raise HTTPException(400, "class_id required")

    try:
        class_uuid = UUID(class_id)
    except:
        raise HTTPException(400, "Invalid class_id")

    content = await file.read()

    extracted_text = ""
    try:
        extracted_text = await extract_text(file.filename, content)
        extracted_text = clean_extracted_text(extracted_text)
    except Exception:
        extracted_text = ""

    img_b64 = base64.b64encode(content).decode()
    source_type = "pdf" if (file.filename or "").lower().endswith(".pdf") else "image"
    session = WorkReviewSession(
        user_id=current_user_id,
        class_id=class_uuid,
        filename=file.filename,
        extracted_text=extracted_text,
        image_base64=img_b64,
        source_type=source_type
    )

    db.add(session)
    await db.commit()
    await db.refresh(session)

    return {
        "session_id": str(session.id),
        "filename": file.filename,
        "extracted_text": extracted_text[:4000]
    }

@router.get("/review-work-sessions/{class_id}")
async def get_review_work_sessions(
    class_id: str,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    try:
        class_uuid = UUID(class_id)
    except:
        raise HTTPException(400, "Invalid class_id")

    res = await db.execute(
        select(WorkReviewSession)
        .where(
            WorkReviewSession.user_id == current_user_id,
            WorkReviewSession.class_id == class_uuid
        )
        .order_by(WorkReviewSession.created_at.desc())
        .limit(20)
    )

    rows = res.scalars().all()

    return [
        {
            "id": str(r.id),
            "filename": r.filename,
            "source_type": r.source_type,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]

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
    mime_type = "application/pdf" if (file.filename or "").lower().endswith(".pdf") else "image/png"
    # -------- RETRIEVE RELEVANT CONCEPTS --------
    content = await file.read()

    try:
        extracted_text = await extract_text(file.filename, content)
        extracted_text = clean_extracted_text(extracted_text)
    except Exception:
        extracted_text = ""

    retrieval_query = f"""
    Student uploaded work review.

    Extracted text:
    {extracted_text[:3000]}

    Task:
    Review the student's reasoning and match it to relevant class concepts.
    """

    scored_concepts = await top_k_concepts(
        retrieval_query,
        concepts,
        k=4
    )

    MIN_GROUNDING_SCORE = 0.25

    top_concepts = [
        c for score, c in scored_concepts
        if score is not None and score >= MIN_GROUNDING_SCORE
    ]

    if not top_concepts:
        return {
            "review": (
                "I could not find enough relevant concepts from your uploaded notes to review this work reliably. "
                "Upload or extract notes for this topic first, or include more of the problem statement."
            ),
            "grounding_confidence": 0.0,
            "grounded_concepts": []
        }

    print("\n===== REVIEW CONCEPT RETRIEVAL =====")

    for i, (score, c) in enumerate(scored_concepts, 1):
        print(f"\n[Concept {i}]")
        print(f"Score: {round(score,4)}")
        print(f"Name: {c.name}")

    

    import base64
    img_b64 = base64.b64encode(content).decode()

    # -------- BUILD CONCEPT CONTEXT --------
    context = "\n\n".join([
        f"""
    CONCEPT KNOWLEDGE

    Name: {c.name}
    
    Definition:
    {c.definition or c.description or "No definition stored."}

    When to use:
    {c.when_to_use or "No when-to-use guidance stored."}
    
    Common pitfall:
    {c.pitfalls or "No pitfall stored."}

    Evidence from notes:
    {c.evidence or "No direct note evidence stored."}

    Confidence:
    {float(c.confidence or 0.5)}
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
            GROUNDING RULES:

            Use the provided Relevant class concepts as your main source of truth.

            If the relevant concepts/evidence do not support a claim, do not pretend the claim came from the student's notes.

            You may use basic algebra and arithmetic, but class-specific formulas, definitions, classifications, and shortcuts must come from the provided concepts.

            If the uploaded work is unclear or the concept context is insufficient, say that clearly instead of giving a confident ungrounded review.

            When you reference a concept, use its concept name naturally.

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

• If the student’s work is mostly correct, preserve their path rather than replacing it
• If the visible error starts earlier than the current line, name where the real break begins
• Distinguish between:
  - correct
  - correct but incomplete
  - right concept, wrong execution
  - wrong concept
  - arithmetic/algebra slip
  
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
                            "url": f"data:{mime_type};base64,{img_b64}"
                        }
                    }
                ]
            }
        ],
        max_tokens=3000,
    )

    grounding_confidence = 0.0

    if scored_concepts:
        grounding_confidence = round(
            sum(float(score) for score, _ in scored_concepts[:4]) / min(len(scored_concepts), 4),
            3
        )

    review_answer, review_finish_reason = extract_final_answer(resp)

    if not review_answer:
        review_answer = (
            "The review model returned an empty final answer. "
            "Try uploading a clearer image or splitting the work into a smaller section."
        )

    return {
        "review": review_answer,
        "grounding_confidence": grounding_confidence,
        "grounded_concepts": [
            {
                "name": c.name,
                "score": round(float(score), 3),
                "has_evidence": bool(c.evidence),
                "confidence": float(c.confidence or 0.5)
            }
            for score, c in scored_concepts[:4]
        ]
    }

@router.post("/step-check")
async def step_check(
    body: StepCheckIn,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    if not body.class_id:
        raise HTTPException(400, "class_id required")

    try:
        class_uuid = UUID(body.class_id)
        session_uuid = UUID(body.session_id)
    except:
        raise HTTPException(400, "Invalid class_id or session_id")

    session = await db.get(WorkReviewSession, session_uuid)
    if not session or str(session.user_id) != str(current_user_id):
        raise HTTPException(404, "Review session not found")

    # -------- LOAD CLASS CONCEPTS --------
    res = await db.execute(
        select(Concept).where(
            Concept.class_id == class_uuid,
            Concept.user_id == current_user_id
        )
    )
    concepts = res.scalars().all()
    mime_type = "application/pdf" if session.source_type == "pdf" else "image/png"
    retrieval_query = f"""
    Student uploaded work.

    User prompt:
    {body.user_prompt}

    Selected step:
    {body.selected_step or ""}

    Requested action:
    {body.action}

    Extracted text from upload:
    {session.extracted_text[:3000] if session.extracted_text else ""}
    """

    scored_concepts = await top_k_concepts(
        retrieval_query,
        concepts,
        k=4
    )

    MIN_GROUNDING_SCORE = 0.25

    top_concepts = [
        c for score, c in scored_concepts
        if score is not None and score >= MIN_GROUNDING_SCORE
    ]

    if not top_concepts:
        return {
            "step_verdict": None,
            "concept_name": None,
            "correct_parts": [],
            "issues": [
                "I could not find enough relevant grounded concepts from your uploaded notes for this step."
            ],
            "next_step": "Upload or extract notes for this topic, or give more problem context.",
            "next_time_rule": "Do not rely on the tutor's feedback unless the system found matching class concepts.",
            "pitfall_tag": "missing_grounding",
            "confidence": 0.0,
            "response_markdown": (
                "I do not have enough grounded class-note context to check this step reliably yet. "
                "Upload/extract the relevant notes or include more of the problem statement."
            )
        }

    context = "\n\n".join([
        f"""
    CONCEPT KNOWLEDGE

    Name: {c.name}

    Definition:
    {c.definition or c.description or "No definition stored."}

    When to use:
    {c.when_to_use or "No when-to-use guidance stored."}

    Common pitfall:
    {c.pitfalls or "No pitfall stored."}

    Evidence from notes:
    {c.evidence or "No direct note evidence stored."}

    Confidence:
    {float(c.confidence or 0.5)}
    """
        for c in top_concepts
    ])[:3000]

    structured_resp = kimi_client.chat.completions.create(
        model="kimi-k2.5",
        messages=[
            {
                "role": "system",
                "content": f"""
You are a step-based remediation tutor.

You are reviewing a student's uploaded work and helping at a specific step.

Relevant concepts:
{context}

GROUNDING RULES:

Use the provided Relevant concepts as the main source of truth.

If the selected step cannot be checked from the uploaded work and the provided concepts, lower confidence and say what information is missing.

Do not invent a class-specific rule, formula, or shortcut unless it appears in the concept context.

You may use basic algebra/arithmetic, but concept classification must come from the grounded concepts.

If no concept clearly applies, set concept_name to null and confidence below 0.4.

Return JSON only.

Schema:
{{
  "step_verdict": "correct|correct_but_incomplete|reasonable_idea_wrong_execution|wrong_concept|algebra_slip|timing_error|unit_error|unsupported_jump",
  "concept_name": "string or null",
  "correct_parts": ["..."],
  "issues": ["..."],
  "error_type": "short_snake_case or null",
  "root_cause_step": "string or null",
  "next_step": "one clear next move only",
  "next_time_rule": "reusable rule for future problems",
  "pitfall_tag": "short_snake_case or null",
  "confidence": 0.0
}}

Rules:
- Preserve correct student reasoning when possible
- Do NOT fully solve unless absolutely necessary
- Focus locally on the selected step
- Distinguish the visible error from the root cause
- If the selected step is correct, explicitly say it is correct
- If the selected step is partly right, repair it instead of replacing it
- Prefer one verdict only from this allowed set:
  correct
  correct_but_incomplete
  reasonable_idea_wrong_execution
  wrong_concept
  algebra_slip
  timing_error
  unit_error
  unsupported_jump
- If uncertain, choose the closest verdict and lower confidence
"""
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"""
Student prompt: {body.user_prompt}
Selected step: {body.selected_step or ""}
Requested action: {body.action}

Extracted text from upload:
{session.extracted_text[:5000]}
"""
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{session.image_base64}"
                        }
                    }
                ]
            }
        ],
        max_tokens=2000,
        
    )

    raw_structured, structured_finish_reason = extract_final_answer(structured_resp)
    parsed = safe_json_loads(raw_structured)

    if not parsed:
        parsed = {
            "step_verdict": None,
            "concept_name": None,
            "correct_parts": [],
            "issues": ["Could not parse structured step review."],
            "error_type": None,
            "root_cause_step": None,
            "next_step": "Re-state the selected step and ask the model to review that exact step.",
            "next_time_rule": None,
            "pitfall_tag": None,
            "confidence": 0.2,
        }

    natural_resp = kimi_client.chat.completions.create(
        model="kimi-k2.5",
        messages=[
            {
                "role": "system",
                "content": """
You are a natural tutor.

Turn the structured step review into clean markdown with these sections:

## What You Did Right
## What’s Off Here
## Is This Step Valid?
## Next Step
## Next-Time Rule

Rules:
- sound like a real tutor
- do not mention JSON
- do not mention tags
- do not dump a full solution
- be specific to the student's current step
"""
            },
            {
                "role": "user",
                "content": f"""
Student prompt: {body.user_prompt}
Selected step: {body.selected_step or ""}

Structured review:
{json.dumps(parsed, indent=2)}
"""
            }
        ],
        max_tokens=2500,
    )

    response_markdown, natural_finish_reason = extract_final_answer(natural_resp)

    if not response_markdown:
        response_markdown = (
            "The step-check model returned an empty final answer. "
            "Try restating the selected step more specifically."
        )

    review_row = StepReview(
        user_id=current_user_id,
        class_id=class_uuid,
        session_id=session_uuid,
        user_prompt=body.user_prompt,
        selected_step=body.selected_step,
        selected_region=body.selected_region,
        concept_name=parsed.get("concept_name"),
        step_verdict=parsed.get("step_verdict"),
        error_type=parsed.get("error_type"),
        root_cause_step=parsed.get("root_cause_step"),
        correct_parts=parsed.get("correct_parts", []),
        issues=parsed.get("issues", []),
        next_step=parsed.get("next_step"),
        next_time_rule=parsed.get("next_time_rule"),
        pitfall_tag=parsed.get("pitfall_tag"),
        confidence=parsed.get("confidence"),
        raw_feedback=response_markdown,
    )
    db.add(review_row)

    pitfall_tag = parsed.get("pitfall_tag")
    if pitfall_tag:
        stmt = insert(StudentPitfall).values(
            user_id=current_user_id,
            class_id=class_uuid,
            pitfall=pitfall_tag,
            explanation=parsed.get("next_time_rule")
        ).on_conflict_do_update(
            index_elements=["user_id", "class_id", "pitfall"],
            set_={"explanation": parsed.get("next_time_rule")}
        )
        await db.execute(stmt)

    db.add(ChatMemory(
        user_id=current_user_id,
        class_id=class_uuid,
        role="user",
        content=f"[STEP CHECK] {body.user_prompt} | selected_step={body.selected_step or ''}"
    ))

    db.add(ChatMemory(
        user_id=current_user_id,
        class_id=class_uuid,
        role="assistant",
        content=response_markdown
    ))

    await db.commit()

    return {
        "step_verdict": parsed.get("step_verdict"),
        "concept_name": parsed.get("concept_name"),
        "correct_parts": parsed.get("correct_parts", []),
        "issues": parsed.get("issues", []),
        "next_step": parsed.get("next_step"),
        "next_time_rule": parsed.get("next_time_rule"),
        "pitfall_tag": parsed.get("pitfall_tag"),
        "confidence": parsed.get("confidence"),
        "response_markdown": response_markdown,
        "grounding_confidence": (
            round(
                sum(float(score) for score, _ in scored_concepts[:4]) / min(len(scored_concepts), 4),
                3
            )
            if scored_concepts else 0.0
        ),
        "grounded_concepts": [
            {
                "name": c.name,
                "score": round(float(score), 3),
                "has_evidence": bool(c.evidence),
                "confidence": float(c.confidence or 0.5)
            }
            for score, c in scored_concepts[:4]
        ]
    }
  
@router.get("/step-review-history/{session_id}")
async def get_step_review_history(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    try:
        session_uuid = UUID(session_id)
    except:
        raise HTTPException(400, "Invalid session_id")

    session = await db.get(WorkReviewSession, session_uuid)
    if not session or str(session.user_id) != str(current_user_id):
        raise HTTPException(404, "Review session not found")

    res = await db.execute(
        select(StepReview)
        .where(
            StepReview.session_id == session_uuid,
            StepReview.user_id == current_user_id
        )
        .order_by(StepReview.created_at.asc())
    )

    rows = res.scalars().all()

    return [
        {
            "id": str(r.id),
            "user_prompt": r.user_prompt,
            "selected_step": r.selected_step,
            "concept_name": r.concept_name,
            "step_verdict": r.step_verdict,
            "error_type": r.error_type,
            "root_cause_step": r.root_cause_step,
            "correct_parts": r.correct_parts or [],
            "issues": r.issues or [],
            "next_step": r.next_step,
            "next_time_rule": r.next_time_rule,
            "pitfall_tag": r.pitfall_tag,
            "confidence": r.confidence,
            "raw_feedback": r.raw_feedback,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
  
  
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
