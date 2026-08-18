# Project overview

College AI is an archived full-stack learning MVP. It organizes material by course, derives structured learning objects with AI providers, records practice signals, and turns uploaded exam evidence into a source-linked preparation workflow.

The repository is a portfolio artifact, not a currently operated service. Its value is the inspectable implementation: a typed frontend, authenticated REST API, asynchronous database access, a broad relational model, AI-provider boundaries, deterministic learning logic, and explicit MVP tradeoffs.

## Problem and product shape

College material is usually split across notes, slide decks, problem sets, chats, and study tools. The MVP explored a single loop:

```text
course material → concepts → practice → attempts/mistakes → mastery → next study action
```

A second, more grounded path handles exam preparation:

```text
syllabus + exam material → extracted source questions → ranked plan → lockdown coaching
```

Model output assists extraction, generation, and coaching. The application persists the resulting objects and applies deterministic validation, ranking, ownership, status, and scheduling logic around them.

## Current user-facing workflows

| Workflow | What is implemented | Persistence |
| --- | --- | --- |
| Identity and courses | Supabase login; create, select, clear, and delete user-owned courses | PostgreSQL plus selected course in browser state |
| Notes and concepts | Manual notes or bounded uploads; background refinement, concept extraction, embeddings, dependencies, and flashcards | PostgreSQL; live job status also cached in process |
| Flashcards | Generated cards, review state, and session controls | PostgreSQL; some current-session state in `localStorage` |
| Practice | Open and MCQ generation, attempts, mistake logs, hints, remedial sets, exam sessions, readiness | PostgreSQL |
| Tutor and homework | Class-aware tutor, chat memory, uploaded work review, step review, and pitfall memory | PostgreSQL; homework display history also in `localStorage` |
| Analytics | Mastery, readiness, mistake heatmaps, weakness/tag views, and knowledge graph | Derived from PostgreSQL records |
| Exam Prep | Syllabus parsing, exam-material extraction, source questions, topic ranking, schedule and tasks | PostgreSQL |
| Exam Lockdown | Source-question coaching, attempts, progress, and pitfalls tied to an active plan | PostgreSQL |
| Blurting and mind map | Editable browser study boards | `localStorage` only |

The mounted `/planner` page contains the Exam Prep workflow. `StudyPlanGenerator`, `WeeklyPlanGenerator`, and the `/plan/generate` and `/plan/weekly-generate` APIs remain as earlier deterministic experiments; they are not presented as current UI features.

## System boundaries

- The browser is responsible for interactive state, the Supabase session, and several local drafts.
- FastAPI verifies the bearer token and is the authorization boundary for server data.
- PostgreSQL is the system of record for server-side learning state.
- OpenAI and Moonshot/Kimi are external processors for selected AI-assisted flows.
- `pgvector` stores concept embeddings; small-scope retrieval is ranked with NumPy in the application.
- FastAPI `BackgroundTasks` runs note extraction in the API process. There is no Redis or durable worker queue.

## Deliberate MVP decisions

- Multiple-choice attempts are graded from the stored answer key on the server; non-MCQ answers remain self-assessed.
- Mastery is a lightweight Bayesian-style estimate, not a validated psychometric model.
- Exam recommendations link to persisted extracted questions, but source extraction and topic inference can still be wrong.
- Upload checks enforce size, extension, filename, page, pixel, and expanded-archive limits; they do not scan for malware.
- The database model is extensive, but the repository contains only incremental Exam Prep/Lockdown migrations and cannot create the full base schema from scratch.
- Browser-only drafts are convenient but are not encrypted or governed by server deletion.

## Good code-review entry points

- `backend/app/routers/classes.py` — ownership-aware multi-table clear/delete logic.
- `backend/app/jobs/concept_jobs.py` — staged extraction, concurrency control, and persisted status.
- `backend/app/services/llm.py` — provider calls, structured output, embeddings, and retrieval.
- `backend/app/services/exam_prep.py` — scoring, planning, validation, and source-linked recommendations.
- `backend/app/services/attempts.py` and `backend/app/services/mastery.py` — deterministic grading and learning-state updates.
- `frontend/lib/api.ts` — frontend/backend contract surface.
- `frontend/components/exam-prep/` and `frontend/components/exam-lockdown/` — the most complete cross-layer workflow.

For trust boundaries and request flows, continue with [Architecture](ARCHITECTURE.md). For a status-by-feature view, see [Features](FEATURES.md).
