# Planning implementation note

College AI contains two planning architectures. They should not be conflated.

1. **Exam Prep/Exam Lockdown** is the current mounted Planner experience. It persists syllabus evidence, material questions, predictions, plans, tasks, recommendations, and coaching progress.
2. **Generic daily/weekly planning** is an earlier deterministic API/component experiment. Its code remains available, but its React components are not mounted on the current `/planner` page.

This document describes the retained generic planner in `app/routers/plan.py` and `app/services/planner.py`. Exam Prep lives in `app/routers/exam_prep.py` and `app/services/exam_prep.py`.

## Generic endpoint inputs

Both endpoints accept:

- a user-owned `class_id`;
- either a user/course-owned `exam_id` or an ISO exam timestamp;
- `available_minutes_per_day` from 10 to 480, default 60.

The exam must be in the future and no more than 365 days away.

```text
POST /plan/generate
POST /plan/weekly-generate
```

Responses are computed JSON and are not persisted as plan/task rows. With no concepts, the endpoints return an empty, shape-consistent response.

## Daily plan

For each course concept, the route supplies:

- stored mastery or `0.35`;
- `next_review_at`;
- total mistake-log count;
- definition, use, and pitfalls;
- an importance heuristic that starts at `0.5` and adds name-based boosts for `definition`, `formula`, `law`, and `theorem` (boosts can accumulate).

The service ranks concept blocks using:

```text
priority = (1 - mastery)
         + 0.5 when the review is already due
         + 0.15 × mistake_count
         + base_0.5_and_name_boosts
```

Concept block size is based on mastery:

| Stored mastery | Minutes per selected block |
| --- | --- |
| below `0.3` | 20 |
| below `0.5` | 15 |
| below `0.7` | 10 |
| otherwise | 5 |

The remaining budget becomes an exam-style practice block with up to five minutes reserved for reflection. The algorithm creates one day for each whole day before the exam, with a minimum one-day horizon.

## Weekly plan

The weekly service sorts concepts weakest first. For each day it combines concepts due by that day with up to four weak concepts, keeps at most three targets, and schedules at most two review blocks. The remaining budget is split into:

- up to eight minutes of reflection;
- a practice block targeted around half of the daily budget (subject to available time);
- review time divided across selected concepts.

It returns `weeks_left`, `days_left`, and a nested `weekly_plan`.

## What the generic planner does not implement

An older design described a multiplicative urgency equation using time-to-exam, forgetting duration, exam weight, and fixed 60/30/10 mastery buckets. That equation is **not** implemented.

The retained planner also does not:

- persist completion state;
- use the exam's `weight` field in ranking;
- apply mastery forgetting dynamically;
- call an AI provider;
- learn from plan completion;
- guarantee that its suggested work fits a student's real schedule;
- appear in the mounted Planner UI.

## Current Exam Prep distinction

The mounted Exam Prep flow accepts syllabus/material evidence, exam targets, weak topics, daily minutes, and intensity. It persists the resulting plan, creates concrete tasks, links recommendations to persisted extracted questions, and feeds Exam Lockdown. Model-assisted evidence parsing and prediction are uncertain, while validation, scoring inputs, record links, task creation, and status transitions are application logic.

Future cleanup should either remove the unmounted generic planner or reconnect it deliberately. Until then, documentation and portfolio claims should present it as retained experimental code.
