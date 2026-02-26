Mastery System v1 (Concept-Level Learning Model)

Goal

Estimate how well a student understands each concept and adapt practice accordingly.

Each concept has:

mastery_prob ∈ [0,1]

Meaning:
    •    0.25 = weak understanding
    •    0.50 = developing
    •    0.75 = strong
    •    0.90+ = near mastery

⸻

Initialization

When a concept is first seen:

mastery_prob = 0.35

Rationale:
    •    assumes partial familiarity
    •    avoids overconfidence
    •    avoids pessimism

⸻

Update After Each Attempt

Inputs:
    •    correct (boolean)
    •    difficulty (1–5)
    •    confidence (1–5)
    •    time_spent_sec
    •    last_practiced_at

⸻

Update Rule

1) Base delta

base = 0.08

delta = base if correct else -base

⸻

2) Difficulty scaling

difficulty_factor = 0.7 + 0.1 × difficulty

delta *= difficulty_factor

Harder questions impact mastery more.

⸻

3) Confidence scaling

confidence_factor = 0.8 + 0.05 × confidence

delta *= confidence_factor

High confidence wrong answers reduce mastery more (captures misconceptions).

⸻

4) Apply update

mastery_prob += delta

Clamp:

mastery_prob = min(0.99, max(0.01, mastery_prob))

Never allow 0 or 1.

⸻

Forgetting Curve

If a concept is not practiced:

mastery *= exp(-λ × days_since_last_practice)

Use:

λ = 0.04

This creates natural decay and enables spaced repetition.

⸻

Readiness Score

Per class:

readiness = average mastery across exam-relevant concepts

Used for:
    •    dashboards
    •    study planning
    •    motivation

⸻

Question Selection Policy

Prioritize:
    1.    Low mastery concepts
    2.    Recently decayed concepts
    3.    Exam-tagged concepts

Avoid:
    •    repeating mastered concepts too often
    •    showing only easy questions

⸻

Design Philosophy

This system models learning, not streaks.

It reflects:
    •    knowledge growth
    •    forgetting
    •    confidence calibration

This creates true personalization.
