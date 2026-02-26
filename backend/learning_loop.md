# Learning Loop v1 (Core System Architecture)

## Purpose

Define how all core systems connect to create an adaptive study engine.

This app is not a collection of tools.

It is a CLOSED LEARNING LOOP that continuously adapts to the student.

Core idea:

Capture → Practice → Evaluate → Update Mastery → Plan → Repeat

---

# Core Philosophy

Students do not just need content.

They need:
- feedback
- adaptation
- prioritization
- exam-oriented preparation

The system must always answer:
"What should I study next?"

---

# The Learning Loop

## Step 1 — Notes → Concept Extraction

User writes notes.

AI extracts:
- concepts
- definitions
- importance weights

Store:
- concepts table
- note_concepts mapping

Outcome:
A structured knowledge map for the class.

---

## Step 2 — Concepts → Practice Generation

Practice is generated from:
- selected concepts
- low mastery concepts
- upcoming exam topics

Questions follow the canonical schema.

Outcome:
Practice sets tied to concepts.

---

## Step 3 — Practice → Attempts

When a student answers:
Store:
- correctness
- time_spent
- confidence rating
- timestamp

Outcome:
Raw performance data.

---

## Step 4 — Attempts → Mastery Update

For each related concept:

Update mastery probability using:
- correctness
- difficulty
- confidence
- forgetting decay

Outcome:
Dynamic mastery score per concept.

---

## Step 5 — Mastery → Study Plan

Study plan reads:
- mastery scores
- exam dates
- exam weight/importance

It computes:
- urgency
- review vs practice balance
- daily task list

Outcome:
Personalized daily plan.

---

## Step 6 — Study Plan → Practice Again

Plan tells the student:
- what to review
- what to practice
- what to maintain

Student practices again.

Loop repeats.

---

# Minimal Data Flow Diagram

Notes
→ Concept Extraction
→ Concepts DB

Concepts + Mastery
→ Practice Generation
→ Questions

Questions
→ Attempts
→ Mastery Update

Mastery + Exams
→ Study Plan
→ Daily Tasks

Daily Tasks
→ Practice

LOOP CONTINUES

---

# MVP Definition

A working MVP requires:

1) Concept extraction
2) Practice generation
3) Attempt tracking
4) Mastery updates
5) Study plan generation

Anything else is optional.

---

# Design Principles

1) Adaptation > Content volume
2) Feedback > Flashcards
3) Exam relevance > trivia
4) Clarity > complexity

---

# Success Criteria

The system is successful if:

- Students know what to study each day
- Weak areas are surfaced automatically
- Practice adapts over time
- Students feel exam-ready

---

# Future Extensions (Not MVP)

- energy-based scheduling
- burnout detection
- streak psychology
- time-of-day optimization
- deep sequence ML models

These are optimizations, not core.
