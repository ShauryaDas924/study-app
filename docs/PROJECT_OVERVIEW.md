# Project Overview

## What This Project Is

College AI is a full-stack study app for college coursework. It combines class management, note storage, AI concept extraction, flashcards, practice generation, homework tutoring, mastery tracking, planning, analytics, and an evidence-based Exam Lockdown workflow.

The repository is split into:

- `frontend/`: a Next.js/React/TypeScript app.
- `backend/`: a FastAPI app using async SQLAlchemy and Postgres.

## Why It Exists

The project is built around a learning-loop idea documented in `backend/learning_loop.md`:

```text
Capture -> Practice -> Evaluate -> Update Mastery -> Plan -> Repeat
```

The app is not only a chatbot. It stores structured learning artifacts and uses them across multiple study workflows.

## Problem It Solves

Students often have course materials spread across notes, homework, practice banks, past exams, and review sheets. They also may not know which topics are weak or what to study next.

College AI tries to solve this by:

- Keeping data scoped by class.
- Extracting concepts from notes.
- Generating practice and flashcards from stored concepts.
- Tracking attempts, mistakes, pitfalls, and mastery.
- Creating study plans.
- Using uploaded materials as evidence for exam prep.
- Letting Tutor coach exact recommended questions.

## Main Users

- College students studying for classes and exams.
- A solo developer maintaining or extending the product.
- Technical reviewers evaluating the product architecture and AI workflows.
- AI coding agents that need project context before modifying the code.

## Core Workflows

### 1. Class Setup

1. User creates or selects a class.
2. Frontend stores selected class ID in Zustand.
3. Backend routes verify the class belongs to the authenticated user before accessing class data.

Important files:

- `frontend/components/ClassSelector.tsx`
- `frontend/store/useStore.ts`
- `backend/app/routers/classes.py`
- `backend/app/services/auth.py`

### 2. Notes To Concepts

1. User creates a note or uploads a note file.
2. Backend extracts text from supported files.
3. Concept extraction can be queued as a background task.
4. Concepts, flashcards, and related study artifacts are stored.

Important files:

- `frontend/app/notes/page.tsx`
- `frontend/components/UploadNotes.tsx`
- `backend/app/routers/notes.py`
- `backend/app/routers/uploads.py`
- `backend/app/jobs/concept_jobs.py`
- `backend/app/routers/concepts.py`

### 3. Practice And Mastery

1. User generates practice for class concepts.
2. User submits attempts.
3. Backend records correctness, confidence, mistakes, and updates mastery.
4. Analytics and remedial practice use this stored data.

Important files:

- `frontend/app/practice/page.tsx`
- `frontend/components/PracticeSetup.tsx`
- `frontend/components/PracticePlayer.tsx`
- `backend/app/routers/practice.py`
- `backend/app/services/mastery.py`

### 4. Homework Tutor And Pitfalls

1. User asks for homework help or uploads homework.
2. Backend retrieves relevant concepts and calls LLM services.
3. Step review and work review can capture repeated pitfalls.
4. Tutor page can generate practice from stored pitfalls.

Important files:

- `frontend/app/homework/page.tsx`
- `frontend/app/tutor/page.tsx`
- `frontend/components/TutorChat.tsx`
- `backend/app/routers/homework.py`

### 5. Planner

1. User asks for a daily or weekly study plan.
2. Backend planner routes use class/concept context.
3. Frontend renders study plan views and planner UI.

Important files:

- `frontend/app/planner/page.tsx`
- `frontend/components/StudyPlanGenerator.tsx`
- `frontend/components/WeeklyPlanGenerator.tsx`
- `backend/app/routers/plan.py`
- `backend/app/services/planner.py`

### 6. Exam Lockdown

1. User uploads exam-prep materials such as syllabi, notes, past exams, homework, practice banks, review sheets, announcements, answer keys, and solutions.
2. Backend stores material rows and extracted text.
3. User explicitly extracts questions from selected materials.
4. Planner generates an evidence-based plan with ranked topics, day blocks, warnings, and recommended questions linked to extracted question IDs.
5. Tutor's Exam Lockdown mode loads the active plan and coaches selected recommended questions.
6. Attempts, progress, and exam-specific pitfalls can be saved.

Important files:

- `frontend/components/exam-prep/`
- `frontend/components/exam-lockdown/`
- `backend/app/routers/exam_prep.py`
- `backend/app/routers/exam_lockdown.py`
- `backend/app/services/exam_prep.py`
- `backend/app/services/exam_lockdown.py`
- `backend/migrations/20260506_exam_prep_planner.sql`
- `backend/migrations/20260512_exam_lockdown_materials.sql`
- `backend/migrations/20260515_exam_prep_extracted_question_status.sql`

## Important Concepts And Terminology

| Term | Meaning in this repo |
| --- | --- |
| Class | User-owned course container. Most data is scoped to a class. |
| Note | Stored note content, usually class-specific. |
| Concept | Extracted or generated learning unit tied to a class. |
| Mastery | Concept-level learning estimate updated through practice. |
| Attempt | User answer submission for practice/exam questions. |
| Pitfall | Stored repeated mistake or weakness pattern. |
| Exam prep material | Uploaded file used as evidence for an exam plan. |
| Extracted question | Persisted located question from an uploaded exam-prep material. |
| Recommended question | Link between an exam prep plan and an extracted question. |
| Exam Lockdown | Tutor mode that works from an active evidence-based exam prep plan. |

## Product Behavior

The product behavior is class-scoped. The frontend selected class determines which data should be loaded, and backend routes generally verify `user_id` and `class_id` before returning or mutating data.

LLM outputs are not treated only as chat text. Many LLM outputs become persistent database records, including concepts, practice questions, plans, extracted questions, recommendations, tutor memories, and pitfalls.

## In Scope

Supported or strongly represented by the current repo:

- Web app frontend.
- FastAPI backend.
- Supabase authentication integration.
- Class-scoped study data.
- Notes, uploads, concept extraction, flashcards, practice, homework help, planner, analytics, and exam prep.
- Postgres-backed persistence.
- LLM-assisted study workflows.

## Out Of Scope Or Unknown

Unknown from current repo:

- Production deployment architecture.
- CI/CD setup.
- Automated test suite.
- License.
- Privacy policy.
- Security policy.
- Data retention policy.
- Object/file storage strategy for original uploaded files.
- Complete database migration history for the base schema outside exam prep migrations.

## Current Limitations

- No automated tests were found.
- Backend deployment commands are not documented in repo scripts.
- Environment examples are not committed in the main source tree.
- Real environment files exist locally (`backend/.env`, `frontend/.env.local`) and should not be committed.
- Some generated or local files are present, including `.DS_Store`, `__pycache__`, `.next`, `node_modules`, `backend/venv`, and `College_AI_resume_audit_context/`; these are not source.
- CORS is configured as `allow_origins=["*"]` in `backend/app/main.py`; production restrictions are unknown.

## High-Level Understanding

Think of College AI as a study operating system for class-specific learning data. The core value is the loop between uploaded/created learning material, extracted structure, practice, evaluation, mastery, planning, and tutoring.
