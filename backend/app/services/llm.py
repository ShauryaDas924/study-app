

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

    # Remove control characters but KEEP math symbols
    text = re.sub(r"[\u0000-\u001F\u007F-\u009F]", " ", text)

    # Remove repeated decorative symbols
    text = re.sub(r"[•■►●◆]+", " ", text)

    # Remove slide numbers like "Slide 12"
    text = re.sub(r"\bslide\s*\d+\b", " ", text, flags=re.I)

    # Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)

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
    
def attach_pitfalls_to_concepts(concepts, pitfalls):

    # normalize concept names
    concept_map = {
        normalize_concept_name(c["name"]): c
        for c in concepts
    }

    for p in pitfalls:
        key = normalize_concept_name(p["concept"])

        if key in concept_map:
            c = concept_map[key]

            if "pitfalls" not in c:
                c["pitfalls"] = []

            # avoid duplicates
            if p["pitfall"] not in c["pitfalls"]:
                c["pitfalls"].append(p["pitfall"])

    return list(concept_map.values())
    
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


async def extract_concepts_from_note(note_text: str):
    cleaned = clean_note_text(note_text)

    if not cleaned.strip():
        return []
    resp = kimi_client.chat.completions.create(
        model="kimi-k2.5",
        messages=[
            {"role": "system", "content": CONCEPT_PROMPT},

            {"role": "user", "content": cleaned},
        ],
        
    )
    raw = resp.choices[0].message.content
    print("\n📄 LLM RAW RESPONSE:\n", raw)
    parsed = safe_json_loads(raw)
    print("\n✅ PARSED JSON:\n", parsed)

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
    
    concepts = booster_add_named_concepts(
        cleaned,
        concepts
    )

    concepts = booster_add_formula_concepts(
        cleaned,
        concepts
    )
    concepts = booster_add_acronyms(cleaned, concepts)

    concepts = booster_review_sections(cleaned, concepts)

    normalized = {}

    for c in concepts:
        key = normalize_concept_name(c["name"])
        normalized[key] = c

    concepts = list(normalized.values())

    filtered = []

    for c in concepts:
        conf = c.get("confidence", 0)

        # keep high confidence
        if conf >= 0.40:
            filtered.append(c)
            continue

        # keep short key terms
        if len(c["name"].split("_")) <= 2 and conf >= 0.30:
            filtered.append(c)

    # ⭐ ADD THIS PART
    ranked = await rank_exam_importance(filtered)
    for c in ranked:
        c["final_score"] = (
            0.6 * c.get("confidence", 0.5)
            + 0.4 * c.get("exam_score", 0.5)
        )

    ranked.sort(key=lambda x: x["final_score"], reverse=True)
    # keep more concepts
    ranked = [c for c in ranked if c.get("exam_score",0) >= 0.45]

    ranked = semantic_dedupe(ranked)

    return ranked[:60]
    

async def extract_pitfalls_from_note(note_text: str):

    cleaned = clean_note_text(note_text)

    if not cleaned.strip():
        return []

    resp = kimi_client.chat.completions.create(
        model="kimi-k2.5",
        messages=[
            {"role": "system", "content": PITFALL_PROMPT},
            {"role": "user", "content": cleaned},
        ],
    )

    raw = resp.choices[0].message.content
    parsed = safe_json_loads(raw)

    if not parsed or "pitfalls" not in parsed:
        return []

    # -------- GROUNDING CHECK (CRITICAL — SAME STANDARD AS CONCEPTS) --------
    grounded = []

    for p in parsed["pitfalls"]:
        evidence = p.get("evidence", "").lower()

        if evidence and evidence.strip()[:50] in cleaned.lower():
            grounded.append(p)

    return grounded

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

    resp = client.chat.completions.create(
        model="gpt-5.4",
        messages=[
            {
                "role":"system",
                "content":"""
You are an expert learning scientist and educator.

Create HIGH-QUALITY atomic flashcards.

Follow the MINIMUM INFORMATION PRINCIPLE used by Anki.

RULES

1. Each flashcard must test ONE meaningful concept.
2. Do NOT split a definition into trivial micro-questions.
3. Prefer ONE strong definition card over several tiny fragments.
4. Answers must be SHORT (1–2 lines max).
5. Generate between 3 and 5 flashcards per concept.
6. Avoid paraphrasing the same concept multiple times.
7. Prefer deeper conceptual questions over surface rewording.
8. Do NOT create multiple cards asking the same definition in different wording.
9. Prefer questions that prevent mistakes over questions that repeat definitions.
CARD TYPE MIX

Across the deck maintain approximately:

35% Definition cards
30% Understanding cards
20% Comparison cards
10% Application cards
5% Recognition cards

DIVERSITY RULE (CRITICAL)

Across the FULL deck:

• At least 40% of concepts should include pitfall cards  
• At least 40% should include decision (when-to-use) cards  
• Avoid repeating the same card type for every concept  

The goal is BALANCED understanding, not maximum quantity.

CRITICAL THINKING CARDS (STRICT REQUIREMENT)

For EACH concept:

If a "pitfalls" field exists:
→ You MUST generate at least ONE pitfall-based flashcard

This is NOT optional.

A pitfall card MUST:
• describe a specific mistake
• test recognition or correction of that mistake
• be clearly tied to exam failure modes

Examples:

Q: What mistake do students make when applying ___?
A: ...

Q: Why is it incorrect to apply ___ in this situation?
A: ...

Q: What condition do students often ignore when using ___?
A: ...

FAILURE TO INCLUDE PITFALL CARDS = INVALID OUTPUT

--------------------------------

You MUST actively use:

• "Common Pitfalls" → generate mistake-based cards
• "Conditions / assumptions" → generate when-to-use cards
• "Exam Insight" → generate decision or reasoning cards

If these sections exist in the concept, you MUST convert them into flashcards.

REQUIRED PER CONCEPT

You MUST generate 2–3 flashcards per concept.

Across those cards, you MUST include:

• At least 1 Definition OR Understanding card  
• At least 1 deeper card (Pitfall OR Decision OR Application)

Do NOT force all card types for every concept.
Only generate what is meaningful and supported by the concept.

These are NOT optional.

OPTIONAL BUT PREFERRED

• 1 Comparison card if related concepts exist
• 1 Application card if a scenario is possible
• 1 Recognition card resembling exam style

COMPARISON RULE

If multiple related concepts exist (e.g., ERP vs MRP, CPU vs RAM),
generate comparison questions.

LIST HANDLING RULE

If the evidence contains a list, create:

• one list recall card
• additional cards testing individual items.

GROUNDING

If an "evidence" field exists, ground the flashcard in that text.

Do NOT invent facts not supported by evidence.

GOOD examples:

Q: What type of process has fixed sequences and rare exceptions?
A: Structured process

Q: Which business process type supports strategic decisions?
A: Dynamic processes

BAD examples:

Q: What are the three types of processes?
A: Structured, Dynamic, Hybrid

Do NOT generate large list answers.

EXAMPLE RULE

If evidence contains an example or scenario,
create a flashcard testing the example.

DO NOT invent information not supported by evidence.

Return JSON ONLY:

{
  "flashcards":[
    {
      "question":"...",
      "answer":"...",
      "confidence":0.8
    }
  ]
}
"""
            },
            {
                "role":"user",
                "content": json.dumps(concepts)
            }
        ],
        temperature=0.2,
        max_completion_tokens=2000
    )

    parsed = safe_json_loads(resp.choices[0].message.content)

    if not parsed:
        return []

    cards = parsed.get("flashcards", [])

    unique = {}
    for c in cards:
        key = c["question"].strip().lower()
        unique[key] = c

    return list(unique.values())

async def generate_math_flashcards_from_concepts(concepts: list[dict]):

    resp = client.chat.completions.create(
        model="gpt-4.1",
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

30% Formula Recall
25% Formula Selection
20% Concept Understanding
15% Pattern Recognition
5% Method Identification
5% Common Pitfall

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
   "question":"...",
   "answer":"...",
   "confidence":0.9
  }
 ]
}
"""
            },
            {
                "role": "user",
                "content": json.dumps(concepts)
            }
        ],
        temperature=0.2,
        max_tokens=2000
    )

    parsed = safe_json_loads(resp.choices[0].message.content)

    if not parsed:
        return []

    cards = parsed.get("flashcards", [])

    unique = {}

    for c in cards:
        key = c["question"].strip().lower()
        unique[key] = c

    return list(unique.values())
    
def semantic_dedupe(concepts, threshold=0.92):

    unique = []

    for c in concepts:

        # create embedding if missing
        if "embedding" not in c:
            text = f"{c.get('name','')} {c.get('description','')}"
            c["embedding"] = embed_text(text)

        cvec = np.array(c["embedding"])

        keep = True

        for u in unique:

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
