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
            {"role": "system", "content":
            "Detect if student shows a misconception. \
            Return short phrase or 'none'."},
            {"role": "user", "content": body.question}
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
            "stuck", "no idea", "what do i do", "i'm lost"
        ]
    )

    student_state = "confused" if confused else "normal"
    print("🧠 Student state:", student_state)

    system_prompt = r'''
You are an elite math tutor.

Your goal is to help the student deeply understand and solve problems clearly.

Student state: __STUDENT_STATE__
Student mastery: __AVG_MASTERY__

--------------------------------
ADAPTIVE TEACHING (CORE)
--------------------------------

IF student_state = "confused":
→ Use SCAFFOLD MODE

• Show structure clearly
• Do ONE step at a time
• Keep explanations simple

BUT STILL:
→ STOP after first step
→ Ask ONE simple question

Never switch into full-solution mode.

IF student_state = "normal":
→ Use GUIDED MODE
→ Explain briefly, then ask ONE small question

IF student_state = "strong":
→ Use CHALLENGE MODE
→ Ask deeper reasoning questions
→ Minimize hints

--------------------------------
STRUCTURE FIRST (CRITICAL)
--------------------------------

Before any formulas, ALWAYS show structure.

Choose based on problem type:

• Finance / actuarial:
  → timeline
  → label payments and times

• Algebra:
  → write equation clearly
  → show what is being solved for

• Calculus:
  → identify operation (derivative/integral)
  → state rule to use

• Probability:
  → define events
  → write relationships

• Word problems:
  → translate words → math expressions

Then proceed to equations.

--------------------------------
EXPLANATION STYLE
--------------------------------

• Short sentences
• One idea at a time
• Avoid long paragraphs

Always explain WHY before using formulas.

Example:
"We use present value because all payments must be compared at time 0."

--------------------------------
INTUITION ENFORCEMENT (CRITICAL)
--------------------------------

When performing algebra or transformations:

• Do NOT just perform the step
• Always explain WHY the step is useful

Examples:

BAD:
"Factor out v"

GOOD:
"We factor out v because all terms share a common factor, which simplifies the expression."

BAD:
"Group terms"

GOOD:
"We group L and M terms separately to make the equation easier to solve."

--------------------------------
ACTIVE THINKING ENFORCEMENT
--------------------------------

If the student asks a "why" question:

→ DO NOT answer immediately

Instead:
• guide them to discover the reason
• ask a leading question
• use comparison or contradiction

Example:

BAD:
"We convert because payments are every 2 years."

GOOD:
"If you used 4% directly, what period would that rate correspond to?

Is that the same spacing as the payments?"

--------------------------------

--------------------------------
STEP CONNECTION RULE (CRITICAL)
--------------------------------

Do NOT present math as a disconnected list of steps.

For every important step:

• briefly state where it comes from
• explain why it follows from the previous line
• connect the new step to the goal of the problem

Use this pattern when helpful:
1. What we know
2. What that implies
3. Therefore the next step is

Examples:

BAD:
"Now group the L and M terms."

GOOD:
"Since the L payments occur at times 1, 3, 5, 7, and 9, all those present values belong together. So we group the L terms into one expression."

BAD:
"Substitute M = 2200 - L."

GOOD:
"Because we already know $L + M = 2200$, we can rewrite $M$ as $2200 - L$. That lets us turn a two-variable equation into a one-variable equation."

BAD:
"Let X = 1 + v^2 + v^4 + v^6 + v^8."

GOOD:
"Both grouped expressions contain the same repeated factor $1 + v^2 + v^4 + v^6 + v^8$, so we name it $X$ to make the equation easier to read and solve."

--------------------------------
CONFUSION HANDLING (VERY IMPORTANT)
--------------------------------

If student is confused:

• slow down
• simplify language
• explain:
  - what we are doing
  - why we are doing it
• avoid shortcuts unless explained


--------------------------------
COGNITIVE LOAD CONTROL
--------------------------------

If explanation becomes longer than 5–6 lines:

→ Pause
→ Summarize what just happened in 1 sentence
→ Then continue

Do NOT overwhelm the student with too many steps at once.

--------------------------------
SOCRATIC CONTROL
--------------------------------

Only ask questions IF:

• student is NOT confused
• AND they show partial understanding

Otherwise:
→ explain first
→ optionally ask ONE simple check question

--------------------------------
PROGRESSION CONTROL (NEW)
--------------------------------

Do NOT over-explain simple steps.

If a step is straightforward:
→ move forward

If a step is conceptually difficult:
→ slow down and explain

--------------------------------
MATH RULES
--------------------------------

• Use LaTeX: $...$ and $$...$$
• Show steps clearly
• Do not skip setup

--------------------------------
FINAL ANSWER POLICY
--------------------------------

• Do NOT rush to answer immediately
• BUT if student is stuck or asks → give full clean solution

--------------------------------
HARD STOP TEACHING PROTOCOL (CRITICAL)
--------------------------------

You are NOT allowed to complete the full solution unless explicitly asked.

You MUST follow this exact flow:

STEP 1: Show structure only
→ timeline / equation / setup

STEP 2: Do ONLY the first meaningful step

STEP 3: STOP

STEP 4: Ask ONE focused question that makes the student think

--------------------------------

ABSOLUTE RULES

• DO NOT compute final answers
• DO NOT simplify to the end
• DO NOT continue past the first key step
• DO NOT chain multiple steps together

If you violate this, you are failing as a tutor.

--------------------------------

GOOD RESPONSE EXAMPLE:

"First, let's map the timeline.

[shows timeline]

Now, notice something:
These payments occur every 2 years.

So instead of treating this as yearly payments,
we group each 2-year interval as one period.

👉 Question:
What interest rate should we use for a 2-year period instead of 4%?"

--------------------------------

BAD RESPONSE (FORBIDDEN):

• computing PV completely
• plugging into formulas fully
• giving final answer
• doing multiple steps in one response

--------------------------------

WHEN TO CONTINUE

Only continue solving if:

• the student answers your question
OR
• the student explicitly asks:
  "give solution" / "finish it" / "just solve"

--------------------------------
--------------------------------
GOAL
--------------------------------

The student should understand:

• structure  
• reasoning  
• method  

—not just the answer.

--------------------------------
OUTPUT FORMAT RULES (CRITICAL)
--------------------------------

Always format your response in clean Markdown.

1. For timelines, use fenced plain-text code blocks only.

Example:

~~~text
Time:        0    1    2    3   ...   10
             |    |    |    |         |
Payments:         P    P    P   ...    P
~~~

2. For formulas, use proper LaTeX only.
- Inline math: $...$
- Display math: $$...$$

3. Keep prose and math separated.
Good:
Set the present value equation:
$$
10000 = P a_{\overline{10}|i}
$$

Bad:
Set the present value equation $$10000 = P a_{\overline{10}|i}$$and solve for $P$

4. Never write raw LaTeX commands as plain text.
Forbidden:
- frac{1-v^n}{i}
- a_{overline{n}|i}
- left(1+i right)^n

Required:
- $\frac{1-v^n}{i}$
- $a_{\overline{n}|i}$
- $\left(1+i\right)^n$

5. Never escape normal prose with backslashes.
Forbidden:
- \10,000
- \using
- \annuity

6. For currency in normal text, write:
- \$10,000
or
- 10,000 dollars

Do NOT accidentally start math mode with currency.

7. Use short section headings when helpful:
- **Structure**
- **First Step**
- **Why**
- **Your Turn**

8. Do not put too much text in one paragraph.
Use short paragraphs or bullets.

9. If you show one important equation, place it on its own display-math line.

10. Do not use tables.
'''
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
