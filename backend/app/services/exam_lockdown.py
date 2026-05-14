from __future__ import annotations

import json

from app.services.exam_prep import clip_text
from app.services.llm import openai_chat_create, safe_json_loads


EXAM_LOCKDOWN_TUTOR_PROMPT = """
You are an Exam Lockdown coach for a study app.

Use the selected uploaded question and source context. Do not invent missing facts.
If source context is insufficient, say what is missing and continue with the safest available setup.
Teach like an exam coach: prioritize pattern recognition, structure, and setup before formulas.
Use class-neutral language unless the material is clearly math-specific.
Do not reveal hidden chain of thought. Give concise, useful reasoning steps.

Return structured markdown with exactly these section headings:

## 0. Pattern Being Used
## 1. Translate the English
## 2. Recognition Clues
## 3. Timeline / Structure First
## 4. Where Are We Standing?
## 5. What Counts?
## 6. Build the Equation Slowly
## 7. Solve
## 8. Why This Is the Same Skeleton
## 9. Common Mistake Alert
## 10. Mini Drill

For non-math classes, adapt the structure:
- pattern/concept
- recognition clues
- conceptual structure
- evidence/reasoning frame
- included/excluded facts
- reasoning steps
- common traps
- mini drill

The Mini Drill should be one easier similar question without its answer.
"""


PITFALL_EXTRACTION_PROMPT = """
Extract exam-prep pitfalls from a student's attempt and tutor feedback.

Return JSON only:
{
  "pitfalls": [
    {
      "category": "timeline_setup_error|wrong_formula|rate_conversion_error|wrong_focal_date|cash_flow_identification_error|algebra_calculator_error|concept_misunderstanding|evidence_reading_error|memorization_gap|careless_error",
      "topic_name": "string or null",
      "tag": "short_snake_case",
      "explanation": "short actionable explanation",
      "evidence": {"quote": "short quote or null"}
    }
  ]
}

Rules:
- Use only the attempt, selected question, and tutor feedback.
- If no real pitfall is visible, return {"pitfalls":[]}.
- Prefer one or two high-quality pitfalls.
"""


async def build_exam_lockdown_tutor_response(
    *,
    plan: dict,
    recommendation: dict,
    question: dict,
    material: dict | None,
    recent_attempts: list[dict] | None = None,
    recent_pitfalls: list[dict] | None = None,
    user_question: str | None = None,
    user_attempt: str | None = None,
) -> str:
    source_ref = question.get("source_ref_json") or {}
    material_context = material or {}
    context = {
        "plan": {
            "exam_title": plan.get("exam_title"),
            "exam_date": plan.get("exam_date"),
            "ranked_topics": [t.get("topic_name") for t in (plan.get("topics") or [])[:8]],
            "warnings": plan.get("warnings") or [],
        },
        "recommendation": {
            "why_selected": recommendation.get("why_selected"),
            "confidence": recommendation.get("confidence"),
            "evidence": recommendation.get("evidence_json") or {},
        },
        "source": {
            "filename": material_context.get("filename"),
            "material_type": material_context.get("material_type"),
            "problem_number": question.get("problem_number") or source_ref.get("problem_number"),
            "page": source_ref.get("page"),
            "source_ref": source_ref,
        },
        "question": {
            "prompt": question.get("prompt_text"),
            "answer": question.get("answer_text"),
            "solution": question.get("solution_text"),
            "topic": question.get("topic_name"),
        },
        "recent_attempts": recent_attempts or [],
        "recent_pitfalls": recent_pitfalls or [],
        "student": {
            "question": user_question,
            "attempt": user_attempt,
        },
    }

    resp = await openai_chat_create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": EXAM_LOCKDOWN_TUTOR_PROMPT},
            {
                "role": "user",
                "content": "Use this JSON context for the exam-coach response:\n"
                + json.dumps(context, indent=2, default=str)[:18000],
            },
        ],
        temperature=0.25,
    )
    return resp.choices[0].message.content


async def extract_exam_lockdown_pitfalls(
    *,
    question: dict,
    user_answer_text: str | None,
    tutor_feedback_json: dict | None,
) -> list[dict]:
    if not user_answer_text and not tutor_feedback_json:
        return []

    payload = {
        "question": {
            "topic_name": question.get("topic_name"),
            "prompt_text": clip_text(question.get("prompt_text"), 2000),
        },
        "user_answer_text": clip_text(user_answer_text, 3000),
        "tutor_feedback_json": tutor_feedback_json or {},
    }

    try:
        resp = await openai_chat_create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": PITFALL_EXTRACTION_PROMPT},
                {"role": "user", "content": json.dumps(payload, indent=2, default=str)},
            ],
            temperature=0.0,
        )
        parsed = safe_json_loads(resp.choices[0].message.content)
        pitfalls = parsed.get("pitfalls") if isinstance(parsed, dict) else []
        if not isinstance(pitfalls, list):
            return []
        return [
            {
                "category": str(item.get("category") or "concept_misunderstanding"),
                "topic_name": item.get("topic_name") or question.get("topic_name"),
                "tag": item.get("tag"),
                "explanation": item.get("explanation"),
                "evidence": item.get("evidence") if isinstance(item.get("evidence"), dict) else {},
            }
            for item in pitfalls
            if isinstance(item, dict) and item.get("category")
        ][:3]
    except Exception:
        return []
