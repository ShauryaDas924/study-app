Study Plan System v1 (Adaptive Planning Engine)

Goal

Generate a daily study plan that:
    •    prioritizes weak concepts
    •    respects exam timelines
    •    adapts to mastery + forgetting
    •    avoids overload
    •    feels achievable

This system answers:

“What should I study today?”

⸻

Core Inputs

For each class:
    •    exam_date
    •    exam_weight (1–5 importance)
    •    concept list
    •    mastery per concept
    •    last_practiced_at per concept
    •    user available study time per day (minutes)

⸻

Step 1 — Compute Urgency Score

For each concept:

Time Factor

days_to_exam = (exam_date - today)

time_factor = 1 / max(days_to_exam, 1)

Closer exam = higher urgency.

⸻

Mastery Factor

mastery_factor = (1 - mastery_prob)

Weak concepts prioritized.

⸻

Forgetting Factor

days_since = days_since_last_practice

forgetting_factor = 1 + 0.15 × days_since

Recently ignored topics rise in priority.

⸻

Exam Weight Factor

weight_factor = 1 + 0.25 × exam_weight

Important exams influence plan more.

⸻

Final Urgency Score

urgency =
time_factor × mastery_factor × forgetting_factor × weight_factor

⸻

Step 2 — Rank Concepts

Sort concepts by urgency descending.

Top concepts = today’s targets.

⸻

Step 3 — Allocate Time

Assume:

daily_minutes = user_available_time

Divide:

60% → weak/high urgency concepts
30% → medium mastery review
10% → strong concepts (maintenance)

Example (60 min day):

36 min weak
18 min medium
6 min strong

⸻

Step 4 — Convert to Tasks

Each task should be concrete:

✅ “Do 5 practice questions on Conditional Probability”
✅ “Review formulas for Interest Theory (10 min)”
✅ “Reattempt 2 incorrect questions from yesterday”

NOT vague:
❌ “Study math”

⸻

Step 5 — Difficulty Progression

If mastery < 0.4:
→ easier + guided questions

0.4–0.7:
→ standard exam-level

0.7:
→ harder/synthesis questions

⸻

Step 6 — Daily Plan Output Format

Return:

Today's Plan

1) Concept: X  
   Task: 5 practice questions  
   Reason: Low mastery + exam soon  

2) Concept: Y  
   Task: Review notes + 3 questions  
   Reason: High forgetting risk  

3) Concept: Z  
   Task: 2 challenge problems  
   Reason: Maintain mastery

Step 7 — Adaptation Rule

After each attempt:
    •    update mastery
    •    recalc urgency
    •    adjust tomorrow’s plan

The system is alive, not static.

⸻

Design Philosophy

The plan should feel:
    •    realistic
    •    personalized
    •    achievable
    •    motivating

Students should think:

“I can finish this today.”

Consistency > intensity.
