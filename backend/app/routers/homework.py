from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from app.models import Concept, ChatMemory, StudentPitfall
from app.db import get_db
from app.services.llm import client, kimi_client, top_k_concepts, grounding_confidence
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
                    "role":"system",
                    "content":"""
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
                    "role":"user",
                    "content":history_text
                }
            ],
        )

        import json

        raw = resp.choices[0].message.content
        raw = raw.replace("```json","").replace("```","").strip()
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
            db.add(
                StudentPitfall(
                    user_id=current_user_id,
                    class_id=class_uuid,
                    pitfall=p["tag"],
                    explanation=p.get("explanation")
                )
            )
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
    resp = kimi_client.chat.completions.create(
        model="kimi-k2.5",
        messages=[
            {
                
                 "role":"system",
                 "content":
            f"""You are a patient, expert tutor helping with homework.
            SOCRATIC TUTOR MODE (STRICT)

            You are NOT allowed to immediately solve the student's problem.

            Your role is to guide the student to the answer step-by-step.

            Rules:

            1. Never give the final numeric answer unless the student explicitly asks for it.
            2. Never compute the final result in the first response.
            3. First help the student identify the correct concept or method.
            4. Ask a question that helps the student take the next step.
            5. Reveal at most ONE step of reasoning at a time.
            6. After each explanation, ask a guiding question.

            If the student asks for the answer directly:
            → ask them what step they tried first.

            If the student says "hint":
            → give only a small hint.

            If the student says "next step":
            → reveal the next reasoning step.

            IMPORTANT:
            The goal is learning, not speed.
            Always pause before the final calculation and ask the student what they think the next step is.
            FINAL ANSWER SAFETY RULE

            Do NOT compute the final numeric answer unless the student explicitly requests it.

            Instead:

            • stop one step before the final calculation
            • ask the student to perform the final step
            • check their reasoning
        
            Example behavior:

            Instead of:
            "The answer is X ≈ 5505."

            Say:
            "Now we have the equation. What value do you get for X when you solve it?"
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
                "role":"system",
                "content":f"""
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
                "role":"user",
                "content":[
                    {
                        "type":"text",
                        "text":"Here is my work so far on the problem. Please review it."
                    },
                    {
                        "type":"image_url",
                        "image_url":{
                            "url":f"data:image/png;base64,{img_b64}"
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
