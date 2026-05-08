from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
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

ACCEPTED_TOPIC_CATEGORIES = {"study_topic", "study_subtopic"}

ASSESSMENT_LABELS = {
    "assessment",
    "comprehensive",
    "comprehensive exam",
    "comprehensive final",
    "cumulative",
    "cumulative exam",
    "cumulative final",
    "exam",
    "final",
    "final exam",
    "midterm",
    "midterm exam",
    "quiz",
    "test",
}

SECTION_HEADER_LABELS = {
    "academic dishonesty",
    "academic integrity",
    "academic support resources",
    "assignment submission",
    "attendance policy",
    "calculator",
    "calculators",
    "class time",
    "classroom",
    "contact information",
    "course and exam policies",
    "course description",
    "course description and objectives",
    "course introduction",
    "course introduction and outline",
    "course objectives",
    "course outline",
    "course policies",
    "exam policies",
    "grade scale",
    "grading",
    "grading scheme",
    "homework submission",
    "important dates",
    "instructor",
    "late missed coursework",
    "late work",
    "learning objectives",
    "meeting time",
    "objectives",
    "office hours",
    "official syllabus policies",
    "posting course material",
    "prerequisites",
    "professor",
    "recommended resources",
    "recommended textbook",
    "required background",
    "required materials",
    "tentative course outline",
    "university policies",
}


SYLLABUS_PARSE_PROMPT = """
You parse course syllabi for an evidence-based study planner.

Return JSON only. Do not include markdown.

Important:
- Extract only information supported by the syllabus text.
- Do not claim certainty about instructor assessments.
- Evidence quotes must be exact short spans from the syllabus text.
- If evidence is weak or missing, add a warning.
- Extract actual academic topics, units, modules, chapters, concepts, course objectives, learning objectives, lecture topics, and subject areas as study_topics.
- Do not include grading weights, policies, instructor/contact details, office hours, classroom logistics, resource boilerplate, exam labels, or generic course description/admin statements as study_topics.
- If a final or midterm is comprehensive or cumulative, mark it in exam_dates/scope metadata. Do not create a study topic called "comprehensive", "cumulative", "final exam", or "midterm".
- Put rejected admin/grading/policy/resource/header lines in ignored_metadata when useful, with reason categories like exam_scope_metadata, exam_date_metadata, grading_metadata, course_admin, course_policy, resource_or_material, section_header, boilerplate, or ambiguous.

Schema:
{
  "course_title": string|null,
  "instructor": string|null,
  "exam_dates": [
    {
      "title": string,
      "date_text": string|null,
      "scope_text": string|null,
      "is_comprehensive": boolean,
      "evidence_quote": string|null
    }
  ],
  "study_topics": [
    {
      "topic": string,
      "section": string|null,
      "chapter": string|null,
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
  "ignored_metadata": [
    {
      "text": string,
      "reason": string
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
    evidence_quotes: list[str] = field(default_factory=list)
    date_text: str | None = None
    scope_text: str | None = None
    section: str | None = None


TOPIC_SECTION_PATTERNS = (
    r"\b(course|tentative|weekly|lecture|class)\s+(outline|schedule)\b",
    r"\bcalendar\s+of\s+topics\b",
    r"\b(topics?|concepts?)\s+(covered|list|schedule|outline)\b",
    r"\b(course|learning)\s+objectives?\b",
    r"\bstudent\s+learning\s+outcomes?\b",
    r"\bmodules?\b",
    r"\bunits?\b",
    r"\bchapters?\b",
    r"\bexam\s+scope\b",
    r"\breading\s+schedule\b",
    r"\brequired\s+readings?\b",
    r"\bassigned\s+chapters?\b",
)

ADMIN_SECTION_PATTERNS = (
    r"\binstructors?\b",
    r"\bprofessors?\b",
    r"\bcontact\b",
    r"\boffice\s+hours?\b",
    r"\bclass(room| time| meeting| location)\b",
    r"\bmeeting\s+(time|location|pattern)\b",
    r"\bprerequisites?\b",
)

POLICY_PATTERNS = (
    r"\bacademic\s+(honesty|dishonesty|integrity)\b",
    r"\baccessibility\b",
    r"\bdisability\b",
    r"\blate\s+(work|policy|submission)\b",
    r"\bmissed\s+(work|exam|quiz|assignment)\b",
    r"\bmake-?up\b",
    r"\b(upload|uploaded|submit|submitted|submission)\b",
    r"\bsubmission\s+policy\b",
    r"\bdeadline\b",
    r"\battendance\s+policy\b",
    r"\b(course|syllabus)\s+polic(?:y|ies)\b",
    r"\b(university|college|department)\s+polic(?:y|ies)\b",
    r"\bpolicies\s+and\s+procedures\b",
    r"\bplagiarism\b",
    r"\bcheating\b",
    r"\btolerated\b",
)

GRADING_PATTERNS = (
    r"\bgrading\b",
    r"\bgrade\s+(breakdown|conversion|scale|scheme|distribution)\b",
    r"\bpoints?\b",
    r"\bpercent(age)?\b",
    r"\bparticipation\b",
    r"\bhomework\b",
    r"\bassignments?\b",
    r"\bquizzes?\b",
)

CONTACT_PATTERNS = (
    r"\bemail\b",
    r"@[a-z0-9.-]+\.[a-z]{2,}",
    r"\bphone\b",
    r"\boffice\b",
    r"\broom\b",
    r"\bclassroom\b",
)

RESOURCE_PATTERNS = (
    r"\btextbooks?\b",
    r"\bmaterials?\b",
    r"\bcalculator\b",
    r"\bsoftware\b",
    r"\bresources?\b",
    r"\btechnology\b",
    r"\bcanvas\b",
    r"\bblackboard\b",
    r"\blearning\s+management\s+system\b",
)

EXAM_LABEL_PATTERNS = (
    r"^\s*(midterm|final|exam|test|quiz)(\s+(exam|test|quiz))?(\s*#?\d+)?\s*(\([^)]*\))?\s*[:,-]?\s*(\d+%|\d+\s*points?)?\s*$",
    r"^\s*(midterm|final|exam|test|quiz)(\s+(exam|test|quiz))?(\s*#?\d+)?\b.*\b(mon|tue|wed|thu|fri|sat|sun|jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\b",
)

LEARNING_OBJECTIVE_START = (
    "analyze",
    "apply",
    "compare",
    "construct",
    "define",
    "describe",
    "design",
    "determine",
    "differentiate",
    "evaluate",
    "explain",
    "identify",
    "interpret",
    "model",
    "prove",
    "recognize",
    "solve",
    "understand",
    "use",
)

SECTION_ONLY_LABELS = SECTION_HEADER_LABELS | {
    "course outline",
    "tentative course outline",
    "weekly schedule",
    "lecture schedule",
    "calendar of topics",
    "topics covered",
    "course topics",
    "course objectives",
    "learning objectives",
    "student learning outcomes",
    "modules",
    "units",
    "chapters",
    "reading schedule",
    "required readings",
    "assigned chapters",
    "exam scope",
    "grading",
    "grading scheme",
    "course policies",
    "policies",
}

GENERIC_TOPIC_WORDS = {
    "application",
    "applications",
    "basic",
    "basics",
    "calculation",
    "calculations",
    "chapter",
    "concept",
    "concepts",
    "fundamental",
    "fundamentals",
    "introduction",
    "intro",
    "module",
    "objective",
    "objectives",
    "overview",
    "principle",
    "principles",
    "unit",
}


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


def normalize_label(value: str | None) -> str:
    text = normalize_space(value or "").lower()
    text = re.sub(r"&", " and ", text)
    text = re.sub(r"[/_\-:;,.()\[\]#]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def singularize_token(token: str) -> str:
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith("s") and not token.endswith("ss") and len(token) > 3:
        return token[:-1]
    return token


def meaningful_topic_tokens(value: str | None) -> set[str]:
    label = normalize_label(value)
    words = re.findall(r"[a-z0-9]+", label)
    tokens = {
        singularize_token(word)
        for word in words
        if len(word) > 2 and word not in STOPWORDS and word not in GENERIC_TOPIC_WORDS
    }
    return tokens


def is_assessment_label(value: str | None) -> bool:
    label = normalize_label(value)
    if not label:
        return False
    if label in ASSESSMENT_LABELS:
        return True
    tokens = set(label.split())
    assessment_tokens = {"assessment", "comprehensive", "cumulative", "exam", "final", "midterm", "quiz", "test"}
    return bool(tokens) and tokens <= assessment_tokens


def is_section_header_label(value: str | None) -> bool:
    label = normalize_label(value)
    if not label:
        return False
    if label in SECTION_ONLY_LABELS:
        return True
    if label.startswith(("course ", "syllabus ", "university ")) and any(
        word in label for word in ["description", "outline", "policy", "policies", "objectives", "introduction"]
    ):
        return True
    return False


def word_count(value: str) -> int:
    return len(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def has_pattern(value: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, value, flags=re.I) for pattern in patterns)


def clean_topic_candidate(text: str | None) -> str | None:
    value = normalize_space(text or "")
    if not value:
        return None

    value = re.sub(r"^[\-\*\u2022\s]+", "", value)
    value = re.sub(r"^\(?[a-z]\)|^\d+[\.)]\s*", "", value, flags=re.I)
    value = re.sub(r"^(course|learning)\s+objectives?\s*[:\-]?\s*", "", value, flags=re.I)
    value = re.sub(r"^(required\s+readings?|assigned\s+chapters?)\s*[:\-]?\s*", "", value, flags=re.I)
    value = re.sub(r"^(topics?|concepts?|objectives?|readings?)\s*(covered|include|includes|:|-)?\s*", "", value, flags=re.I)
    value = re.sub(r"^(week|unit|module|lecture)\s*\d+[a-z]?\s*[:\-]?\s*", "", value, flags=re.I)
    value = re.sub(r"^chapter\s*\d+[a-z]?\s*[:\-]?\s*", "", value, flags=re.I)
    value = re.sub(r"^final\s+exam\s*(covers|will cover|includes?|scope|content)\s*[:\-]?\s*", "", value, flags=re.I)
    value = re.sub(r"^final\s+exam\s*[:\-]\s*", "", value, flags=re.I)
    value = re.sub(r"^comprehensive\s*[:\-]\s*", "", value, flags=re.I)
    value = re.sub(r"^(exam|midterm|test|quiz)\s*(\d+|#\d+)?\s*(covers|will cover|includes?|scope|content)\s*[:\-]?\s*", "", value, flags=re.I)
    value = re.sub(r"^(exam|midterm|test|quiz)\s*(\d+|#\d+)\s*[:\-]\s*", "", value, flags=re.I)
    value = re.sub(r"^(students?|learners?)\s+(will|should|can)\s+(be able to\s+)?", "", value, flags=re.I)
    value = re.sub(r"^(students?|learners?)\s+are\s+expected\s+to\s+", "", value, flags=re.I)
    value = value.strip(" -:;,.()[]")
    value = normalize_space(value)
    return value or None


def classify_syllabus_candidate(text: str | None, source: str = "", section: str | None = None) -> tuple[str, str]:
    raw = normalize_space(text or "")
    candidate = clean_topic_candidate(raw) or ""
    low_raw = raw.lower()
    low = candidate.lower()
    section_low = normalize_space(section or source).lower()
    words = word_count(candidate)

    if not candidate or words == 0:
        return "ambiguous", "empty candidate"

    if is_assessment_label(raw) or is_assessment_label(candidate):
        return "exam_scope_metadata", "assessment label rather than a study topic"

    if is_section_header_label(raw) or is_section_header_label(candidate):
        return "section_header", "section heading without a study topic"

    has_percentage = bool(re.search(r"\b\d{1,3}\s*%", low_raw))
    if has_percentage and (
        has_pattern(low_raw, GRADING_PATTERNS)
        or re.search(r"\b(exams?|midterms?|finals?|tests?|quizzes?|participation)\b", low_raw)
    ):
        return "grading_metadata", "grading or exam weight line"

    if has_pattern(section_low, ADMIN_SECTION_PATTERNS) or has_pattern(low_raw, ADMIN_SECTION_PATTERNS) or has_pattern(low_raw, CONTACT_PATTERNS):
        return "course_admin", "contact or course logistics line"

    if has_pattern(section_low, POLICY_PATTERNS) or has_pattern(low_raw, POLICY_PATTERNS):
        return "course_policy", "policy or submission boilerplate"

    if has_pattern(section_low, RESOURCE_PATTERNS) or (
        has_pattern(low_raw, RESOURCE_PATTERNS)
        and not re.search(r"\b(required\s+readings?|assigned\s+chapters?)\b", section_low)
    ):
        return "resource_or_material", "materials or resource line"

    if has_pattern(section_low, GRADING_PATTERNS) or (
        has_pattern(low_raw, GRADING_PATTERNS)
        and has_percentage
    ):
        return "grading_metadata", "grading line"

    if any(re.search(pattern, low_raw, flags=re.I) for pattern in EXAM_LABEL_PATTERNS):
        return "exam_date_metadata", "exam label rather than an academic topic"

    if re.search(r"\b(final|midterm|exam|test|quiz)\b", low_raw) and re.search(r"\bcomprehensive\b", low_raw):
        return "exam_scope_metadata", "comprehensive exam metadata rather than a topic"

    if re.search(r"\b(comprehensive|cumulative|all material covered|whole course|entire course)\b", low_raw):
        if re.search(r"\b(exam|final|midterm|assessment|covers?|covered)\b", low_raw):
            return "exam_scope_metadata", "comprehensive or cumulative scope metadata"

    if (
        re.search(r"\b(this|the)\s+(class|course)\s+(covers|prepares|aligns)\b", low_raw)
        and re.search(r"\b(exam|certification|licensure|board|standardized)\b", low_raw)
    ):
        return "boilerplate", "generic external exam coverage statement"

    if re.search(r"^\s*(this|the)\s+(class|course)\s+(covers|introduces|prepares|aligns)\b", low_raw):
        return "ambiguous", "broad course description statement"

    if re.search(r"^\s*the\s+purpose\s+of\s+this\s+course\s+is\b", low_raw):
        return "ambiguous", "broad course purpose statement"

    if re.search(r"^\s*students?\s+are\s+expected\s+to\b", low_raw):
        after_prefix = re.sub(r"^\s*students?\s+are\s+expected\s+to\s+", "", low_raw)
        first_word = after_prefix.split(" ", 1)[0] if after_prefix else ""
        if first_word not in LEARNING_OBJECTIVE_START:
            return "boilerplate", "student expectation boilerplate"

    if re.search(r"\b(class|meeting)\s+time\b", low_raw) or re.search(r"\b(mon|tue|wed|thu|fri)\b.*\b(am|pm)\b", low_raw):
        return "course_admin", "date or meeting-time logistics"

    if re.search(r"\b(final|midterm|exam|test|quiz)\b", low) and words <= 5:
        return "exam_date_metadata", "exam label rather than an academic topic"

    preferred_section = has_pattern(section_low, TOPIC_SECTION_PATTERNS)
    preferred_source = source in {"study_topic", "schedule_topic", "explicit_scope", "exam_scope", "fallback_topic"}
    starts_with_objective = low.split(" ", 1)[0] in LEARNING_OBJECTIVE_START
    has_topic_marker = re.search(r"\b(chapter|unit|module|lecture|topic)\s+\d+\b", low_raw)
    has_sentence_punctuation = bool(re.search(r"[.!?]", candidate))

    if words > 22 and not starts_with_objective:
        return "ambiguous", "too long and sentence-like for a study topic"

    if has_sentence_punctuation and words > 14 and not starts_with_objective:
        return "ambiguous", "sentence-like statement without a clear objective"

    if preferred_section or preferred_source or starts_with_objective or has_topic_marker:
        return "study_topic", "topic section or learning objective"

    if 1 <= words <= 12 and not re.search(r"\b(please|must|should|deadline|required|office|email)\b", low):
        return "study_topic", "concise academic-topic candidate"

    return "ambiguous", "ambiguous syllabus line"


def is_probable_study_topic(text: str | None, source: str = "", section: str | None = None) -> bool:
    category, _reason = classify_syllabus_candidate(text, source=source, section=section)
    return category in ACCEPTED_TOPIC_CATEGORIES


def split_topic_fragments(text: str | None) -> list[str]:
    value = normalize_space(text or "")
    value = re.sub(r"^final\s+exam\s*(covers|will cover|includes?|scope|content)\s*[:\-]?\s*", "", value, flags=re.I)
    value = re.sub(r"^final\s+exam\s*[:\-]\s*", "", value, flags=re.I)
    value = re.sub(r"^comprehensive\s*[:\-]\s*", "", value, flags=re.I)
    value = re.sub(r"^(exam|midterm|test|quiz)\s*(\d+|#\d+)?\s*(covers|will cover|includes?|scope|content)\s*[:\-]?\s*", "", value, flags=re.I)
    value = re.sub(r"^(exam|midterm|test|quiz)\s*(\d+|#\d+)\s*[:\-]\s*", "", value, flags=re.I)
    value = re.sub(r"^(topics?|concepts?)\s+(include|covered)\s*[:\-]\s*", "", value, flags=re.I)
    parts = re.split(r"\s*(?:;|\||/|\n)\s*", value)
    cleaned = []
    for part in parts:
        topic = clean_topic_candidate(part)
        if topic:
            cleaned.append(topic)
    return cleaned or ([clean_topic_candidate(value)] if clean_topic_candidate(value) else [])


def topic_merge_key(value: str | None) -> str:
    return " ".join(sorted(meaningful_topic_tokens(value)))


def topics_should_merge(left: str | None, right: str | None) -> bool:
    left_tokens = meaningful_topic_tokens(left)
    right_tokens = meaningful_topic_tokens(right)
    if not left_tokens or not right_tokens:
        return False
    if left_tokens == right_tokens:
        return True

    smaller, larger = (left_tokens, right_tokens) if len(left_tokens) <= len(right_tokens) else (right_tokens, left_tokens)
    overlap = len(left_tokens & right_tokens)
    if len(smaller) >= 2 and smaller <= larger:
        return True
    if overlap / max(1, len(smaller)) >= 0.8 and overlap / max(1, len(larger)) >= 0.6:
        return True
    return False


def topic_name_score(value: str | None) -> tuple[int, int, int]:
    text = clean_topic_candidate(value) or ""
    tokens = meaningful_topic_tokens(text)
    generic_count = sum(1 for word in re.findall(r"[a-z0-9]+", normalize_label(text)) if word in GENERIC_TOPIC_WORDS)
    return (generic_count, word_count(text), -len(tokens))


def merge_topic_candidates(existing: TopicCandidate, incoming: TopicCandidate) -> TopicCandidate:
    if topic_name_score(incoming.topic_name) < topic_name_score(existing.topic_name):
        existing.topic_name = incoming.topic_name

    if not existing.evidence_quote and incoming.evidence_quote:
        existing.evidence_quote = incoming.evidence_quote

    for quote in incoming.evidence_quotes or ([incoming.evidence_quote] if incoming.evidence_quote else []):
        if quote and quote not in existing.evidence_quotes:
            existing.evidence_quotes.append(quote)

    if not existing.scope_text and incoming.scope_text:
        existing.scope_text = incoming.scope_text
    if not existing.section and incoming.section:
        existing.section = incoming.section
    return existing


def is_accepted_topic_name(topic_name: str | None) -> bool:
    category, _reason = classify_syllabus_candidate(topic_name, source="final_topic")
    return category in ACCEPTED_TOPIC_CATEGORIES


def filter_accepted_topic_dicts(topics: list[dict]) -> list[dict]:
    accepted = []
    for topic in topics or []:
        if is_accepted_topic_name(topic.get("topic_name")):
            accepted.append(topic)
    return accepted


def accepted_parsed_topic_count(parsed_json: dict) -> int:
    candidates: list[TopicCandidate] = []
    for item in parsed_json.get("study_topics") or []:
        if isinstance(item, dict):
            add_topic_candidate(
                candidates,
                item.get("topic"),
                source="study_topic",
                evidence_quote=item.get("evidence_quote") or item.get("topic"),
                section=item.get("section"),
            )
    for item in parsed_json.get("schedule_topics") or []:
        if isinstance(item, dict):
            add_topic_candidate(
                candidates,
                item.get("topic"),
                source="schedule_topic",
                evidence_quote=item.get("evidence_quote") or item.get("topic"),
                section=item.get("section"),
            )
    return len({topic_merge_key(candidate.topic_name) for candidate in candidates if topic_merge_key(candidate.topic_name)})


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

    accepted_topics_count = accepted_parsed_topic_count(parsed_json)
    return {
        "course_title": parsed_json.get("course_title"),
        "instructor": parsed_json.get("instructor"),
        "exam_dates": (parsed_json.get("exam_dates") or [])[:5],
        "accepted_topics_count": accepted_topics_count,
        "study_topics_count": len(parsed_json.get("study_topics") or []),
        "schedule_topics_count": len(parsed_json.get("schedule_topics") or []),
        "explicit_scope_count": len(parsed_json.get("explicit_scope_statements") or []),
        "ignored_metadata_count": len(parsed_json.get("ignored_metadata") or []),
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
    study_topics = []
    schedule_topics = []
    scope_statements = []
    ignored_metadata = []
    current_section: str | None = None

    for line in lines[:350]:
        low = line.lower()
        if has_pattern(low, TOPIC_SECTION_PATTERNS):
            current_section = line
            if (clean_topic_candidate(line) or "").lower() in SECTION_ONLY_LABELS:
                continue

        category, reason = classify_syllabus_candidate(line, source="fallback", section=current_section)
        has_exam_word = any(word in low for word in ["exam", "midterm", "final", "test", "quiz"])
        has_calendar_hint = bool(
            re.search(r"\b(mon|tue|wed|thu|fri|sat|sun|jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\b", low)
            or re.search(r"\b\d{1,2}/\d{1,2}\b", low)
        )

        if has_exam_word and has_calendar_hint and category != "study_topic" and len(exam_dates) < 8:
            exam_dates.append(
                {
                    "title": clip_text(line, 80),
                    "date_text": None,
                    "scope_text": None,
                    "is_comprehensive": bool(re.search(r"\b(comprehensive|cumulative)\b", low)),
                    "evidence_quote": clip_text(line, 180),
                }
            )
            continue

        if category == "study_topic":
            topic = clean_topic_candidate(line)
            if topic and len(study_topics) < 50:
                target = schedule_topics if re.search(r"\b(week|chapter|unit|module|topic|lecture)\b", low) else study_topics
                target.append(
                    {
                        "date_text": None,
                        "topic": clip_text(topic, 120),
                        "section": current_section,
                        "chapter": None,
                        "evidence_quote": clip_text(line, 180),
                    }
                )
        elif category not in ACCEPTED_TOPIC_CATEGORIES and len(ignored_metadata) < 40:
            ignored_metadata.append({"text": clip_text(line, 180), "reason": reason})

    if not study_topics and not schedule_topics:
        for line in lines[:18]:
            if len(schedule_topics) >= 12:
                break
            if is_probable_study_topic(line, source="fallback"):
                topic = clean_topic_candidate(line)
                if topic:
                    schedule_topics.append(
                        {
                            "date_text": None,
                            "topic": clip_text(topic, 120),
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
        "study_topics": study_topics,
        "schedule_topics": schedule_topics,
        "explicit_scope_statements": scope_statements[:12],
        "ignored_metadata": ignored_metadata,
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

    for item in parsed.get("study_topics") or []:
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

    for item in parsed.get("ignored_metadata") or []:
        quote = item.get("text")
        if quote and not quote_in_text(quote, raw_text):
            item["inferred_summary"] = quote
            item["text"] = ""

    return parsed


def ensure_parse_shape(parsed_json: dict) -> dict:
    parsed = parsed_json if isinstance(parsed_json, dict) else {}
    raw_exam_dates = parsed.get("exam_dates") if isinstance(parsed.get("exam_dates"), list) else []
    raw_study_topics = parsed.get("study_topics") if isinstance(parsed.get("study_topics"), list) else []
    raw_schedule_topics = parsed.get("schedule_topics") if isinstance(parsed.get("schedule_topics"), list) else []
    raw_scope_statements = (
        parsed.get("explicit_scope_statements")
        if isinstance(parsed.get("explicit_scope_statements"), list)
        else []
    )
    raw_ignored_metadata = (
        parsed.get("ignored_metadata")
        if isinstance(parsed.get("ignored_metadata"), list)
        else []
    )
    raw_warnings = parsed.get("warnings") if isinstance(parsed.get("warnings"), list) else []

    exam_dates = []
    for item in raw_exam_dates:
        if not isinstance(item, dict):
            continue
        normalized = dict(item)
        normalized["is_comprehensive"] = bool(normalized.get("is_comprehensive"))
        exam_dates.append(normalized)

    study_topics = [item for item in raw_study_topics if isinstance(item, dict)]
    schedule_topics = [item for item in raw_schedule_topics if isinstance(item, dict)]
    scope_statements = [
        item for item in raw_scope_statements
        if isinstance(item, dict)
    ]
    ignored_metadata = [item for item in raw_ignored_metadata if isinstance(item, dict)]
    warnings = [str(item) for item in raw_warnings if item]

    return {
        "course_title": parsed.get("course_title") if isinstance(parsed.get("course_title"), str) else None,
        "instructor": parsed.get("instructor") if isinstance(parsed.get("instructor"), str) else None,
        "exam_dates": exam_dates,
        "study_topics": study_topics,
        "schedule_topics": schedule_topics,
        "explicit_scope_statements": scope_statements,
        "ignored_metadata": ignored_metadata,
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
            "topics": len(parsed.get("study_topics") or []) + len(parsed.get("schedule_topics") or []),
            "exam_dates": len(parsed.get("exam_dates") or []),
            "ignored_metadata": len(parsed.get("ignored_metadata") or []),
            "elapsed_sec": round(elapsed, 2),
        },
    )
    return parsed, status, error


def exam_item_is_comprehensive(item: dict) -> bool:
    text = " ".join(
        normalize_space(item.get(key) or "")
        for key in ["title", "scope_text", "date_text", "evidence_quote"]
    ).lower()
    return bool(item.get("is_comprehensive")) or bool(
        re.search(r"\b(comprehensive|cumulative|all material covered|whole course|entire course)\b", text)
    )


def add_topic_candidate(
    candidates: list[TopicCandidate],
    topic: str | None,
    source: str,
    evidence_quote: str | None = None,
    date_text: str | None = None,
    scope_text: str | None = None,
    section: str | None = None,
) -> None:
    for fragment in split_topic_fragments(topic):
        if not fragment:
            continue
        category, _reason = classify_syllabus_candidate(fragment, source=source, section=section)
        if category not in ACCEPTED_TOPIC_CATEGORIES:
            continue
        cleaned = clean_topic_candidate(fragment)
        if not cleaned:
            continue
        evidence = clip_text(evidence_quote or topic or fragment, 320)
        candidates.append(
            TopicCandidate(
                topic_name=clip_text(cleaned, 120),
                source=source,
                evidence_quote=evidence,
                evidence_quotes=[evidence] if evidence else [],
                date_text=date_text,
                scope_text=scope_text,
                section=section,
            )
        )


def collect_topic_candidates(parsed_json: dict, raw_text: str) -> tuple[list[TopicCandidate], list[str]]:
    candidates: list[TopicCandidate] = []
    warnings: list[str] = []
    exam_dates = parsed_json.get("exam_dates") or []
    is_comprehensive = any(exam_item_is_comprehensive(item) for item in exam_dates if isinstance(item, dict))

    if is_comprehensive:
        warnings.append("The exam appears comprehensive, so the plan uses all major syllabus topics found.")

    for item in parsed_json.get("study_topics") or []:
        topic = item.get("topic")
        if topic:
            add_topic_candidate(
                candidates,
                topic,
                source="study_topic",
                evidence_quote=item.get("evidence_quote") or topic,
                section=item.get("section"),
            )

    for item in parsed_json.get("explicit_scope_statements") or []:
        text = item.get("text") or item.get("evidence_quote")
        if text:
            add_topic_candidate(
                candidates,
                text,
                source="explicit_scope",
                evidence_quote=item.get("evidence_quote") or text,
                scope_text=text,
            )

    for item in exam_dates:
        scope = item.get("scope_text")
        if scope:
            add_topic_candidate(
                candidates,
                scope,
                source="exam_scope",
                evidence_quote=item.get("evidence_quote") or scope,
                date_text=item.get("date_text"),
                scope_text=scope,
            )

    for item in parsed_json.get("schedule_topics") or []:
        topic = item.get("topic")
        if topic:
            add_topic_candidate(
                candidates,
                topic,
                source="schedule_topic",
                evidence_quote=item.get("evidence_quote") or topic,
                date_text=item.get("date_text"),
                section=item.get("section"),
            )

    if not candidates:
        fallback = fallback_parse_syllabus(raw_text)
        for warning in fallback.get("warnings") or []:
            if warning not in warnings:
                warnings.append(warning)
        for item in fallback.get("schedule_topics") or []:
            add_topic_candidate(
                candidates,
                item.get("topic"),
                source="fallback_topic",
                evidence_quote=item.get("evidence_quote"),
            )
        for item in fallback.get("study_topics") or []:
            add_topic_candidate(
                candidates,
                item.get("topic"),
                source="fallback_topic",
                evidence_quote=item.get("evidence_quote"),
                section=item.get("section"),
            )

    deduped: list[TopicCandidate] = []
    seen: set[str] = set()
    source_rank = {"explicit_scope": 0, "exam_scope": 1, "study_topic": 2, "schedule_topic": 3, "fallback_topic": 4}
    candidates.sort(key=lambda c: source_rank.get(c.source, 9))

    for candidate in candidates:
        if not is_accepted_topic_name(candidate.topic_name):
            continue
        key = topic_merge_key(candidate.topic_name)
        if not key:
            continue

        merged = False
        for existing in deduped:
            if topics_should_merge(existing.topic_name, candidate.topic_name):
                merge_topic_candidates(existing, candidate)
                merged = True
                break
        if merged:
            continue

        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
        if len(deduped) >= 35:
            break

    return deduped, warnings


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

    syllabus_quotes = candidate.evidence_quotes or ([candidate.evidence_quote] if candidate.evidence_quote else [])
    for quote in syllabus_quotes[:3]:
        evidence.append(
            {
                "source": "syllabus",
                "label": candidate.source.replace("_", " "),
                "quote": clip_text(quote, 320),
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
        action = "Review this syllabus topic and upload notes for stronger course grounding."

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
    candidates, candidate_warnings = collect_topic_candidates(parsed_json, raw_text)
    warnings.extend(candidate_warnings)

    if not concepts:
        warnings.append("No uploaded course concepts were found for this course, so the plan is based mostly on syllabus evidence.")

    predictions = []
    matched_concept_count = 0
    for candidate in candidates:
        if not is_accepted_topic_name(candidate.topic_name):
            continue
        matched = match_candidate_to_concepts(candidate, concepts)
        matched_concept_count += len(matched)
        predictions.append(score_topic(candidate, matched, mastery_map, bool(concepts)))

    predictions = filter_accepted_topic_dicts(predictions)
    predictions.sort(
        key=lambda item: (item["student_priority_score"], item["exam_likelihood_score"]),
        reverse=True,
    )

    if len(predictions) < 3:
        warnings.append("Only a few clear study topics were found. Upload notes or a review guide for better planning.")

    elapsed = time.perf_counter() - start
    print(
        "[exam_prep] topic_scoring",
        {
            "concepts_loaded": len(concepts),
            "topics": len(predictions),
            "matched_concepts": matched_concept_count,
            "ignored_metadata": len(parsed_json.get("ignored_metadata") or []),
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
    topics = filter_accepted_topic_dicts(topics)
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

    if len(topics) < 3:
        warnings.append("Only a few clear study topics were found. Upload notes or a review guide for better planning.")

    if not topics:
        topics = [
            {
                "topic_name": "Clarify study topics",
                "matched_concept_ids": [],
                "student_priority_score": 0.4,
                "exam_likelihood_score": 0.4,
                "recommended_study_action": "Review the syllabus outline and upload notes for stronger planning.",
                "is_general_fallback": True,
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

            if topic.get("is_general_fallback"):
                title = "Clarify study topics"
                description = topic.get("recommended_study_action") or "Review the syllabus outline and upload notes."
                task_type = "review"
            elif task_type == "mock_exam":
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
                        "No clear study topics were found yet."
                        if topic.get("is_general_fallback")
                        else f"Priority {round(topic.get('student_priority_score', 0) * 100)} based on "
                        "syllabus evidence and available course concepts."
                    ),
                    "is_general_fallback": bool(topic.get("is_general_fallback")),
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
            topic_name = task.get("topic_name")
            if topic_name and not is_accepted_topic_name(topic_name):
                continue
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
                        "topic_name": topic_name,
                        "task_type": task_type,
                    },
                }
            )
    return rows
