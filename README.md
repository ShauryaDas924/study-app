# College AI

College AI is a full-stack AI study app for managing college course materials, extracting concepts from notes, generating practice, tracking mastery, planning study work, and running an evidence-based Exam Lockdown tutoring flow.

The project is for students who want one place to organize class-specific notes, homework help, practice questions, flashcards, analytics, and exam prep. It is also useful as a portfolio project because it combines a Next.js frontend, FastAPI backend, Postgres persistence, Supabase authentication, and several LLM-backed learning workflows.

## What The Project Does

- Lets users create and select classes/courses.
- Stores notes by class and supports AI concept extraction from those notes.
- Generates concepts, flashcards, practice questions, remedial practice, and learning analytics.
- Provides homework help, step review, chat memory, and stored student pitfalls.
- Tracks attempts, mistakes, mastery, exam sessions, flashcard state, and planner tasks.
- Provides a Planner page for exam prep.
- Provides an Exam Lockdown workflow where uploaded course materials are used as evidence for an exam plan and Tutor can coach recommended questions.

## Main Features

| Area | Summary | Key files |
| --- | --- | --- |
| Authentication | Supabase session on the frontend and backend Bearer-token verification. | `frontend/lib/auth.ts`, `frontend/lib/supabaseClient.ts`, `backend/app/services/auth.py` |
| Classes | User-owned class creation, listing, clearing, and deletion. | `backend/app/routers/classes.py`, `frontend/app/courses/page.tsx` |
| Notes | Notes can be created manually or from uploads. Concept extraction runs as a background task. | `backend/app/routers/notes.py`, `backend/app/routers/uploads.py`, `backend/app/jobs/concept_jobs.py`, `frontend/app/notes/page.tsx` |
| Concepts and flashcards | Extracted concepts support flashcards and review state. | `backend/app/routers/concepts.py`, `frontend/app/flashcards/page.tsx` |
| Practice | Practice generation, remedial practice, attempts, step hints, step checks, exam sessions, readiness, and analytics. | `backend/app/routers/practice.py`, `frontend/app/practice/page.tsx` |
| Tutor and homework | Normal Tutor, homework help, work review, step review, chat memory, and pitfalls. | `backend/app/routers/homework.py`, `frontend/app/tutor/page.tsx`, `frontend/components/TutorChat.tsx` |
| Planner | Daily and weekly plan generation plus exam prep planner UI. | `backend/app/routers/plan.py`, `frontend/app/planner/page.tsx` |
| Exam Lockdown | Evidence upload, question extraction, plan generation, recommended questions, tutor coaching, attempts, progress, and pitfalls. | `backend/app/routers/exam_prep.py`, `backend/app/routers/exam_lockdown.py`, `frontend/components/exam-prep/`, `frontend/components/exam-lockdown/` |
| Analytics | Mistake heatmap, weakness map, tag frequency, readiness, and knowledge graph views. | `backend/app/routers/performance.py`, `frontend/app/analytics/page.tsx`, `frontend/app/insights/page.tsx` |

## Tech Stack

### Frontend

- Next.js 16
- React 19
- TypeScript
- Tailwind CSS
- TanStack Query
- Zustand
- Supabase JavaScript client
- React Markdown, KaTeX, React Force Graph, XY Flow

### Backend

- FastAPI
- SQLAlchemy async
- asyncpg
- PostgreSQL
- pgvector
- Pydantic
- OpenAI Python SDK
- PyMuPDF, Pillow, python-pptx for file extraction
- json-repair, jsonschema, python-dateutil, httpx

## Quick Start

The repository has separate `frontend/` and `backend/` apps.

### 1. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The backend reads environment variables through `python-dotenv`.

Required or referenced backend variables found in the repo:

```bash
DATABASE_URL=postgresql+asyncpg://...
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=...
OPENAI_API_KEY=...
MOONSHOT_API_KEY=...
DEV_MODE=false
DEV_USER_ID=00000000-0000-0000-0000-000000000001
```

Notes:

- `DATABASE_URL` is required by `backend/app/db.py`.
- `SUPABASE_URL` and `SUPABASE_ANON_KEY` are required by backend auth unless `DEV_MODE` is enabled.
- `OPENAI_API_KEY` is used by LLM and file-extraction services.
- `MOONSHOT_API_KEY` is referenced by `backend/app/services/llm.py`.
- No safe root `.env.example` file exists in the repo at the time of writing.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend expects:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
```

`NEXT_PUBLIC_API_BASE_URL` defaults to `http://localhost:8000` in `frontend/lib/auth.ts`.

## Basic Usage

1. Start the backend.
2. Start the frontend.
3. Sign in through the Supabase-backed frontend flow.
4. Create or select a class.
5. Add notes or upload course material.
6. Extract concepts and generate practice.
7. Use Tutor or Homework flows for help.
8. Use Planner and Exam Lockdown for evidence-based exam preparation.

## Development Commands

Frontend commands are defined in `frontend/package.json`:

```bash
cd frontend
npm run dev
npm run lint
npm run build
npm run start
```

Backend commands are not defined in a package script file. The supported local run command follows the FastAPI app layout:

```bash
cd backend
uvicorn app.main:app --reload
```

## Testing Commands

No dedicated automated test command or test suite was found in the current repository.

Recommended validation from current repo support:

```bash
cd frontend
npm run lint
npm run build
```

Backend test setup is unknown from the current repo. There is no `pytest.ini`, test folder, or test dependency list visible.

## Build And Release Commands

Frontend build:

```bash
cd frontend
npm run build
```

Frontend production start after a successful build:

```bash
cd frontend
npm run start
```

Backend deployment/release commands are unknown from the current repo. No Dockerfile, CI workflow, deployment manifest, or process file was found.

## Project Structure Summary

```text
backend/
  app/
    main.py                 FastAPI entry point and router registration
    db.py                   async SQLAlchemy engine/session setup
    models.py               SQLAlchemy data model
    routers/                API route modules
    services/               auth, LLM, file extraction, planner, mastery, exam services
    jobs/                   background concept extraction job logic
  migrations/               SQL migrations for exam prep and lockdown tables
  *.md                      learning-system specs and prompt notes

frontend/
  app/                      Next.js route pages
  components/               UI and feature components
  lib/                      API client, auth helpers, Supabase client
  store/                    Zustand app state
  styles/                   global CSS
```

See [docs/FILE_MAP.md](docs/FILE_MAP.md) for a detailed map.

## Documentation

- [AI_CONTEXT.md](AI_CONTEXT.md)
- [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/SETUP.md](docs/SETUP.md)
- [docs/DEVELOPMENT_GUIDE.md](docs/DEVELOPMENT_GUIDE.md)
- [docs/FEATURES.md](docs/FEATURES.md)
- [docs/FILE_MAP.md](docs/FILE_MAP.md)
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
- [docs/CHANGELOG_STARTER.md](docs/CHANGELOG_STARTER.md)

## Current Status

In development / functional MVP. The codebase contains substantial app functionality, including Exam Lockdown, but production readiness is unknown from the current repo because automated tests, CI, deployment configuration, privacy policy, and security documentation are not present.

## License

License: Unknown from current repo.
