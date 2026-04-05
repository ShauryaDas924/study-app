


import re
import os, json
import pathlib
from openai import OpenAI
import numpy as np

EXAMPLE_QUESTIONS_PATH = pathlib.Path("practice_engine_spec.md")

with open(EXAMPLE_QUESTIONS_PATH) as f:
    EXAMPLE_QUESTIONS = f.read()


NOTES_REFINEMENT_PROMPT = """
You are an expert instructor, learning scientist, and exam strategist.

Your task is to transform raw lecture content into HIGH-PRECISION, EXAM-OPTIMIZED STUDY NOTES.

These notes will be used downstream for:
• concept extraction
• flashcard generation
• practice problem generation
• knowledge graph construction

Therefore, ALL testable knowledge MUST be preserved and clearly structured.

------------------------------------------------
PRIMARY OBJECTIVE
------------------------------------------------

Convert messy lecture input into structured, highly scannable, exam-ready notes
that maximize:
• recall
• conceptual clarity
• problem-solving readiness

------------------------------------------------
MANDATORY CONTENT EXTRACTION
------------------------------------------------

You MUST extract and explicitly structure:

• Definitions (precise, minimal, accurate)
• Key ideas (atomic facts — ONE idea per bullet)
• Relationships between concepts (CRITICAL)
• Comparisons (structured differences between concepts)
• Rules / principles
• Processes / systems / flows
• Conditions / assumptions
• Examples (cleaned but faithful)
• Common pitfalls (student mistakes)
• Exam insights (WHY this is tested)

------------------------------------------------
CRITICAL PRESERVATION RULES
------------------------------------------------

You MUST preserve:

• ALL definitions
• ALL named concepts, frameworks, and systems
• ALL examples that illustrate logic
• ALL comparisons (explicit or implied)
• ALL technical terminology

DO NOT:
• merge multiple concepts into one
• remove “redundant-looking” information (it may be testable)
• simplify away important distinctions

When unsure → KEEP the information

------------------------------------------------
STRUCTURE (STRICT AND REPEATABLE)
------------------------------------------------

For EACH concept, use EXACTLY this format:

### [Concept Name]

Definition
- precise, minimal, accurate

Key Ideas
- one idea per bullet
- no compound bullets

Relationships
- explicitly state connections to other concepts
- e.g. "ERP eliminates data silos across enterprise processes"

Processes / Mechanisms (if applicable)
- step-by-step or system behavior

Formulas (if applicable)
- formula
- variable meanings
- when it applies

Examples
- simplified but logically identical

Common Pitfalls
- what students misunderstand
- typical confusion points

Exam Insight
- WHY professors test this
- what kind of question it appears in

------------------------------------------------
COMPARISON RULE (MANDATORY)
------------------------------------------------

If the input includes contrasting concepts (explicitly OR implicitly),
you MUST create a comparison section:

### Comparison: [Concept A vs Concept B]

- Difference in purpose
- Difference in structure
- Difference in usage
- Key distinguishing features
- Examples

This is REQUIRED for:
• structured vs dynamic processes
• workgroup vs enterprise vs inter-enterprise
• ERP vs MRP
• CRM vs ERP vs EAI

------------------------------------------------
FORMATTING RULES
------------------------------------------------

• NO paragraphs longer than 2 lines
• Bullet = EXACTLY one idea
• Use spacing between sections
• Remove slide artifacts (numbers, headers, noise)
• Preserve terminology EXACTLY as given
• Keep wording concise but precise

------------------------------------------------
EXAM SIGNAL HANDLING
------------------------------------------------

If input contains:
• learning objectives
• review sections
• key points

→ treat EACH bullet as HIGH PRIORITY and preserve individually

------------------------------------------------
QUALITY CONSTRAINTS
------------------------------------------------

• DO NOT invent information
• DO NOT add external knowledge
• DO NOT re-interpret beyond given content
• DO NOT skip edge cases or exceptions

------------------------------------------------
OUTPUT FORMAT
------------------------------------------------

Return JSON ONLY:

{
  "clean_notes": "fully structured, exam-optimized notes"
}
"""

MATH_RECONSTRUCTION_PROMPT = """
You are an expert in actuarial mathematics, financial mathematics, and mathematical notation reconstruction.

Your task is to CLEAN, REPAIR, and RECONSTRUCT corrupted mathematical lecture text into precise, readable, and logically correct notes.

The input may contain:
• OCR errors
• broken equations
• missing symbols
• misordered variables
• fragmented expressions
• duplicated or noisy text

------------------------------------------------
PRIMARY OBJECTIVE
------------------------------------------------

Reconstruct mathematically correct, structured, and readable content
while preserving ALL underlying meaning.

------------------------------------------------
RECONSTRUCTION RULES
------------------------------------------------

1. Rebuild equations into correct mathematical form
2. Infer intended formulas ONLY when strongly implied
3. Preserve ALL variables and relationships
4. Standardize notation using actuarial conventions:

• A(t) = accumulated value
• a(t) = accumulation function
• i = effective interest rate
• d = effective discount rate
• v = discount factor
• PV = present value
• AV = accumulated value

5. Fix spacing, alignment, and structure of equations

------------------------------------------------
FORMULA HANDLING (CRITICAL)
------------------------------------------------

For each formula:

• Write clean equation
• Define ALL variables
• State when it applies

Example format:

Formula
- A(t) = k · a(t)

Where:
- A(t): accumulated value at time t
- k: initial principal
- a(t): accumulation function

------------------------------------------------
RELATIONSHIPS (MANDATORY)
------------------------------------------------

You MUST explicitly reconstruct key relationships such as:

• i, d, v relationships
    i = d / (1 - d)
    v = 1 / (1 + i)
    d = i / (1 + i)

• accumulation vs discount
• PV ↔ AV relationships

------------------------------------------------
STRUCTURE OUTPUT
------------------------------------------------

### [Concept Name]

Definition
- clean and precise

Formulas
- clean equations
- variables defined
- usage context

Relationships
- connections between formulas

Examples
- reconstructed clean example (if present)

Notes
- clarifications or important observations

------------------------------------------------
UNCERTAINTY HANDLING
------------------------------------------------

If a portion is unclear or corrupted:

• DO NOT hallucinate
• mark it clearly:

[uncertain reconstruction]

------------------------------------------------
STRICT CONSTRAINTS
------------------------------------------------

• DO NOT invent formulas
• DO NOT introduce external knowledge
• DO NOT skip messy parts — attempt reconstruction
• DO NOT leave raw corrupted text

------------------------------------------------
OUTPUT FORMAT
------------------------------------------------

Return JSON ONLY:

{
  "clean_math_notes": "fully reconstructed mathematical notes with correct notation"
}
"""


def clean_note_text(text: str) -> str:
    # Remove control chars but keep newlines
    text = re.sub(r"[\u0000-\u0008\u000B-\u001F\u007F-\u009F]", " ", text)

    # Preserve bullets by converting them into line-start markers
    text = text.replace("❖", "\n❖ ")
    text = text.replace("•", "\n• ")
    text = text.replace("►", "\n• ")
    text = text.replace("●", "\n• ")
    text = text.replace("◆", "\n• ")

    # Remove only decorative solid blocks
    text = re.sub(r"[■]+", " ", text)

    # Remove slide labels like "Slide 12"
    text = re.sub(r"\bslide\s*\d+\b", " ", text, flags=re.I)

    # Collapse spaces but preserve lines
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()
    
def cosine_sim(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


async def top_k_concepts(query: str, concepts: list, k=5):

    if not concepts:
        return []

    qemb = client.embeddings.create(
        model="text-embedding-3-small",
        input=query
    ).data[0].embedding

    qvec = np.array(qemb)

    scored = []

    for c in concepts:

        # AUTO-GENERATE embedding if missing
        if c.embedding is None:
            text = f"{c.name} {c.description or ''} {c.definition or ''}"
            c.embedding = embed_text(text)

        cvec = np.array(c.embedding)

        score = cosine_sim(qvec, cvec)
        scored.append((score, c))

    scored.sort(reverse=True, key=lambda x: x[0])

    return scored[:k]
 
from jsonschema import validate, ValidationError
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
kimi_client = OpenAI(
    api_key=os.getenv("MOONSHOT_API_KEY"),
    base_url="https://api.moonshot.ai/v1"
)
def embed_text(text: str):
    resp = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return resp.data[0].embedding
SCHEMA_PATH = pathlib.Path("practice_question_schema.json")

with open(SCHEMA_PATH) as f:
    QUESTION_SCHEMA = json.load(f)
    
def safe_json_loads(s: str):

    if not s:
        return None

    # Remove markdown code blocks like ```json ... ```
    s = s.replace("```json", "")
    s = s.replace("```", "")

    # Remove whitespace
    s = s.strip()

    # Extract the first JSON object if extra text exists
    start = s.find("{")
    end = s.rfind("}")

    if start != -1 and end != -1:
        s = s[start:end+1]

    try:
        return json.loads(s)

    except Exception as e:
        print("\n⚠️ LLM JSON PARSE FAILED")
        print("RAW OUTPUT:\n", s)
        print("ERROR:", e, "\n")
        return None
        
# ================= BOOSTER =================

NAMED_PATTERN = re.compile(
    r"\b([A-Z][a-zA-Z’']+(?:\s+[A-Z][a-zA-Z0-9’']+){0,4}\s+"
    r"(Law|Theorem|Model|Framework|Principle|Theory|Forces|Chain|Advantage))\b"
)

async def refine_notes(note_text: str):

    resp = kimi_client.chat.completions.create(
        model="kimi-k2.5",
        messages=[
            {"role":"system","content":NOTES_REFINEMENT_PROMPT},
            {"role":"user","content":note_text}
        ],
        
    )

    raw = resp.choices[0].message.content

    parsed = safe_json_loads(raw)

    if not parsed:
        return note_text

    return parsed.get("clean_notes", note_text)
    
def booster_add_named_concepts(note_text: str, concepts: list):
    found = set()

    for match in NAMED_PATTERN.findall(note_text):
        full_name = match[0].strip()
        found.add(full_name)

    existing = {c["name"] for c in concepts}

    for term in found:

        # ✅ NEW FILTER
        if len(term.split()) > 6:
            continue

        snake = term.lower().replace(" ", "_")

        if snake not in existing:
            concepts.append({
                "name": snake,
                "description": term,
                "confidence": 0.75
            })

    return concepts
    
    
FORMULA_PATTERN = re.compile(
    r"(=|Σ|∑|μ|σ|β|θ|λ|δ|∫|ln|log|\bP\(|\bE\[|\bVar|\bCov)"
)

OBJECTIVE_LINE_PATTERN = re.compile(
    r"^\s*[•\-❖]\s*(what|how|why|when|which)\b.*",
    re.I
)

COMPARISON_PATTERN = re.compile(
    r"\b(.+?)\s+vs\.?\s+(.+?)\b",
    re.I
)

def booster_add_comparisons(note_text: str, concepts: list):
    existing = {c["name"] for c in concepts}

    for match in COMPARISON_PATTERN.findall(note_text):
        left = match[0].strip()
        right = match[1].strip()

        if len(left) > 40 or len(right) > 40:
            continue

        snake = (
            f"{left}_vs_{right}"
            .lower()
            .replace(" ", "_")
            .replace(".", "")
            .replace("/", "_")
        )[:80]

        if snake not in existing:
            concepts.append({
                "name": snake,
                "description": f"Comparison between {left} and {right}",
                "evidence": f"{left} vs {right}",
                "confidence": 0.78,
                "exam_priority_locked": True
            })

    return concepts

def booster_add_objective_concepts(note_text: str, concepts: list):
    lines = note_text.split("\n")
    existing = {c["name"] for c in concepts}

    for line in lines:
        clean = line.strip()
        if not clean:
            continue

        if OBJECTIVE_LINE_PATTERN.search(clean):
            base = re.sub(r"^[•\-❖]\s*", "", clean).strip()
            snake = (
                base.lower()
                .replace("?", "")
                .replace(",", "")
                .replace(" ", "_")
            )[:80]

            if snake not in existing:
                concepts.append({
                    "name": snake,
                    "description": base,
                    "evidence": clean,
                    "confidence": 0.82,
                    "exam_priority_locked": True
                })

    return concepts


# ========= ACRONYM BOOSTER =========

ACRONYM_PATTERN = re.compile(r"\b[A-Z]{2,6}\b")

def booster_add_acronyms(note_text: str, concepts: list):
    found = set(ACRONYM_PATTERN.findall(note_text))
    existing = {c["name"] for c in concepts}

    for term in found:
        snake = term.lower()

        # avoid junk like AND, THE, FOR
        STOP_ACRONYMS = {
            "AND","THE","FOR","WITH","FROM","THIS",
            "YOU","HW","LEC","PDF","ISBN"
        }

        if term in STOP_ACRONYMS:
            continue

        # Only keep if repeated
        if note_text.count(term) < 2:
            continue

        if snake not in existing:
            concepts.append({
                "name": snake,
                "description": f"Acronym mentioned in notes: {term}",
                "confidence": 0.6
            })

    return concepts
    
# ========= REVIEW BOOSTER =========

REVIEW_PATTERN = re.compile(
    r"(review|summary|key points|objectives|takeaways)",
    re.I
)

def booster_review_sections(note_text: str, concepts: list):
    if not REVIEW_PATTERN.search(note_text):
        return concepts

    for c in concepts:
        c["confidence"] = max(c.get("confidence",0), 0.7)

    return concepts

def booster_add_formula_concepts(note_text: str, concepts: list):
    lines = note_text.split("\n")

    existing = {c["name"] for c in concepts}

    for line in lines:
        if FORMULA_PATTERN.search(line) and len(line.split()) <= 12:
            clean = line.strip()

            if len(clean) < 5:
                continue

            name = clean[:60]

            snake = (
                name.lower()
                .replace(" ", "_")
                .replace("=", "")
                .replace("(", "")
                .replace(")", "")
            )

            if snake not in existing:
                concepts.append({
                    "name": snake[:60],
                    "description": f"Formula or symbolic expression: {clean}",
                    "confidence": 0.65
                })

    return concepts

MATH_SYMBOL_PATTERN = re.compile(
    r"(=|∫|Σ|∑|Γ\(|Beta|Gamma|χ|P\[|E\[|Var|Cov|→|⇒)"
)

def booster_math_formulas(note_text: str, concepts: list):
    lines = note_text.split("\n")
    existing = {c["name"] for c in concepts}

    for line in lines:
        if MATH_SYMBOL_PATTERN.search(line):
            clean = line.strip()
            if len(clean) < 5:
                continue

            name = clean[:80]
            snake = (
                name.lower()
                .replace(" ", "_")
                .replace("(", "")
                .replace(")", "")
                .replace("=", "")
            )

            if snake not in existing:
                concepts.append({
                    "name": snake[:80],
                    "description": f"Mathematical formula or identity: {clean}",
                    "confidence": 0.75
                })

    return concepts

DISTRIBUTION_PATTERN = re.compile(
    r"\b(Gamma|Beta|Normal|Exponential|Chi-?Squared|Poisson|Binomial)\b",
    re.I
)

def booster_distributions(note_text: str, concepts: list):
    found = set(DISTRIBUTION_PATTERN.findall(note_text))
    existing = {c["name"] for c in concepts}

    for term in found:
        snake = normalize_concept_name(term.lower())

        if snake not in existing:
            concepts.append({
                "name": snake,
                "description": f"Named probability distribution: {term}",
                "confidence": 0.85
            })

    return concepts
    
    
IDENTITY_PATTERN = re.compile(
    r"[a-zA-Zδλσμ]+\s*=\s*[^\n]{3,50}"
)

def booster_math_identities(note_text: str, concepts: list):

    found = IDENTITY_PATTERN.findall(note_text)

    existing = {c["name"] for c in concepts}

    for expr in found:

        clean = expr.strip()

        snake = (
            clean.lower()
            .replace(" ", "_")
            .replace("(", "")
            .replace(")", "")
        )

        if snake not in existing:

            concepts.append({
                "name": snake[:60],
                "description": f"Mathematical identity: {clean}",
                "confidence": 0.8
            })

    return concepts
    
    
DERIVATION_PATTERN = re.compile(
    r"(E\[.*?\]|Var\(.*?\)|Cov\(.*?\)|f_?\{?[A-Za-z]+\+?[A-Za-z]*\}?\(.*?\))\s*=\s*[^\n]{3,80}"
)

def booster_math_derivations(note_text: str, concepts: list):

    lines = note_text.split("\n")
    existing = {c["name"] for c in concepts}

    for line in lines:

        if DERIVATION_PATTERN.search(line):

            clean = line.strip()

            if len(clean) < 6:
                continue

            snake = (
                clean.lower()
                .replace(" ", "_")
                .replace("(", "")
                .replace(")", "")
                .replace("[", "")
                .replace("]", "")
            )

            if snake not in existing:

                concepts.append({
                    "name": snake[:80],
                    "description": f"Mathematical derivation or identity: {clean}",
                    "confidence": 0.85
                })

    return concepts

def batch_list(items, size=18):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def chunk_text_by_lines(text: str, max_lines: int = 70):
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    chunks = []
    current = []

    for line in lines:
        current.append(line)
        if len(current) >= max_lines:
            chunks.append("\n".join(current))
            current = []

    if current:
        chunks.append("\n".join(current))

    return chunks

CONCEPT_PROMPT = """
You are an expert educator building an EXAM-FOCUSED concept list.

GOAL:
Extract ALL concepts that could reasonably appear on an exam.

Assume the text comes from lecture slides, textbooks, or exam prep.

A concept can be ANY testable knowledge unit, including:

- definitions or vocabulary terms  
- rules, frameworks, or models, or laws
- formulas or equations
- what each variable in a formula represents   
- the conditions under which a formula or rule applies  
- methods or problem-solving techniques  
- processes or step-by-step procedures  
- comparisons or distinctions  
- cause-effect relationships  
- derivations or logical results  
- assumptions behind methods  
- edge cases or limitations  
- common student mistakes
- interpretations of results
- something usable in an applied scenario question  
If unsure, INCLUDE rather than exclude.
IMPORTANT:
Do NOT filter too aggressively.
If a term or idea looks testable, include it.

It is better to include more relevant concepts than miss testable ones.
Always include concepts from slides containing the words: review, summary, objectives, key points
Use these EXAM SIGNALS:
- headings and subheadings  
- bolded or emphasized terms  
- bullet lists  
- repeated terminology  
- formulas or equations  
- definitions introduced with "is" or "refers to"  
- worked examples  
- example problems
- summary or review sections  

SPECIAL PRIORITY:
Always include:
- named laws  
- named principles  
- named theorems  
- named models  
- named frameworks
- summary or review sections   

CRITICAL:
If a slide appears to be:
- learning objectives
- review
- summary
- key takeaways

Extract each bullet as a separate concept.
Assign confidence ≥ 0.7.

(e.g., Bayes' Theorem, Central Limit Theorem, CAPM, Metcalfe's Law)

Even if mentioned only once.
These are highly testable and frequently appear on exams.
If a named law, theorem, or model appears,
assign confidence ≥ 0.7 unless clearly minor.

QUALITY RULES:
- Return 25–80 concepts if available  
- Cover ALL major sections of the text  
- Include both major and supporting concepts  
- Each concept must be concrete and testable  
- Avoid vague phrases like "important idea"  
- Avoid overly broad topics like "technology" or "science"  


STRICT FILTERING RULES:
- Ignore page numbers, headers, footers
- Ignore slide titles like "Lecture 3"
- Ignore decorative text
- Ignore incomplete fragments
- Ignore symbols without context
- Ignore formatting artifacts


GOOD CONCEPT TEST:
A good concept is something a professor could:
- write a multiple-choice question about  
- ask students to apply in a scenario  
- base a problem-solving question on  
- use to test misunderstandings  

Confidence guidelines:
0.9–1.0 = core exam topic  
0.6–0.8 = likely testable  
0.3–0.5 = supporting/testable  
<0.3 = minor mention  

Return JSON ONLY:

{
  "concepts":[
    {
      "name":"snake_case_name",
      "description":"clear one-sentence explanation",
      "evidence":"exact phrase or sentence copied from the text",
      "confidence":0.0
    }
  ]
}

CRITICAL RULE:

Every concept MUST include an "evidence" field.

Evidence must be copied EXACTLY from the notes.

If you cannot find supporting text,
DO NOT include the concept.
"""

PITFALL_PROMPT = """
You are an expert instructor, exam designer, and cognitive error analyst.

Your task:
Extract ONLY **real, text-grounded student mistakes and misconceptions** from the notes.

------------------------------------------------
PRIMARY OBJECTIVE
------------------------------------------------

Identify mistakes that:
• students commonly make
• would lead to wrong answers on exams
• reflect misunderstanding of concepts, formulas, or conditions

------------------------------------------------
STRICT GROUNDING RULE
------------------------------------------------

You MUST ONLY extract pitfalls that are:

• explicitly stated
OR
• strongly implied by:
  - examples
  - contrasts
  - warnings
  - edge cases
  - conditions
  - incorrect vs correct reasoning

If you cannot find textual support → DO NOT include it.

------------------------------------------------
WHAT COUNTS AS A PITFALL
------------------------------------------------

Valid pitfalls include:

• misapplying a formula
• using a method in the wrong context
• misunderstanding a definition
• confusing similar concepts
• ignoring conditions or assumptions
• sign errors / variable misuse
• incorrect interpretation of results

------------------------------------------------
WHAT TO IGNORE
------------------------------------------------

DO NOT include:

• vague advice
• generic study tips
• invented mistakes
• anything not grounded in text

------------------------------------------------
LINKING RULE (CRITICAL)
------------------------------------------------

Each pitfall MUST be tied to a specific concept.

Use the SAME naming style as concept extraction:
snake_case

------------------------------------------------
QUALITY RULES
------------------------------------------------

• Each pitfall must be concrete and testable
• Keep descriptions short and precise (1–2 lines)
• Prefer fewer HIGH-QUALITY pitfalls over many weak ones

------------------------------------------------
OUTPUT FORMAT
------------------------------------------------

Return JSON ONLY:

{
  "pitfalls":[
    {
      "concept":"snake_case_concept_name",
      "pitfall":"clear description of the mistake",
      "evidence":"exact phrase or sentence from the text"
    }
  ]
}
"""

MATH_CONCEPT_PROMPT = """
You are an elite actuarial professor, probability theorist, and advanced calculus instructor.

Your task:
Extract ALL mathematically testable concepts from these notes.

ASSUME:
These notes prepare students for actuarial exams (P, FM, IFM, SRM),
advanced probability courses, mathematical statistics, and upper-level calculus.

PRIORITY:
We are optimizing for EXAM RELEVANCE + MATHEMATICAL RIGOR.

--------------------------------------------
EXTRACT ALL TESTABLE MATHEMATICAL UNITS:
--------------------------------------------

1) Core Theorems
- Named theorems (e.g., Central Limit Theorem)
- Distribution identities
- Convergence results
- Independence results
- Law of Total Expectation / Variance
- Conditioning results

2) Distribution Structure
- PDF / PMF definitions
- CDF derivations
- Parameter interpretation
- Support/domain restrictions
- Shape, scale, rate meanings
- Special cases (e.g., Gamma(a=1) = Exponential)

3) Transformations
- Change-of-variable formulas
- Jacobians
- W = g(X,Y) transformations
- Linear combinations
- Sum of independent variables
- Convolution formulas

4) Expectation & Variance Logic
- Derivations
- Moment calculations
- MGF usage
- Conditional expectation
- Variance decomposition

5) Integrals & Calculus Logic
- Integration tricks
- Substitution steps
- Limits of integration changes
- Differentiation under the integral sign
- Integration by parts used in derivations

6) Statistical Structure
- Likelihood functions
- Estimator properties
- Bias
- Consistency
- Variance formulas
- Fisher Information (if present)

7) Proof Structure
If a proof appears:
Extract EACH major logical leap as a separate concept.

8) Actuarial Signals
If material resembles:
- Conditioning arguments
- Gamma/Beta integrals
- Continuous-time models
- Risk models
- Distribution relationships
- Independence proofs

Extract aggressively.

--------------------------------------------
EXAM PRIORITY RULES
--------------------------------------------

If:
• A formula is derived step-by-step
• A distribution identity is proven
• A transformation is demonstrated
• A method is reused
• A result is boxed or emphasized
• A result is used in a worked example

Assign confidence ≥ 0.8

If:
• A theorem is named
• A core identity appears
• A common exam trick appears

Assign confidence ≥ 0.9

--------------------------------------------
QUALITY RULES
--------------------------------------------

• Each concept must be independently testable
• Must be mathematically precise
• No vague phrases
• No slide metadata
• No decorative text
• Extract 25–80 concepts if available
• DO NOT under-extract

--------------------------------------------
FORMULA HANDLING RULE
--------------------------------------------

If a formula appears, extract:

1) The formula
2) What it represents
3) When it applies
4) Required assumptions

--------------------------------------------

Return JSON ONLY:

{
  "concepts":[
    {
      "name":"snake_case_name",
      "description":"precise mathematical explanation",
      "evidence":"exact phrase or equation copied from the notes",
      "confidence":0.0
    }
  ]
}

CRITICAL RULE:

Every concept MUST include an "evidence" field.

Evidence must be copied EXACTLY from the notes.

If you cannot find supporting text,
DO NOT include the concept.
"""

EXAM_RANK_PROMPT = """
You are an expert professor designing exams.

Your task:
Rank concepts by how likely they are to appear on an exam.

Consider:
- core definitions
- formulas used in problems
- named laws/theorems
- frequently tested ideas
- concepts used in applications
- common sources of mistakes

Less important:
- minor examples
- decorative info
- historical notes

Return JSON ONLY:

{
  "ranked":[
    {"name":"concept_name","exam_score":0.0}
  ]
}

exam_score:
0.9–1.0 = almost guaranteed exam topic
0.7–0.89 = very likely
0.5–0.69 = possibly tested
<0.5 = low priority
"""


PRACTICE_PROMPT = """You are an expert educator and assessment designer.

Your job is to generate high-quality practice questions that build deep understanding and exam readiness.
"You MUST ground questions in the provided definition, when_to_use, and pitfalls.",
You MUST output valid JSON that follows the provided schema exactly.
Do NOT include any text outside JSON.

GOAL
Create a question that:
- tests reasoning, not memorization
- requires selecting methods or concepts
- teaches thinking through structured solutions
- includes common mistakes

CONSTRAINTS
1) The question must be ORIGINAL.
Create an ORIGINAL question that tests the same skills and concepts as typical exam questions, but with a new scenario, values, and framing.

2) The question must be solvable using the given concepts.
3) Difficulty must match the requested level.
4) Include at least:
- 3 reasoning steps
- 2 common mistakes (for difficulty ≥3)
5) Solutions must explain WHY a method is chosen.

Return ONLY valid JSON matching the schema.
"""

MCQ_PROMPT = """
You are an expert exam writer.

Create a concept-grounded MULTIPLE CHOICE question.

Rules:
- Base the question on the provided concepts
- Test understanding, not memorization
- 4 options
- Only ONE correct
- Distractors must reflect common misunderstandings
- Question should resemble real exams

Return JSON ONLY:

{
 "type":"mcq",
 "prompt":"...",
 "options":["A","B","C","D"],
 "correct_index":0,
 "explanation":"why correct"
}
"""

# Canonical schema for a single question object (matches your docs)
QUESTION_SCHEMA = {
  "type": "object",
  "required": ["metadata", "prompt", "reasoning_path", "common_mistakes", "solution", "confidence_tags"],
  "properties": {
    "metadata": {
      "type": "object",
      "required": ["concepts", "difficulty", "cognitive_skill", "subject_tag"],
      "properties": {
        "concepts": {"type": "array", "items": {"type": "string"}},
        "difficulty": {"type": "integer", "minimum": 1, "maximum": 5},
        "cognitive_skill": {"type": "string", "enum": ["recall", "application", "reasoning", "synthesis"]},
        "subject_tag": {"type": "string"}
      }
    },
    "prompt": {"type": "string"},
    "reasoning_path": {"type": "array", "minItems": 3, "items": {"type": "string"}},
    "common_mistakes": {
    "type": "array",
    "items": {
    "type": "object",
    "required": ["description","why_wrong","tag"],
    "properties": {
      "description":{"type":"string"},
      "why_wrong":{"type":"string"},
      "tag":{"type":"string"}
    }
}
},
    "solution": {
      "type": "object",
      "required": ["steps","final_answer"],
      "properties": {
        "steps": {"type":"array","items":{"type":"string"}},
        "final_answer": {"type":"string"},
        "interpretation": {"type":"string"}
      }
    },
    "confidence_tags": {
      "type":"object",
      "required":["formula_selection_required","multi_step","concept_combo"],
      "properties":{
        "formula_selection_required":{"type":"boolean"},
        "multi_step":{"type":"boolean"},
        "concept_combo":{"type":"boolean"}
      }
    }
  }
}

MCQ_SCHEMA = {
  "type":"object",
  "required":["type","prompt","options","correct_index","explanation"],
  "properties":{
    "type":{"const":"mcq"},
    "prompt":{"type":"string"},
    "options":{
      "type":"array",
      "minItems":4,
      "maxItems":5,
      "items":{"type":"string"}
    },
    "correct_index":{
      "type":"integer",
      "minimum":0,
      "maximum":4
    },
    "explanation":{"type":"string"}
  }
}
def grounding_confidence(answer: str, concepts: list):

    hits = 0

    for c in concepts:
        if c.name.lower().replace("_"," ") in answer.lower():
            hits += 1

    return round(hits / max(1, len(concepts)), 2)

def normalize_concept_name(name: str):

    name = name.lower().strip()

    name = name.replace(" distribution","")
    name = name.replace("_distribution","")

    name = name.replace(" theorem","")
    name = name.replace("_theorem","")

    return name


EXAM_META_PATTERNS = [
    r"\bexam\b",
    r"\bhigh[- ]yield\b",
    r"\boften tested\b",
    r"\bfrequently tested\b",
    r"\bscenario[- ]based questions?\b",
    r"\bcritical distinction for questions?\b",
    r"\bcommon in multiple choice\b",
    r"\bprocess questions?\b",
    r"\btest(s|ing)? the\b",
]

EXAMPLE_PATTERNS = [
    r"^example:",
    r"\be\.g\.",
    r"\bfor example\b",
]

STATISTIC_PATTERNS = [
    r"\b\d+(\.\d+)?%\b",
    r"\b\d+(\.\d+)?\s*(million|billion|thousand)\b",
    r"\$\d+",
]

STEP_PATTERNS = [
    r"\bstep\s*\d+\b",
    r"^\d+\.",
    r"\bfirst step\b",
    r"\bsecond step\b",
    r"\bthird step\b",
]

PITFALL_PATTERNS = [
    r"\bpitfall\b",
    r"\bcommon error\b",
    r"\bmistake\b",
    r"\bconfusing\b",
    r"\bincorrect\b",
    r"\bshould not\b",
]


def _matches_any(patterns: list[str], text: str) -> bool:
    text = (text or "").lower()
    return any(re.search(p, text, re.I) for p in patterns)


def classify_concept_role(concept: dict) -> str:
    """
    Broad, domain-agnostic role assignment.
    Works for business, science, math, humanities, etc.
    """
    name = concept.get("name", "")
    desc = concept.get("description", "")
    evidence = concept.get("evidence", "")
    text = f"{name} {desc} {evidence}".strip()

    if _matches_any(EXAM_META_PATTERNS, text):
        return "exam_meta"

    if _matches_any(PITFALL_PATTERNS, name) or _matches_any(PITFALL_PATTERNS, desc):
        return "pitfall"

    if _matches_any(STEP_PATTERNS, name) or _matches_any(STEP_PATTERNS, evidence):
        return "process_step"

    if _matches_any(EXAMPLE_PATTERNS, evidence) or _matches_any(EXAMPLE_PATTERNS, desc):
        return "example"

    # statistic-only concepts are often weak standalone flashcards
    if _matches_any(STATISTIC_PATTERNS, evidence):
        # if the description is mostly just a stat, mark as statistic
        if len(desc.split()) <= 16:
            return "statistic"

    exam_score = float(concept.get("exam_score", 0.5))
    confidence = float(concept.get("confidence", 0.5))
    final_score = float(concept.get("final_score", 0.5))

    if final_score >= 0.78 or exam_score >= 0.82 or confidence >= 0.88:
        return "core"

    return "supporting"


def assign_card_budget(concept: dict) -> int:
    """
    Broad budget:
    - 0 = do not make a standalone card
    - 1 = one good card
    - 2 = anchor + one deeper card
    """
    role = concept.get("role") or classify_concept_role(concept)

    exam_score = float(concept.get("exam_score", 0.5))
    confidence = float(concept.get("confidence", 0.5))
    final_score = float(concept.get("final_score", 0.5))

    if role == "exam_meta":
        return 0

    if role == "core":
        return 2

    if role in {"supporting", "process_step", "pitfall"}:
        return 1

    if role == "example":
        return 1 if (exam_score >= 0.78 or final_score >= 0.75) else 0

    if role == "statistic":
        return 1 if (exam_score >= 0.82 or confidence >= 0.9) else 0

    return 1


def annotate_concepts_for_flashcards(concepts: list[dict]) -> list[dict]:
    annotated = []

    for c in concepts:
        c = dict(c)
        c["role"] = classify_concept_role(c)
        c["card_budget"] = assign_card_budget(c)
        annotated.append(c)

    return annotated


async def extract_concepts_from_note(note_text: str):
    cleaned = clean_note_text(note_text)

    if not cleaned.strip():
        return []

    chunks = chunk_text_by_lines(cleaned, max_lines=70)
    all_concepts = []

    for chunk in chunks:
        resp = kimi_client.chat.completions.create(
            model="kimi-k2.5",
            messages=[
                {"role": "system", "content": CONCEPT_PROMPT},
                {"role": "user", "content": chunk},
            ],
        )

        raw = resp.choices[0].message.content
        print("\n📄 LLM RAW RESPONSE:\n", raw)
        parsed = safe_json_loads(raw)
        print("\n✅ PARSED JSON:\n", parsed)

        if not parsed or "concepts" not in parsed:
            continue

        chunk_concepts = parsed["concepts"]

        grounded = []
        for c in chunk_concepts:
            evidence = c.get("evidence", "").lower().strip()
            if evidence and evidence[:80] in chunk.lower():
                grounded.append(c)

        all_concepts.extend(grounded)

    concepts = all_concepts

    concepts = booster_add_named_concepts(cleaned, concepts)
    concepts = booster_add_formula_concepts(cleaned, concepts)
    concepts = booster_add_acronyms(cleaned, concepts)
    concepts = booster_review_sections(cleaned, concepts)
    concepts = booster_add_objective_concepts(cleaned, concepts)
    concepts = booster_add_comparisons(cleaned, concepts)
    normalized = {}
    for c in concepts:
        key = normalize_concept_name(c["name"])
        best = normalized.get(key)

        if not best or c.get("confidence", 0) > best.get("confidence", 0):
            normalized[key] = c

    concepts = list(normalized.values())

    filtered = []
    for c in concepts:
        conf = c.get("confidence", 0)

        if c.get("exam_priority_locked"):
            filtered.append(c)
            continue

        if conf >= 0.40:
            filtered.append(c)
            continue

        if len(c["name"].split("_")) <= 2 and conf >= 0.30:
            filtered.append(c)

    ranked = await rank_exam_importance(filtered)

    for c in ranked:
        c["final_score"] = (
            0.55 * c.get("confidence", 0.5)
            + 0.45 * c.get("exam_score", 0.5)
        )

    ranked.sort(key=lambda x: x["final_score"], reverse=True)
    ranked = [
        c for c in ranked
        if c.get("exam_score", 0) >= 0.28 or c.get("confidence", 0) >= 0.72
    ]

    ranked = semantic_dedupe(ranked, threshold=0.93)
    ranked = annotate_concepts_for_flashcards(ranked)

    return ranked[:100]
    



async def rank_exam_importance(concepts: list[dict]):

    if not concepts:
        return []

    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role":"system","content":EXAM_RANK_PROMPT},
            {"role":"user","content":json.dumps(concepts)}
        ],
        temperature=0.0
    )

    parsed = safe_json_loads(resp.choices[0].message.content)

    if not parsed or "ranked" not in parsed:
        return concepts

    scores = {r["name"]: r["exam_score"] for r in parsed["ranked"]}

    for c in concepts:
        c["exam_score"] = scores.get(c["name"], 0.5)

    concepts.sort(
        key=lambda x: x.get("exam_score",0),
        reverse=True
    )

    return concepts


async def extract_math_concepts_from_note(note_text: str):

    cleaned = clean_note_text(note_text)

    if not cleaned.strip():
        return []

    resp = kimi_client.chat.completions.create(
        model="kimi-k2.5",
        messages=[
            {"role": "system", "content": MATH_CONCEPT_PROMPT},
            {"role": "user", "content": cleaned},
        ],
        
    )

    raw = resp.choices[0].message.content
    parsed = safe_json_loads(raw)

    if not parsed or "concepts" not in parsed:
        return []

    concepts = parsed["concepts"]
    # -------- GROUNDING CHECK --------

    grounded = []

    for c in concepts:

        evidence = c.get("evidence","").lower()

        if evidence and evidence.lower().strip()[:50] in cleaned.lower():
            grounded.append(c)

    concepts = grounded

    concepts = booster_math_formulas(cleaned, concepts)
    concepts = booster_math_identities(cleaned, concepts)
    concepts = booster_math_derivations(cleaned, concepts)
    concepts = booster_distributions(cleaned, concepts)
    concepts = booster_add_formula_concepts(cleaned, concepts)
    concepts = booster_add_named_concepts(cleaned, concepts)

    concepts = list({c["name"]: c for c in concepts}.values())
    ranked = await rank_exam_importance(concepts)

    for c in ranked:
        c["final_score"] = (
            0.55 * c.get("confidence", 0.5)
            + 0.45 * c.get("exam_score", 0.5)
        )

    ranked = semantic_dedupe(ranked, threshold=0.94)
    ranked = annotate_concepts_for_flashcards(ranked)

    return ranked[:80]

async def generate_one_question(concepts: list, difficulty: int, subject_tag: str, context_blob="", concept_details: list | None = None):
    payload = {
        "concepts": concepts,
        "difficulty": difficulty,
        "subject": subject_tag
    }
    # Build grounding context
    context_blob = ""

    if concept_details:
        context_blob = "\n".join([
            f"Concept: {c.get('name')}\n"
            f"Definition: {c.get('definition','')}\n"
            for c in concept_details
        ])

    resp = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {
                "role": "system",
                "content": PRACTICE_PROMPT
            },
            {
                "role": "system",
                "content": f"""
    Here are gold-standard example exam questions.
    Follow their style, structure, and reasoning depth.

    {EXAMPLE_QUESTIONS}
    """
            },
            {
                "role": "user",
                "content": f"""
    Use this student context:

    {context_blob}
    
    INPUTS:
    {json.dumps(payload)}

    SCHEMA:
    {json.dumps(QUESTION_SCHEMA)}
    """
            }
        ],
        temperature=0.3,
    )

    content = resp.choices[0].message.content
    q = json.loads(content)

    try:
        validate(instance=q, schema=QUESTION_SCHEMA)
    except ValidationError as e:
        raise ValueError(f"Invalid question format: {e}")

    return q
    
async def generate_mcq(concepts, difficulty, subject_tag):

    payload = {
        "concepts": concepts,
        "difficulty": difficulty,
        "subject": subject_tag
    }

    resp = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role":"system","content":MCQ_PROMPT},
            {"role":"user","content":json.dumps(payload)}
        ],
        temperature=0.4
    )

    raw = resp.choices[0].message.content

    try:
        q = json.loads(raw)
    except json.JSONDecodeError:
        print("⚠️ BAD MCQ JSON:\n", raw)
        raise ValueError("MCQ model returned invalid JSON")

    validate(instance=q, schema=MCQ_SCHEMA)

    return q

DEPENDENCY_PROMPT = """
You are an expert educator.

Your job is to identify prerequisite relationships between concepts.

Given concepts with definitions, return which concepts depend on others.

RULES:
- Only include REAL prerequisite relationships
- If unsure, omit it
- A concept can have multiple prerequisites

Return JSON ONLY:

[
  {"concept":"concept_a","depends_on":"concept_b"},
  ...
]
"""

async def propose_dependencies(concepts: list[dict]):
    """
    concepts = [
      {"name":..., "definition":...},
      ...
    ]
    """

    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role":"system","content":DEPENDENCY_PROMPT},
            {"role":"user","content":json.dumps(concepts)}
        ],
        temperature=0.2
    )

    return json.loads(resp.choices[0].message.content)
    

HOMEWORK_PROMPT = """
You are a Socratic tutor.

Rules:
- Ask guiding questions
- Do not give full solutions immediately
- Let student reason
- Break into small steps

If student is stuck:
→ ask a diagnostic question

Always end with a question that pushes thinking.
"""

async def grounded_homework_help(question: str, concept_context: str):

    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role":"system","content": HOMEWORK_PROMPT},
            {
                "role":"user",
                "content": f"""
Student question:
{question}

Class concepts:
{concept_context}
"""
            }
        ],
        temperature=0.4
    )

    return resp.choices[0].message.content
    
    
async def generate_flashcards_from_concepts(concepts: list[dict]):
    all_cards = []

    for batch in batch_list(concepts, size=18):
        resp = client.chat.completions.create(
            model="gpt-5.4",
            messages=[
                {
                "role":"system",
                "content":"""
You are an expert learning scientist, educator, and exam designer.

Create HIGH-QUALITY atomic flashcards.

Follow the MINIMUM INFORMATION PRINCIPLE used by Anki.

--------------------------------
PRIMARY GOAL
--------------------------------

Build the SMALLEST high-quality deck that still preserves BROAD and DEEP coverage of the notes.

Do NOT maximize card count.
Maximize:
• learning value per card
• exam performance
• conceptual clarity
• mistake prevention
• efficient review

Each concept may include:
• role
• card_budget
• description
• definition
• when_to_use
• pitfalls
• evidence
• confidence

You MUST obey card_budget strictly.

--------------------------------
CORE LEARNING RULES
--------------------------------

1. Each flashcard must test ONE meaningful concept or decision point.
2. Do NOT split a definition into trivial micro-questions.
3. Prefer ONE strong card over several weak or overlapping cards.
4. Answers must be SHORT (1–2 lines max).
5. Avoid paraphrasing the same concept multiple times.
6. Prefer deeper conceptual questions over surface rewording.
7. Do NOT create multiple cards asking the same definition in different wording.
8. Prefer questions that prevent mistakes over questions that merely restate notes.
9. Do NOT force a card if the concept is weak, redundant, example-only, or low-value.
10. Do NOT exceed the allowed budget for any concept.

--------------------------------
CARD BUDGET RULES (MANDATORY)
--------------------------------

For EACH concept:

• If card_budget = 0:
  Generate NO standalone card.

• If card_budget = 1:
  Generate EXACTLY 1 strong card.

• If card_budget = 2:
  Generate EXACTLY 2 cards:
  1) EXACTLY 1 anchor card
  2) EXACTLY 1 deeper card

Never exceed card_budget.

If a concept is supporting rather than core, usually generate only one compact, high-value card.

--------------------------------
ANCHOR VS DEEPER CARD RULE
--------------------------------

ANCHOR CARD:
A core memory-stabilizing card.

Valid anchor types:
• definition
• core identification
• key distinction
• framework recognition
• process step identification
• formula recognition (if applicable)

DEEPER CARD:
A card that improves exam decision-making or prevents errors.

Valid deeper types:
• pitfall
• when-to-use
• when-NOT-to-use
• condition / assumption
• comparison
• application
• scenario recognition
• mechanism / interpretation

If card_budget = 2, the second card should almost always be the deeper card.

--------------------------------
CARD TYPE MIX (DECK LEVEL)
--------------------------------

Across the FULL deck, aim approximately for:

• 25–35% Definition / Core Identification
• 20–30% Understanding / Mechanism
• 15–25% Comparison / Distinction
• 10–20% Application / Scenario
• 10–20% Pitfall / When-to-use / Condition
• 0–10% Recognition

These are deck-level tendencies, not per-concept requirements.

Do NOT force all card types for every concept.

The goal is BALANCED understanding, not maximum quantity.

--------------------------------
DIVERSITY RULE
--------------------------------

Across the FULL deck:

• Use pitfall cards when they prevent REAL wrong answers
• Use decision / when-to-use cards when conditions matter
• Avoid repeating the same card type for concept after concept
• Do not overproduce definition cards if a deeper card would teach more

--------------------------------
CRITICAL THINKING CARDS
--------------------------------

You MUST actively use these fields when they are meaningful and grounded:

• "pitfalls" → generate concrete mistake-prevention cards
• "when_to_use" → generate decision / condition cards
• evidence → generate grounded cards with real distinctions
• definition → generate anchor cards when needed

If the concept payload includes a pitfall or usage boundary,
prefer converting that into a strong card rather than producing another shallow definition card.

--------------------------------
PITFALL GENERATION (EXAM-GRADE)
--------------------------------

A pitfall is a HIGH-PROBABILITY mistake that would realistically cause a student to lose points.

A valid pitfall usually involves one of:

• CONFUSION — mixing this concept with a similar one
• MISAPPLICATION — using the concept in the wrong situation
• MISSING CONDITION — ignoring a required assumption or boundary
• OVERSIMPLIFICATION — using a vague definition that leads to wrong answers
• MISINTERPRETATION — drawing the wrong meaning from the concept

Only generate a pitfall card if:

• a student could realistically make this mistake
• the mistake would lead to a wrong answer or wrong method
• the pitfall clarifies a boundary, contrast, or condition

If not, DO NOT generate a pitfall card.

PREFERRED PITFALL TYPES

• contrast traps
• “when this fails” scenarios
• hidden assumption errors
• subtle definition traps
• wrong-application traps

WEAK PITFALLS (DO NOT GENERATE)

• “students forget this”
• “be careful with ___”
• vague warnings with no concrete failure mode

GOOD PITFALL FORMATS

Q: What mistake do students make when using ___?
Q: What concept is commonly confused with ___?
Q: When is it incorrect to apply ___?
Q: What condition is often ignored when using ___?

--------------------------------
ROLE-AWARE GENERATION RULE
--------------------------------

Use role intelligently:

• core:
  usually deserves the strongest anchor and, if budget allows, one deeper card

• supporting:
  usually deserves only one compact, high-value card

• process_step:
  card should focus on the purpose of the step, correct sequence, or order mistake

• pitfall:
  card should focus on the concrete misunderstanding and correction

• example:
  only generate a card if the example teaches a transferable exam pattern

• statistic:
  only generate a card if the number itself is testable and meaningful

• exam_meta:
  generate NO card unless card_budget explicitly permits it,
  and even then avoid “this is often tested” style wording

--------------------------------
DEFINITION QUALITY RULE
--------------------------------

A definition card must:

• clearly state what the concept IS
• not merely describe behavior vaguely
• be answerable in ≤2 lines
• be testable in direct exam-style wording

These rules are NOT optional.

But do NOT force a definition card if a stronger anchor card exists
and the concept budget is only 1.

--------------------------------
COMPARISON RULE
--------------------------------

If related concepts exist, comparison cards are HIGH VALUE.

Generate comparison cards when they help prevent confusion.

Examples:
• ERP vs MRP
• CPU vs RAM
• social media vs SMIS
• traditional CRM vs social CRM
• human capital vs social capital

A strong comparison card should clarify:
• difference in purpose
• difference in usage
• difference in structure
• difference in conditions
• what students commonly mix up

--------------------------------
LIST HANDLING RULE
--------------------------------

If evidence contains a list:

• create a list recall card ONLY if the whole list is genuinely testable as a unit
• do NOT automatically create extra cards for every list item
• only create an additional item-level card if an item is especially important, confusing, or exam-relevant

Do NOT inflate the deck just because a list appears.

--------------------------------
EXAMPLE RULE
--------------------------------

If evidence contains an example or scenario:

• create a card ONLY if the example teaches a transferable pattern, application, or distinction
• do NOT create standalone cards for weak or decorative examples
• prefer examples that improve interpretation, method choice, or recognition

--------------------------------
GROUNDING RULE
--------------------------------

If an "evidence" field exists, ground the flashcard in that text.

Use:
• evidence
• pitfalls
• when_to_use
• definition

Do NOT invent facts not supported by the concept payload.

Every flashcard must be grounded in the extracted concept data.

--------------------------------
DUPLICATE PREVENTION RULE
--------------------------------

Do NOT generate:

• multiple cards asking the same definition in different wording
• one definition card plus another disguised definition card
• separate cards for minor variations of the same concept
• separate cards for weak examples unless clearly valuable
• “this is often tested” cards
• cards that overlap heavily in learning value

If two candidate cards teach nearly the same thing, keep the stronger one.

--------------------------------
GOOD EXAMPLES
--------------------------------

Good:

Q: What type of process has fixed sequences and rare exceptions?
A: Structured process.

Q: Which business process type is dynamic and unpredictable?
A: Social media processes.

Q: When should social CRM be emphasized over traditional CRM?
A: When customer influence and real-time interaction matter more than controlled transactions.

--------------------------------
BAD EXAMPLES
--------------------------------

Bad:

Q: What are the three types of processes?
A: Structured, Dynamic, Hybrid.

Q: What is an important idea about social media?
A: It is important.

Q: What is this concept called?
A: [paraphrased duplicate of another card]

Do NOT generate weak or bloated cards like these.

--------------------------------
ANSWER STYLE
--------------------------------

Answers must be:
• short
• precise
• direct
• usually 1–2 lines

Do not write mini-paragraphs.

--------------------------------
OUTPUT FORMAT
--------------------------------

Return JSON ONLY:

{
  "flashcards":[
    {
      "concept_name":"snake_case_name",
      "question":"...",
      "answer":"...",
      "confidence":0.8
    }
  ]
}
"""
            },
            {
                "role": "user",
                    "content": f"""
Generate flashcards from these concepts.

Requirements:
- Obey card_budget strictly.
- Return concept_name for every card.
- Keep cards atomic.
- Do not compress multiple concepts into one card.
- Avoid paraphrase duplicates.
- Prefer the smallest strong deck over maximum quantity.
- Prefer mistake prevention, conditions, comparisons, and when-to-use over shallow recall when those are grounded.

Concepts:
{json.dumps(batch)}
"""
                }
            ],
            temperature=0.2,
            max_completion_tokens=5000
        )

        parsed = safe_json_loads(resp.choices[0].message.content)

        if parsed:
            all_cards.extend(parsed.get("flashcards", []))

    unique = {}
    for c in all_cards:
        q = c.get("question", "").strip().lower()
        if q:
            unique[q] = c

    return list(unique.values())

async def generate_math_flashcards_from_concepts(concepts: list[dict]):
    all_cards = []

    for batch in batch_list(concepts, size=16):
        resp = client.chat.completions.create(
            model="gpt-5.4",
            messages=[
                {
                "role": "system",
                "content": """
You are an expert mathematician, statistician, actuarial scientist, and learning scientist.

Your task is to generate HIGH-QUALITY MATHEMATICAL FLASHCARDS that help students master
mathematical reasoning, proof logic, formula selection, and problem-solving strategies.

These flashcards must support university-level mathematics including:

• calculus
• advanced calculus
• probability theory
• mathematical statistics
• discrete mathematics
• combinatorics
• graph theory
• linear algebra
• differential equations
• optimization
• actuarial mathematics

--------------------------------
CORE LEARNING PRINCIPLE
--------------------------------

Follow the **Minimum Information Principle** used by Anki.

Each flashcard must test ONE meaningful mathematical idea.

Avoid splitting concepts into trivial fragments.

Prefer one strong conceptual card over several weak cards.

--------------------------------
CARD TYPES
--------------------------------

Across the deck maintain approximately:

20% Formula Recall
30% Formula Selection (PRIMARY)
20% Concept Understanding
10% Pattern Recognition
10% Pitfalls (MANDATORY)
10% Method Identification

--------------------------------
EXAM FAILURE PREVENTION (CRITICAL)
--------------------------------

You MUST generate flashcards that explicitly prevent common exam failures:

1) WRONG FORMULA SELECTION
2) MISSING CONDITIONS
3) DOMAIN / SUPPORT ERRORS
4) SIGN / VARIABLE MISUSE
5) INCOMPLETE SOLUTIONS

At least 40% of concepts MUST include a failure-prevention (pitfall) card.

--------------------------------
PROOF AND LOGIC CARDS
--------------------------------

If the concept involves a proof, theorem, or logical structure,
generate cards that test:

• key proof steps
• assumptions required
• why the result holds
• common logical mistakes

Example:

Q: What key assumption allows the Central Limit Theorem to apply?
A: Independent and identically distributed variables with finite variance.

--------------------------------
DISCRETE MATH RULE
--------------------------------

If concepts involve:

• combinatorics
• recurrence relations
• graph structures
• algorithmic complexity
• logical inference

Create flashcards that test:

• reasoning steps
• structural properties
• interpretation of results

--------------------------------
FLASHCARD TYPES EXPLAINED
--------------------------------

1️⃣ Formula Recall

Test recognition of important formulas.

Example:
Q: What is the variance of a Poisson distribution with parameter λ?
A: Var(X) = λ

---

2️⃣ Formula Selection

Test when a formula or method should be used.

Example:
Q: When should integration by parts be used?
A: When integrating a product of functions where one simplifies when differentiated.

---

3️⃣ Pattern Recognition

Test identifying distributions, structures, or identities.

Example:
Q: What distribution has density proportional to q^(a−1)(1−q)^(b−1)?
A: Beta distribution.

---

4️⃣ Concept Understanding

Test interpretation of mathematical results.

Example:
Q: What does the parameter λ represent in a Poisson distribution?
A: The expected number of events per interval.

---

5️⃣ Method Identification

Test which mathematical technique solves a problem.

Example:
Q: What technique is commonly used to compute the distribution of a sum of independent variables?
A: Convolution.

---

6️⃣ Common Pitfall

Test common mistakes students make.

Example:
Q: What mistake do students often make when applying the Central Limit Theorem?
A: Forgetting that the theorem applies to sample means or sums, not individual observations.

--------------------------------
CARD GENERATION RULES
--------------------------------

Generate between **2 and 4 flashcards per concept**.

Avoid repeating the same formula or concept using slightly different wording.

Prefer deeper conceptual questions rather than trivial recall.

Answers must be **short (1–2 lines)**.

--------------------------------
PER CONCEPT STRUCTURE (MANDATORY)
--------------------------------

For EACH concept, you MUST generate:

• EXACTLY 1 core anchor card:
  - either formula recall OR core identification

AND

• At least 1 deeper card:
  - formula selection OR pitfall OR multi-step reasoning

Do NOT generate only recall-based cards.

Each concept MUST include depth.

--------------------------------
PRIORITY ORDER
--------------------------------

If limited information is available, prioritize:

1) Formula selection (HIGHEST)
2) Pitfalls / failure prevention
3) Conditions / assumptions
4) Multi-step reasoning
5) Formula recall (LOWEST)

The goal is EXAM PERFORMANCE, not memorization.

--------------------------------
VARIABLE INTERPRETATION RULE
--------------------------------

If a formula appears, try to generate at least one card explaining:

• what the formula represents
• what each key variable means
• when the formula should be used

--------------------------------
FORMULA HANDLING RULE
--------------------------------

If a formula appears in the concept:

Create flashcards testing:

• formula recognition
• variable meaning
• conditions of validity
• typical application scenarios

--------------------------------
FORMULA DECISION RULE (CRITICAL)
--------------------------------

For EACH important formula, you MUST generate at least one card that tests:

• WHEN to use the formula
• WHEN NOT to use it
• What alternative method might be confused with it

--------------------------------
MULTI-STEP THINKING RULE
--------------------------------

If a concept is used in multi-step problems:

Generate at least one card that tests:

• sequence of reasoning
• first step identification
• intermediate reasoning

These simulate real exam problem solving.


--------------------------------
TRAP PRIORITY RULE
--------------------------------

If concepts are similar:

You MUST generate confusion/comparison cards.

These are HIGH PRIORITY for exam performance.

--------------------------------
PATTERN RECOGNITION RULE
--------------------------------

If expressions resemble known mathematical structures such as:

q^(a−1)(1−q)^(b−1)

or

e^(−λx)

or

Σ Xi

Create recognition flashcards that test identification of the distribution or concept.

--------------------------------
GROUNDING RULE
--------------------------------

If a concept contains an **"evidence" field**, use that evidence
to ground the flashcard.

Do NOT invent formulas or theorems not supported by the concept list.

Flashcards must be grounded in the extracted concepts.

--------------------------------
GOOD FLASHCARD EXAMPLES
--------------------------------

Good:

Q: What distribution has density proportional to q^(a−1)(1−q)^(b−1)?
A: Beta distribution.

Q: When should the convolution formula be used?
A: When finding the distribution of the sum of independent random variables.

Q: What does λ represent in a Poisson distribution?
A: The expected number of events per interval.

--------------------------------
BAD FLASHCARD EXAMPLES
--------------------------------

Bad:

Q: What is mathematics?
A: A field of study.

Q: What is a distribution?
A: Something describing probability.

--------------------------------
OUTPUT FORMAT
--------------------------------

Return JSON ONLY:

{
  "flashcards":[
    {
      "concept_name":"snake_case_name",
      "question":"...",
      "answer":"...",
      "confidence":0.8
    }
  ]
}
"""
            },
            {
                "role": "user",
                    "content": f"""
Generate mathematical flashcards from these concepts.

Requirements:
- Return concept_name for every card.
- Keep each card atomic.
- Prefer formula selection and pitfall prevention over shallow recall.

Concepts:
{json.dumps(batch)}
"""
                }
            ],
            temperature=0.2,
            max_completion_tokens=5000
        )

        parsed = safe_json_loads(resp.choices[0].message.content)

        if parsed:
            all_cards.extend(parsed.get("flashcards", []))

    # exact question dedupe first
    unique = {}
    for c in all_cards:
        q = c.get("question", "").strip().lower()
        if q:
            unique[q] = c

    deduped = dedupe_flashcards(list(unique.values()))
    return deduped
    
def semantic_dedupe(concepts, threshold=0.96):
    unique = []

    for c in concepts:
        if "embedding" not in c:
            text = f"{c.get('name','')} {c.get('description','')}"
            c["embedding"] = embed_text(text)

        cvec = np.array(c["embedding"])
        keep = True

        for u in unique:
            c_evidence = c.get("evidence", "").strip().lower()
            u_evidence = u.get("evidence", "").strip().lower()

            # If evidence is different, allow both to coexist
            if c_evidence and u_evidence and c_evidence != u_evidence:
                continue

            if "embedding" not in u:
                text = f"{u.get('name','')} {u.get('description','')}"
                u["embedding"] = embed_text(text)

            uvec = np.array(u["embedding"])

            if cosine_sim(cvec, uvec) > threshold:
                keep = False
                break

        if keep:
            unique.append(c)

    return unique
    
    
def normalize_card_text(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def flashcards_too_similar(a: dict, b: dict) -> bool:
    qa = normalize_card_text(a.get("question", ""))
    qb = normalize_card_text(b.get("question", ""))
    aa = normalize_card_text(a.get("answer", ""))
    ab = normalize_card_text(b.get("answer", ""))

    if qa == qb:
        return True

    # same concept + same answer + very overlapping question
    if a.get("concept_name") == b.get("concept_name") and aa == ab:
        a_words = set(qa.split())
        b_words = set(qb.split())
        if not a_words or not b_words:
            return False
        overlap = len(a_words & b_words) / max(1, len(a_words | b_words))
        if overlap >= 0.72:
            return True

    return False


def dedupe_flashcards(cards: list[dict]) -> list[dict]:
    unique = []

    for card in cards:
        keep = True
        for seen in unique:
            if flashcards_too_similar(card, seen):
                keep = False
                break
        if keep:
            unique.append(card)

    return unique
