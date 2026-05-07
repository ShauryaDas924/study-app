from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, time as dt_time, timezone, timedelta
from uuid import UUID

from app.services.file_extraction import extract_text
from app.services.llm import openai_chat_create, safe_json_loads


MIN_SYLLABUS_CHARS = 30
SHORT_SYLLABUS_CHARS = 240
MAX_PARSE_CHARS = 16000
MAX_PLAN_DAYS = 60

VALID_INTENSITIES = {"light", "balanced", "aggressive"}
VALID_TASK_TYPES = {"review", "practice", "flashcards", "mixed", "mock_exam"}
VALID_TASK_STATUSES = {"pending", "done", "skipped"}

STOPWORDS = {
    "and",
    "are",
    "chapter",
    "class",
    "course",
    "date",
    "due",
    "exam",
    "final",
    "for",
    "from",
    "introduction",
    "lecture",
    "lesson",
    "midterm",
    "module",
    "of",
    "on",
    "quiz",
    "review",
    "section",
    "syllabus",
    "test",
    "the",
    "to",
    "topic",
    "unit",
    "week",
    "with",
}


SYLLABUS_PARSE_PROMPT = """
You parse course syllabi for an evidence-based study planner.

Return JSON only. Do not include markdown.

Important:
- Extract only information supported by the syllabus text.
- Do not claim certainty about instructor assessments.
- Evidence quotes must be exact short spans from the syllabus text.
- If evidence is weak or missing, add a warning.

Schema:
{
  "course_title": string|null,
  "instructor": string|null,
  "exam_dates": [
    {
      "title": string,
      "date_text": string|null,
      "scope_text": string|null,
      "evidence_quote": string|null
    }
  ],
  "schedule_topics": [
    {
      "date_text": string|null,
      "topic": string,
      "chapter": string|null,
      "evidence_quote": string|null
    }
  ],
  "explicit_scope_statements": [
    {
      "text": string,
      "evidence_quote": string
    }
  ],
  "warnings": string[]
}
"""


@dataclass
class TopicCandidate:
    topic_name: str
    source: str
    evidence_quote: str | None = None
    date_text: str | None = None
    scope_text: str | None = None


def clip_text(value, max_chars: int = 420) -> str:
    text = str(value or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def tokenize(value: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", str(value or "").lower())
    return {w for w in words if len(w) > 2 and w not in STOPWORDS}


def normalize_key(value: str) -> str:
    return " ".join(sorted(tokenize(value)))


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def parse_exam_datetime(exam_date_iso: str) -> datetime:
    try:
        value = exam_date_iso.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(value)
    except Exception as exc:
        raise ValueError("Invalid exam_date_iso") from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def parsed_summary(parsed_json: dict, warnings: list[str] | None = None) -> dict:
    parsed_warnings = list(parsed_json.get("warnings") or [])
    for warning in warnings or []:
        if warning and warning not in parsed_warnings:
            parsed_warnings.append(warning)

    return {
        "course_title": parsed_json.get("course_title"),
        "instructor": parsed_json.get("instructor"),
        "exam_dates": (parsed_json.get("exam_dates") or [])[:5],
        "schedule_topics_count": len(parsed_json.get("schedule_topics") or []),
        "explicit_scope_count": len(parsed_json.get("explicit_scope_statements") or []),
        "warnings": parsed_warnings,
    }


async def extract_syllabus_text(filename: str, file_bytes: bytes) -> tuple[str, list[str]]:
    start = time.perf_counter()
    warnings: list[str] = []
    lower = (filename or "").lower()

    if lower.endswith((".txt", ".md")):
        try:
            raw_text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            raw_text = file_bytes.decode("latin-1", errors="ignore")
    elif lower.endswith((".pdf", ".png", ".jpg", ".jpeg", ".ppt", ".pptx")):
        raw_text = await extract_text(filename, file_bytes)
    elif lower.endswith(".docx"):
        raise ValueError("DOCX syllabus upload is not supported yet. Please export the syllabus as PDF or TXT.")
    else:
        raise ValueError("Unsupported syllabus file type. Please upload a PDF or TXT file.")

    raw_text = str(raw_text or "").replace("\r\n", "\n").replace("\r", "\n").replace("\u0000", "")
    raw_text = re.sub(r"[ \t]+", " ", raw_text)
    raw_text = re.sub(r"\n{3,}", "\n\n", raw_text).strip()

    if not raw_text or raw_text.lower() == "unsupported file type":
        raise ValueError("No syllabus text could be extracted from this file.")

    if len(raw_text.strip()) < MIN_SYLLABUS_CHARS:
        raise ValueError("The extracted syllabus text is too short to analyze.")

    if len(raw_text.strip()) < SHORT_SYLLABUS_CHARS:
        warnings.append("The extracted syllabus text is very short, so confidence may be low.")

    elapsed = time.perf_counter() - start
    print(
        "[exam_prep] syllabus_extraction",
        {"filename": filename, "chars": len(raw_text), "elapsed_sec": round(elapsed, 2)},
    )
    return raw_text, warnings


def fallback_parse_syllabus(raw_text: str, warning: str | None = None) -> dict:
    lines = [normalize_space(line) for line in raw_text.splitlines()]
    if len(lines) <= 1:
        lines = re.split(r"(?<=[.;])\s+", raw_text)
    lines = [line for line in lines if 5 <= len(line) <= 220]

    exam_dates = []
    schedule_topics = []
    scope_statements = []

    for line in lines[:350]:
        low = line.lower()
        has_exam_word = any(word in low for word in ["exam", "midterm", "final", "test", "quiz"])
        has_topic_word = any(word in low for word in ["week", "chapter", "unit", "module", "topic", "lecture"])

        if has_exam_word and len(exam_dates) < 8:
            exam_dates.append(
                {
                    "title": clip_text(line, 80),
                    "date_text": None,
                    "scope_text": None,
                    "evidence_quote": clip_text(line, 180),
                }
            )
            scope_statements.append({"text": clip_text(line, 180), "evidence_quote": clip_text(line, 180)})
            continue

        if has_topic_word and len(schedule_topics) < 40:
            schedule_topics.append(
                {
                    "date_text": None,
                    "topic": clip_text(line, 120),
                    "chapter": None,
                    "evidence_quote": clip_text(line, 180),
                }
            )

    if not schedule_topics:
        for line in lines[:18]:
            if len(schedule_topics) >= 12:
                break
            schedule_topics.append(
                {
                    "date_text": None,
                    "topic": clip_text(line, 120),
                    "chapter": None,
                    "evidence_quote": clip_text(line, 180),
                }
            )

    warnings = ["Syllabus parsing used a fallback parser; evidence may be less structured."]
    if warning:
        warnings.append(warning)

    return {
        "course_title": None,
        "instructor": None,
        "exam_dates": exam_dates,
        "schedule_topics": schedule_topics,
        "explicit_scope_statements": scope_statements[:12],
        "warnings": warnings,
    }


def quote_in_text(quote: str | None, raw_text: str) -> bool:
    if not quote:
        return False
    quote_norm = normalize_space(quote).lower()
    raw_norm = normalize_space(raw_text).lower()
    return quote_norm in raw_norm


def validate_evidence_quotes(parsed_json: dict, raw_text: str) -> dict:
    parsed = dict(parsed_json or {})

    for item in parsed.get("exam_dates") or []:
        quote = item.get("evidence_quote")
        if quote and not quote_in_text(quote, raw_text):
            item["inferred_summary"] = quote
            item["evidence_quote"] = None

    for item in parsed.get("schedule_topics") or []:
        quote = item.get("evidence_quote")
        if quote and not quote_in_text(quote, raw_text):
            item["inferred_summary"] = quote
            item["evidence_quote"] = None

    for item in parsed.get("explicit_scope_statements") or []:
        quote = item.get("evidence_quote")
        if quote and not quote_in_text(quote, raw_text):
            item["inferred_summary"] = quote
            item["evidence_quote"] = ""

    return parsed


def ensure_parse_shape(parsed_json: dict) -> dict:
    parsed = parsed_json if isinstance(parsed_json, dict) else {}
    raw_exam_dates = parsed.get("exam_dates") if isinstance(parsed.get("exam_dates"), list) else []
    raw_schedule_topics = parsed.get("schedule_topics") if isinstance(parsed.get("schedule_topics"), list) else []
    raw_scope_statements = (
        parsed.get("explicit_scope_statements")
        if isinstance(parsed.get("explicit_scope_statements"), list)
        else []
    )
    raw_warnings = parsed.get("warnings") if isinstance(parsed.get("warnings"), list) else []

    exam_dates = [item for item in raw_exam_dates if isinstance(item, dict)]
    schedule_topics = [item for item in raw_schedule_topics if isinstance(item, dict)]
    scope_statements = [
        item for item in raw_scope_statements
        if isinstance(item, dict)
    ]
    warnings = [str(item) for item in raw_warnings if item]

    return {
        "course_title": parsed.get("course_title") if isinstance(parsed.get("course_title"), str) else None,
        "instructor": parsed.get("instructor") if isinstance(parsed.get("instructor"), str) else None,
        "exam_dates": exam_dates,
        "schedule_topics": schedule_topics,
        "explicit_scope_statements": scope_statements,
        "warnings": warnings,
    }


async def parse_syllabus(raw_text: str) -> tuple[dict, str, str | None]:
    start = time.perf_counter()
    parse_input = raw_text[:MAX_PARSE_CHARS]

    try:
        resp = await openai_chat_create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": SYLLABUS_PARSE_PROMPT},
                {"role": "user", "content": parse_input},
            ],
            temperature=0.0,
        )
        parsed = safe_json_loads(resp.choices[0].message.content)
        if not parsed:
            raise ValueError("Parser returned invalid JSON.")

        parsed = validate_evidence_quotes(ensure_parse_shape(parsed), raw_text)
        status = "completed"
        error = None
    except Exception as exc:
        parsed = fallback_parse_syllabus(raw_text, str(exc))
        status = "fallback"
        error = str(exc)

    elapsed = time.perf_counter() - start
    print(
        "[exam_prep] syllabus_parse",
        {
            "status": status,
            "topics": len(parsed.get("schedule_topics") or []),
            "exam_dates": len(parsed.get("exam_dates") or []),
            "elapsed_sec": round(elapsed, 2),
        },
    )
    return parsed, status, error


def topic_from_scope_text(text: str) -> str:
    text = normalize_space(text)
    text = re.sub(r"^(exam|midterm|final|test|quiz)\s*\d*\s*[:,-]?\s*", "", text, flags=re.I)
    return clip_text(text, 120) or "Exam scope"


def collect_topic_candidates(parsed_json: dict, raw_text: str) -> list[TopicCandidate]:
    candidates: list[TopicCandidate] = []

    for item in parsed_json.get("explicit_scope_statements") or []:
        text = item.get("text") or item.get("evidence_quote")
        if text:
            candidates.append(
                TopicCandidate(
                    topic_name=topic_from_scope_text(text),
                    source="explicit_scope",
                    evidence_quote=item.get("evidence_quote") or text,
                    scope_text=text,
                )
            )

    for item in parsed_json.get("exam_dates") or []:
        scope = item.get("scope_text")
        title = item.get("title")
        if scope:
            candidates.append(
                TopicCandidate(
                    topic_name=topic_from_scope_text(scope),
                    source="exam_scope",
                    evidence_quote=item.get("evidence_quote") or scope,
                    date_text=item.get("date_text"),
                    scope_text=scope,
                )
            )
        elif title and item.get("evidence_quote"):
            candidates.append(
                TopicCandidate(
                    topic_name=topic_from_scope_text(title),
                    source="exam_date",
                    evidence_quote=item.get("evidence_quote"),
                    date_text=item.get("date_text"),
                )
            )

    for item in parsed_json.get("schedule_topics") or []:
        topic = item.get("topic")
        if topic:
            candidates.append(
                TopicCandidate(
                    topic_name=clip_text(topic, 120),
                    source="schedule_topic",
                    evidence_quote=item.get("evidence_quote") or topic,
                    date_text=item.get("date_text"),
                )
            )

    if not candidates:
        fallback = fallback_parse_syllabus(raw_text)
        for item in fallback.get("schedule_topics") or []:
            candidates.append(
                TopicCandidate(
                    topic_name=item["topic"],
                    source="fallback_topic",
                    evidence_quote=item.get("evidence_quote"),
                )
            )

    deduped: list[TopicCandidate] = []
    seen: set[str] = set()
    source_rank = {"explicit_scope": 0, "exam_scope": 1, "schedule_topic": 2, "exam_date": 3, "fallback_topic": 4}
    candidates.sort(key=lambda c: source_rank.get(c.source, 9))

    for candidate in candidates:
        key = normalize_key(candidate.topic_name)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
        if len(deduped) >= 35:
            break

    return deduped


def concept_blob(concept) -> str:
    return " ".join(
        [
            concept.name or "",
            concept.description or "",
            concept.definition or "",
            concept.when_to_use or "",
            concept.pitfalls or "",
            concept.evidence or "",
            str(getattr(concept, "related_concepts", "") or ""),
        ]
    )


def score_concept_match(candidate: TopicCandidate, concept) -> float:
    topic_text = f"{candidate.topic_name} {candidate.scope_text or ''} {candidate.evidence_quote or ''}"
    topic_tokens = tokenize(topic_text)
    if not topic_tokens:
        return 0.0

    name_text = (concept.name or "").replace("_", " ")
    blob_text = concept_blob(concept)
    name_tokens = tokenize(name_text)
    blob_tokens = tokenize(blob_text)

    overlap = len(topic_tokens & blob_tokens) / max(1, len(topic_tokens))
    name_overlap = len(topic_tokens & name_tokens) / max(1, len(name_tokens or topic_tokens))

    score = 0.55 * overlap + 0.35 * name_overlap

    topic_low = topic_text.lower()
    name_low = name_text.lower()
    if name_low and name_low in topic_low:
        score += 0.35
    if name_low and name_low in blob_text.lower() and any(t in name_tokens for t in topic_tokens):
        score += 0.08

    return clamp(score)


def match_candidate_to_concepts(candidate: TopicCandidate, concepts: list) -> list[dict]:
    scored = []
    for concept in concepts:
        score = score_concept_match(candidate, concept)
        if score >= 0.12:
            scored.append({"score": score, "concept": concept})

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:3]


def evidence_for_candidate(candidate: TopicCandidate, matched: list[dict], mastery_map: dict[UUID, float]) -> list[dict]:
    evidence = []

    if candidate.evidence_quote:
        evidence.append(
            {
                "source": "syllabus",
                "label": candidate.source.replace("_", " "),
                "quote": clip_text(candidate.evidence_quote, 320),
                "concept_id": None,
            }
        )

    for item in matched:
        concept = item["concept"]
        concept_quote = concept.evidence or concept.definition or concept.description
        evidence.append(
            {
                "source": "concept",
                "label": concept.name,
                "quote": clip_text(concept_quote, 320) if concept_quote else None,
                "concept_id": str(concept.id),
            }
        )

        if concept.id in mastery_map:
            mastery = mastery_map[concept.id]
            evidence.append(
                {
                    "source": "mastery",
                    "label": "Current mastery estimate",
                    "quote": f"{round(mastery * 100)}% mastery estimate",
                    "concept_id": str(concept.id),
                }
            )

    if not evidence:
        evidence.append(
            {
                "source": "inference",
                "label": "Fallback syllabus topic",
                "quote": None,
                "concept_id": None,
            }
        )

    return evidence


def score_topic(candidate: TopicCandidate, matched: list[dict], mastery_map: dict[UUID, float], concepts_available: bool) -> dict:
    has_syllabus_evidence = bool(candidate.evidence_quote)
    top_match = matched[0]["score"] if matched else 0.0
    matched_concepts = [item["concept"] for item in matched]
    matched_ids = [str(concept.id) for concept in matched_concepts]

    explicit_scope_signal = 1.0 if candidate.source in {"explicit_scope", "exam_scope"} else 0.35
    syllabus_signal = 1.0 if has_syllabus_evidence else 0.0
    schedule_signal = 0.75 if candidate.source == "schedule_topic" else 0.55
    note_evidence_signal = 1.0 if any((concept.evidence or "").strip() for concept in matched_concepts) else 0.0
    concept_confidence_signal = (
        sum(float(concept.confidence or 0.5) for concept in matched_concepts) / len(matched_concepts)
        if matched_concepts
        else 0.0
    )

    exam_likelihood = (
        0.30 * syllabus_signal
        + 0.20 * explicit_scope_signal
        + 0.20 * top_match
        + 0.10 * schedule_signal
        + 0.10 * note_evidence_signal
        + 0.10 * concept_confidence_signal
    )

    if not has_syllabus_evidence:
        exam_likelihood = min(exam_likelihood, 0.45)
    elif not matched:
        exam_likelihood = min(exam_likelihood, 0.75)

    exam_likelihood = round(clamp(exam_likelihood), 3)

    mastery_values = [mastery_map[concept.id] for concept in matched_concepts if concept.id in mastery_map]
    mastery_known = bool(mastery_values)
    weakness = sum(1.0 - value for value in mastery_values) / len(mastery_values) if mastery_values else None
    low_concept_confidence_signal = 1.0 - concept_confidence_signal if matched_concepts else 0.0

    if weakness is not None:
        student_priority = 0.72 * exam_likelihood + 0.23 * weakness + 0.05 * low_concept_confidence_signal
    else:
        student_priority = exam_likelihood + 0.05 * low_concept_confidence_signal

    student_priority = round(clamp(student_priority), 3)

    if has_syllabus_evidence and top_match >= 0.34 and exam_likelihood >= 0.68:
        confidence = "high"
    elif has_syllabus_evidence or top_match >= 0.24:
        confidence = "medium"
    else:
        confidence = "low"

    missing_data = []
    if not has_syllabus_evidence:
        missing_data.append("No exact syllabus evidence quote was available for this topic.")
    if not concepts_available:
        missing_data.append("No uploaded course concepts were found for this course.")
    elif not matched:
        missing_data.append("No matching course concept was found in uploaded notes.")
    if matched and not mastery_known:
        missing_data.append("No mastery record exists yet for the matched concept.")
    if confidence == "low":
        missing_data.append("Evidence is limited, so this topic should be treated as a cautious estimate.")

    if matched_concepts:
        action = f"Review {matched_concepts[0].name.replace('_', ' ')} and practice one applied question."
    else:
        action = "Review the syllabus topic, then add or upload notes for stronger course grounding."

    scoring_json = {
        "syllabus_signal": syllabus_signal,
        "explicit_scope_signal": explicit_scope_signal,
        "concept_match_signal": round(top_match, 3),
        "schedule_before_exam_signal": schedule_signal,
        "note_evidence_signal": note_evidence_signal,
        "concept_confidence_signal": round(concept_confidence_signal, 3),
        "mastery_weakness_signal": round(weakness, 3) if weakness is not None else None,
    }

    return {
        "topic_name": clip_text(candidate.topic_name, 120),
        "matched_concept_ids": matched_ids,
        "exam_likelihood_score": exam_likelihood,
        "student_priority_score": student_priority,
        "confidence": confidence,
        "evidence": evidence_for_candidate(candidate, matched, mastery_map),
        "missing_data": missing_data,
        "recommended_study_action": action,
        "scoring_json": scoring_json,
    }


def build_topic_predictions(parsed_json: dict, raw_text: str, concepts: list, mastery_map: dict[UUID, float]) -> tuple[list[dict], list[str]]:
    start = time.perf_counter()
    warnings = []
    candidates = collect_topic_candidates(parsed_json, raw_text)

    if not concepts:
        warnings.append("No uploaded course concepts were found, so the plan is based mostly on syllabus evidence.")

    predictions = []
    matched_concept_count = 0
    for candidate in candidates:
        matched = match_candidate_to_concepts(candidate, concepts)
        matched_concept_count += len(matched)
        predictions.append(score_topic(candidate, matched, mastery_map, bool(concepts)))

    predictions.sort(
        key=lambda item: (item["student_priority_score"], item["exam_likelihood_score"]),
        reverse=True,
    )

    elapsed = time.perf_counter() - start
    print(
        "[exam_prep] topic_scoring",
        {
            "concepts_loaded": len(concepts),
            "topics": len(predictions),
            "matched_concepts": matched_concept_count,
            "elapsed_sec": round(elapsed, 2),
        },
    )
    return predictions[:30], warnings


def minutes_for_intensity(available_minutes: int, intensity: str) -> int:
    if intensity == "light":
        return max(10, min(available_minutes, int(available_minutes * 0.8)))
    if intensity == "aggressive":
        return available_minutes
    return available_minutes


def task_count_for_day(minutes: int, days_until_exam: int, intensity: str) -> int:
    if minutes < 30:
        return 1
    if days_until_exam <= 2:
        return 2
    if intensity == "aggressive" and minutes >= 75:
        return 3
    if minutes >= 50:
        return 2
    return 1


def choose_task_type(day_index: int, days_left: int, topic: dict) -> str:
    if days_left <= 2 and day_index == max(0, days_left - 1):
        return "mock_exam"
    if topic.get("matched_concept_ids"):
        return ["review", "practice", "mixed"][day_index % 3]
    return "review"


def build_plan_days(
    exam_date: datetime,
    topics: list[dict],
    available_minutes_per_day: int,
    intensity: str,
) -> tuple[list[dict], list[str], datetime, datetime]:
    start = time.perf_counter()
    warnings: list[str] = []
    now = datetime.now(timezone.utc)
    today = now.date()
    exam_day = exam_date.astimezone(timezone.utc).date()
    days_left = max(1, (exam_day - today).days)

    if days_left <= 2:
        warnings.append("The exam is very soon, so this is a compressed study plan.")

    if available_minutes_per_day < 25:
        warnings.append("Available study time is low, so each day focuses on only the highest-priority work.")

    total_days = min(days_left, MAX_PLAN_DAYS)
    if days_left > MAX_PLAN_DAYS:
        warnings.append(f"The exam is more than {MAX_PLAN_DAYS} days away, so this plan starts with the next {MAX_PLAN_DAYS} days.")

    if not topics:
        topics = [
            {
                "topic_name": "Syllabus review",
                "matched_concept_ids": [],
                "student_priority_score": 0.4,
                "exam_likelihood_score": 0.4,
                "recommended_study_action": "Review the syllabus and add course notes for stronger planning.",
            }
        ]

    daily_minutes = minutes_for_intensity(available_minutes_per_day, intensity)
    plan_days = []
    ranked_topics = sorted(topics, key=lambda item: item["student_priority_score"], reverse=True)

    for day_index in range(total_days):
        day = today + timedelta(days=day_index)
        remaining = daily_minutes
        days_until_exam = max(1, (exam_day - day).days)
        count = task_count_for_day(daily_minutes, days_until_exam, intensity)
        tasks = []

        for task_index in range(count):
            if remaining <= 0:
                break

            topic = ranked_topics[(day_index + task_index) % len(ranked_topics)]
            minutes = max(10, remaining // (count - task_index))
            minutes = min(minutes, remaining)
            task_type = choose_task_type(day_index + task_index, days_left, topic)
            concept_id = topic.get("matched_concept_ids", [None])[0] if topic.get("matched_concept_ids") else None
            topic_name = topic["topic_name"]

            if task_type == "mock_exam":
                title = "Timed mixed review"
                description = "Work through a short mixed set, then mark uncertain steps for review."
            elif task_type == "practice":
                title = f"Practice: {topic_name}"
                description = "Answer applied questions and explain why each method fits."
            elif task_type == "mixed":
                title = f"Review and practice: {topic_name}"
                description = "Start with notes, then do a small practice block."
            else:
                title = f"Review: {topic_name}"
                description = topic.get("recommended_study_action") or "Review course evidence and summarize the key idea."

            tasks.append(
                {
                    "title": title,
                    "description": description,
                    "minutes": minutes,
                    "topic_name": topic_name,
                    "concept_id": concept_id,
                    "task_type": task_type,
                    "topic_prediction_id": topic.get("id"),
                    "rationale": (
                        f"Priority {round(topic.get('student_priority_score', 0) * 100)} based on "
                        "syllabus evidence and available course concepts."
                    ),
                }
            )
            remaining -= minutes

        plan_days.append(
            {
                "date": day.isoformat(),
                "title": "Exam prep focus",
                "tasks": tasks,
            }
        )

    starts_on = datetime.combine(today, dt_time.min, tzinfo=timezone.utc)
    ends_on = datetime.combine(today + timedelta(days=total_days - 1), dt_time.max, tzinfo=timezone.utc)
    elapsed = time.perf_counter() - start
    print(
        "[exam_prep] plan_generation",
        {"days": len(plan_days), "topics": len(topics), "elapsed_sec": round(elapsed, 2)},
    )
    return plan_days, warnings, starts_on, ends_on


def apply_prediction_ids_to_plan(plan_days: list[dict], topics: list[dict]) -> list[dict]:
    by_name = {topic["topic_name"]: topic.get("id") for topic in topics}
    for day in plan_days:
        for task in day.get("tasks") or []:
            task["topic_prediction_id"] = by_name.get(task.get("topic_name"))
    return plan_days


def build_task_rows_from_plan(plan_json: dict) -> list[dict]:
    rows = []
    for day in plan_json.get("plan_days") or []:
        planned_date = datetime.fromisoformat(day["date"]).date()
        planned_for = datetime.combine(planned_date, dt_time(hour=12), tzinfo=timezone.utc)

        for task in day.get("tasks") or []:
            task_type = task.get("task_type") if task.get("task_type") in VALID_TASK_TYPES else "mixed"
            rows.append(
                {
                    "planned_for": planned_for,
                    "task_type": task_type,
                    "title": clip_text(task.get("title") or "Exam prep task", 180),
                    "description": clip_text(task.get("description") or "", 800),
                    "minutes": int(task.get("minutes") or 0),
                    "rationale": clip_text(task.get("rationale") or "", 800),
                    "concept_id": task.get("concept_id"),
                    "exam_topic_prediction_id": task.get("topic_prediction_id"),
                    "source_json": {
                        "topic_name": task.get("topic_name"),
                        "task_type": task_type,
                    },
                }
            )
    return rows
