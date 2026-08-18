import logging

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from app.services.auth import get_current_user_id
from app.services.file_extraction import extract_text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from app.services.llm import client, kimi_client
from app.db import get_db
from app.models import Class, Concept, ExamInsight
from fastapi import Form
from app.services.llm import top_k_concepts
from app.services.upload_safety import IMAGE_OR_PDF_EXTENSIONS, read_upload_limited


router = APIRouter(prefix="/performance", tags=["performance"])
logger = logging.getLogger(__name__)


@router.post("/analyze-exam")
async def analyze_exam(
    class_id: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):

    # -------- VALIDATE CLASS ID --------
    if not class_id:
        raise HTTPException(400, "class_id required")

    try:
        class_uuid = UUID(class_id)
    except:
        raise HTTPException(400, "Invalid class_id")

    class_res = await db.execute(
        select(Class.id).where(Class.id == class_uuid, Class.user_id == current_user_id)
    )
    if not class_res.scalar_one_or_none():
        raise HTTPException(404, "Class not found")

    filename, content = await read_upload_limited(file, IMAGE_OR_PDF_EXTENSIONS)

    try:
        text = await extract_text(filename, content, math_mode=True)
    except Exception as exc:
        logger.warning("exam_upload_extraction_failed error_type=%s", type(exc).__name__)
        raise HTTPException(400, "The uploaded exam could not be processed") from exc

    if not text or not text.strip():
        raise HTTPException(400, "No text could be extracted from the uploaded exam")
    
    # -------- LOAD CLASS CONCEPTS --------
    res = await db.execute(
        select(Concept).where(
            Concept.class_id == class_uuid,
            Concept.user_id == current_user_id
        )
    )

    concepts = res.scalars().all()
    
    # -------- RAG CONCEPT RETRIEVAL --------
    query = text[:4000]
    missing = sum(1 for c in concepts if c.embedding is None)
    scored_concepts = await top_k_concepts(
        query,
        concepts,
        k=12
    )

    top_concepts = [c for score, c in scored_concepts]
    
    logger.info(
        "exam_analysis_retrieval concepts=%d missing_embeddings=%d matches=%d",
        len(concepts),
        missing,
        len(scored_concepts),
    )
        
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
    ])[:4000]
    
    
    resp = kimi_client.chat.completions.create(
        model="kimi-k2.5",
        messages=[
            {
                "role": "system",
                "content": f"""
                You are an expert actuarial science and mathematics learning coach.

                IMPORTANT: Use the following class concepts when analyzing the exam.

                If the student's mistake relates to one of these concepts,
                you MUST explicitly reference the concept name.
    
                Available concepts:

                {context}

                When diagnosing mistakes:

                • map mistakes to one or more concepts
                • explain which concept was misunderstood
                • explain how the concept should have been applied

                When analyzing the exam:
                • Identify which concepts the student struggled with
                • Refer to concept names when appropriate
                • Explain which concepts were misapplied

The student uploaded a graded exam or assignment.

Your job is NOT just to analyze the exam — your job is to help the student
learn from their mistakes and improve their future exam performance.

Act like a professor carefully reviewing a student's exam after grading.

You must analyze the work deeply and identify patterns in the student's thinking.

------------------------------------------------

YOUR OBJECTIVES

1. Identify mistakes in the student's solutions
2. Identify the concepts the student struggles with
3. Detect patterns across mistakes
4. Diagnose WHY those mistakes occur
5. Estimate the student's current mastery level
6. Provide specific guidance on how the student should improve
7. Predict their likely score on the next exam if they continue with their current study habits

------------------------------------------------

IMPORTANT RULES

• Focus on reasoning mistakes, not just wrong answers
• Look for conceptual misunderstandings
• Look for recurring mistakes across problems
• Explain WHY mistakes occur
• Provide actionable improvement advice
• Focus on patterns of mistakes rather than listing every single incorrect answer.

Do NOT just summarize the exam.

You must act like a tutor who wants the student to improve.

------------------------------------------------

PERSONALIZATION REQUIREMENT

All recommendations must be derived directly from the student's detected mistake patterns.

Do NOT give generic study advice.

Each recommendation must clearly connect to:

• a specific mistake pattern
• a specific weak concept
• a specific exam behavior

Every strategy must explain WHY it will improve the student's score.

--------------------------------------------------


STRUCTURE YOUR RESPONSE EXACTLY USING THESE SECTIONS

## Overall Performance

Briefly summarize how the student performed overall.

Example:
• Strong conceptual understanding but calculation errors
• Good structure but weak formula selection
• Major conceptual misunderstanding

------------------------------------------------

## Mistakes Found

List the mistakes detected in the exam.

For each mistake include:

• what the student did
• why it is incorrect
• what the correct reasoning should be

Focus on the *thinking error* behind the mistake.

------------------------------------------------

## Weak Concepts

Identify the key concepts the student struggles with.

Examples:

• interest rate conversion
• annuity formulas
• timeline construction
• probability distributions
• expected value reasoning

Explain briefly what each concept means.

------------------------------------------------

## Mistake Patterns

Look for repeated patterns in the student's mistakes.

Examples:

• calculation mistakes
• incorrect interest conversions
• misunderstanding problem structure
• skipping timelines
• choosing the wrong formula

Explain what habit or misunderstanding is causing these patterns.

------------------------------------------------

## Why These Mistakes Happen

Explain the underlying thinking errors.

For example:

Students often make these mistakes because:

• they rush calculations
• they skip structural steps like timelines
• they memorize formulas without understanding when to use them

Help the student understand what mental habits caused these mistakes.

------------------------------------------------

## How To Improve

Give very concrete improvement advice.

Examples:

• Always draw a timeline before solving annuity problems
• Convert nominal interest rates before using formulas
• Write down the number of periods before calculating present value
• Double check formulas before substituting numbers

Focus on methods that improve exam performance.

------------------------------------------------

## Targeted Practice Plan

Suggest a short study plan to fix the weaknesses.

Example:

Practice Set:
• 5 interest conversion problems
• 5 annuity timeline problems
• 3 expected value problems

Explain briefly what the student should focus on while practicing.

------------------------------------------------

## Predicted Next Exam Score

Estimate the student's likely score range if their current study habits remain unchanged.

Then estimate how specific improvement strategies would affect their score.

IMPORTANT:

The strategies must be derived directly from the student's mistake patterns and weak concepts identified earlier.

Each improvement strategy should include:

• the specific issue it fixes
• why that issue affects exam performance
• an estimated score improvement if corrected

Structure the response like this:

Current trajectory (if study habits stay the same):
Example: 65–72

Potential improvement strategies and expected impact:

Strategy 1
Fix: [specific mistake pattern]

Example:
Fix: incorrect interest rate conversion

Why it matters:
Incorrect rate conversions cause entire problems to be wrong even when the method is correct.

Estimated impact:
+6 to +10 points

Strategy 2
Fix: [specific structural mistake]

Example:
Fix: not drawing timelines before solving annuity problems

Why it matters:
Without a timeline students misplace payments and use the wrong formula.

Estimated impact:
+4 to +8 points

Strategy 3
Fix: [specific conceptual weakness]

Explain why improving this concept would increase exam performance.

Estimated impact:
+3 to +7 points

After listing strategies, estimate the improved score range if the student follows the recommendations.

Example:

If these strategies are applied consistently:

Expected next exam score:
80–90

------------------------------------------------

CLARITY RULES

• Use short explanations
• Use bullet points when helpful
• Avoid long paragraphs
• Focus on teaching

------------------------------------------------

MATH FORMATTING

Use LaTeX when showing formulas.

Inline math: $...$

Equations: $$...$$
"""
            },
            {
                "role": "user",
                "content": text
            }
        ],
        
    )

    analysis_text = resp.choices[0].message.content

    insight = ExamInsight(
        user_id=current_user_id,
        class_id=class_uuid,
        filename=filename,
        extracted_text=text,
        analysis=analysis_text
    )

    db.add(insight)
    await db.commit()

    return {
        "analysis": analysis_text
    }

@router.get("/insights/{class_id}")
async def get_exam_insights(
    class_id: str,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):

    try:
        class_uuid = UUID(class_id)
    except:
        raise HTTPException(400, "Invalid class_id")

    class_res = await db.execute(
        select(Class.id).where(Class.id == class_uuid, Class.user_id == current_user_id)
    )
    if not class_res.scalar_one_or_none():
        raise HTTPException(404, "Class not found")

    res = await db.execute(
        select(ExamInsight)
        .where(
            ExamInsight.user_id == current_user_id,
            ExamInsight.class_id == class_uuid
        )
        .order_by(ExamInsight.created_at.desc())
    )

    rows = res.scalars().all()

    return [
        {
            "id": str(r.id),
            "filename": r.filename,
            "analysis": r.analysis,
            "created_at": r.created_at
        }
        for r in rows
    ]
