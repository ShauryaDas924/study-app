# Practice Engine Blueprint v1 (Exam-Oriented Mastery)

## Primary Goal
**Exam-Oriented Mastery**
> Ensure the student understands concepts deeply enough to apply them in new exam-style scenarios.

This system generates practice that forces:
- concept understanding
- reasoning steps
- decision-making
Not memorization.

---

## Question Object Schema (Canonical)

Every generated question MUST include the following fields.

### 1) Metadata
- `concepts`: [list of concept_ids OR concept_names for v1]
- `difficulty`: 1–5
- `cognitive_skill`: one of
  - recall
  - application
  - reasoning
  - synthesis
- `subject_tag`: e.g.
  - math
  - actuarial
  - data_science
  - physics
  - chemistry
  - history
  - etc

### 2) Question Prompt
The actual question text.

Rules:
- scenario-based when possible
- requires selecting a method/formula/model (for difficulty ≥ 3)
- not a pure definition question unless difficulty = 1
- includes enough context to be solvable without guessing

### 3) Expected Reasoning Path (Structured)
This is the core teaching value.
Must include clear steps like:

- step_1: identify concept being tested
- step_2: choose method / formula / model
- step_3: apply method correctly
- step_4: interpret result / check reasonableness

### 4) Common Mistakes (With Explanations)
At least 2 mistakes for difficulty ≥ 3.

Format:
- mistake_1:
  - description
  - why_wrong
- mistake_2:
  - description
  - why_wrong

### 5) Solution (Worked + Explained)
Must:
- show steps
- explain WHY this method is chosen
- include interpretation / reasonableness check
- (optional) give a quick “exam tip” at the end

### 6) Confidence Tags (for tuning)
- `formula_selection_required`: true/false
- `multi_step`: true/false
- `concept_combo`: true/false

---

## Quality Standards (Non-negotiable)

A "good" question:
- tests *application*, not trivia
- includes reasoning path + common mistakes
- teaches the student how to decide what tool to use

A "bad" question:
- is just recall
- has no explanation for why a formula/model was chosen
- has no mistake analysis
- is vague or underspecified

---

## Manual Gold Standard Examples (Required)
These are written manually (not AI-generated) to define quality.

### Example 1 — Actuarial/Math (FM-style)
#### Metadata
- concepts: [ nominal_intrest_rate, compounding_frequency, exponential_growth]
- difficulty: 4
- cognitive_skill: reasoning
- subject_tag: actuarial

#### Prompt
Lucas invests $1000 at a nominal annual interest rate of 6% convertible semiannually.
Danielle invests $1000 at a nominal annual interest rate of 3% convertible monthly.

Interest is credited only at the end of each conversion period.

How many months are required for Lucas’s account value to be at least twice Danielle’s?

#### Expected Reasoning Path
    •    step_1: convert nominal rates to periodic rates
    •    step_2: express both accounts as exponential growth functions of time
    •    step_3: write inequality comparing the two balances
    •    step_4: solve logarithmically for time
    •    step_5: convert to months and round appropriately

#### Common Mistakes
mistake_1
    •    description: comparing nominal rates directly (6% vs 3%)
    •    why_wrong: ignores compounding frequency

mistake_2
    •    description: mixing time units (years vs months)
    •    why_wrong: leads to incorrect exponents

#### Solution
Lucas:
    •    semiannual rate = 0.06 / 2 = 0.03
    •    value after t years:
1000(1.03)^(2t)

Danielle:
    •    monthly rate = 0.03 / 12 = 0.0025
    •    value after t years:
1000(1.0025)^(12t)

We want:
1000(1.03)^(2t) ≥ 2·1000(1.0025)^(12t)

Cancel 1000:
(1.03)^(2t) ≥ 2(1.0025)^(12t)

Take logs and solve for t.

(You’d complete the algebra here.)

Interpretation:
Time represents when Lucas’s stronger compounding overtakes Danielle’s.

#### Confidence Tags
    •    formula_selection_required: true
    •    multi_step: true
    •    concept_combo: true
---

### Example 2 — General Chemistry
#### Metadata
- concepts: [acid_base_neutralization, strong_acids_bases, net_ionic_equations]
- difficulty: 2
- cognitive_skill: application
- subject_tag: chemistry

#### Prompt
Nitric acid (HNO₃) reacts with sodium hydroxide (NaOH) in aqueous solution.

Which of the following represents the correct net ionic equation?

A) HNO₃(aq) + NaOH(aq) → NaNO₃(aq) + H₂O(l)
B) H⁺ + NO₃⁻ + Na⁺ + OH⁻ → Na⁺ + NO₃⁻ + H₂O
C) H⁺ + OH⁻ → H₂O
D) HNO₃ + OH⁻ → NO₃⁻ + H₂O
E) Na⁺ + OH⁻ → NaOH

#### Expected Reasoning Path
    •    step_1: identify this as a strong acid–strong base reaction
    •    step_2: dissociate strong electrolytes into ions
    •    step_3: remove spectator ions
    •    step_4: write the true reacting species

#### Common Mistakes
mistake_1
    •    description: keeping spectator ions in the final equation
    •    why_wrong: net ionic equations only show reacting species

mistake_2
    •    description: not dissociating strong acids/bases
    •    why_wrong: strong electrolytes fully ionize in water

#### Solution
HNO₃ and NaOH are both strong electrolytes.

Full ionic form:
H⁺ + NO₃⁻ + Na⁺ + OH⁻ → Na⁺ + NO₃⁻ + H₂O

Na⁺ and NO₃⁻ are spectator ions and cancel.

Net ionic equation:
H⁺ + OH⁻ → H₂O

Correct answer: C

Interpretation:
Neutralization reactions between strong acids and bases always reduce to proton + hydroxide forming water.

#### Confidence Tags
    •    formula_selection_required: false
    •    multi_step: true
    •    concept_combo: false
---

### Example 3 — Linear Algebra
#### Metadata
- concepts: [solving_linear_systems, matrix_vector_multiplication, linear_combinations]
- difficulty: 3
- cognitive_skill: reasoning
- subject_tag: linear_algebra

#### Prompt
Let

A =
\begin{pmatrix}
1 & 2 & -1 \\
0 & 1 & 3 \\
2 & -1 & 1
\end{pmatrix},
\quad
\mathbf{x} =
\begin{pmatrix}
x_1\\
x_2\\
x_3
\end{pmatrix},
\quad
\mathbf{b} =
\begin{pmatrix}
4\\
5\\
1
\end{pmatrix}.

(a) Write the system of equations corresponding to A\mathbf{x}=\mathbf{b}.
(b) Solve the system.
(c) Express \mathbf{b} as a linear combination of the columns of A.

#### Expected Reasoning Path
    •    step_1: convert matrix equation into a system of linear equations
    •    step_2: use substitution or elimination to solve
    •    step_3: interpret solution vector
    •    step_4: express b as a linear combination using solution coefficients
#### Common Mistakes
mistake_1
    •    description: mixing up rows and columns when forming equations
    •    why_wrong: leads to incorrect system setup

mistake_2
    •    description: arithmetic errors during elimination
    •    why_wrong: produces incorrect solution vector
#### Solution
(a) System

\begin{cases}
x_1 + 2x_2 - x_3 = 4 \\
x_2 + 3x_3 = 5 \\
2x_1 - x_2 + x_3 = 1
\end{cases}

⸻

(b) Solve

From equation 2:

x_2 = 5 - 3x_3

Substitute into eq 1:

x_1 + 2(5-3x_3) - x_3 = 4
x_1 +10 -6x_3 -x_3 = 4
x_1 = -6 +7x_3

Substitute into eq 3:

2(-6+7x_3) - (5-3x_3) + x_3 = 1
-12 +14x_3 -5 +3x_3 +x_3 =1
-17 +18x_3 =1
x_3 =1

Then:

x_2=2,\quad x_1=1

Solution:

(x_1,x_2,x_3)=(1,2,1)

⸻

(c) Linear Combination

\mathbf{b}=1\mathbf{a}_1 +2\mathbf{a}_2 +1\mathbf{a}_3

(where \mathbf{a}_i are columns of A)

Interpretation:
The solution gives the weights needed to combine columns of A to get b.

#### Confidence Tags
    •    formula_selection_required: false
    •    multi_step: true
    •    concept_combo: true
