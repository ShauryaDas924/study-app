# File Map

This map identifies important files/folders and how future maintainers or AI agents should treat them.

## Top-Level

| Path | Type | Purpose | Edit guidance |
| --- | --- | --- | --- |
| `README.md` | Documentation | Main project README. | Edit when setup, features, status, or docs links change. |
| `AI_CONTEXT.md` | Documentation | AI-agent-specific project context. | Keep current with architecture and critical behavior. |
| `docs/` | Documentation | Project docs. | Edit only Markdown docs here. |
| `backend/` | Source/config/docs | FastAPI backend. | Edit carefully; preserve auth and data scoping. |
| `frontend/` | Source/config/docs | Next.js frontend. | Edit carefully; preserve API contracts and auth flows. |
| `College_AI_resume_audit_context/` | Generated audit artifact | Lightweight context folder created for resume/portfolio review. | Do not treat as source. Avoid editing unless regenerating audit context intentionally. |
| `College_AI_resume_audit_context.zip` | Generated archive | ZIP of audit context. | Do not edit manually. |

## Backend

| Path | Type | Purpose | Edit guidance |
| --- | --- | --- | --- |
| `backend/requirements.txt` | Config | Python dependencies. | Do not change unless adding/removing backend dependencies. |
| `backend/.env` | Local secret config | Local backend environment variables. | Do not commit or include in docs output. |
| `backend/app/main.py` | Source | FastAPI app, CORS, startup reset, router registration. | Be careful with CORS and router registration. |
| `backend/app/db.py` | Source/security-sensitive | Database URL, async engine, session dependency, rollback/close behavior. | High risk. Preserve connection/session cleanup. |
| `backend/app/models.py` | Source/schema | SQLAlchemy ORM models for all persistent data. | High risk. Pair changes with migrations and serializers. |
| `backend/app/routers/` | Source | API route modules by feature area. | Add endpoints in the relevant router; preserve auth/class checks. |
| `backend/app/services/` | Source | Auth, LLM, extraction, mastery, planner, exam services. | Keep substantial business logic here when possible. |
| `backend/app/jobs/` | Source | Background concept extraction job logic. | Be careful with job status and note extraction fields. |
| `backend/migrations/` | Database migration | SQL migrations for exam prep/lockdown. | Add idempotent migrations for schema changes. |
| `backend/*.md` | Documentation/spec | Learning system specs and prompt guidance. | Preserve useful product/prompt context. |
| `backend/*.json` | Schema/config | Practice question schema. | Keep in sync with LLM prompt expectations. |
| `backend/backfill_embeddings.py` | Script | Backfill script for embeddings. | Inspect before running; may require env/database access. |
| `backend/venv/` | Generated/local environment | Python virtual environment. | Do not edit or commit. |
| `backend/.cache/` | Generated/cache | Local cache. | Do not edit or commit. |

## Backend Routers

| Path | Type | Purpose | Edit guidance |
| --- | --- | --- | --- |
| `backend/app/routers/classes.py` | Source/data integrity | Class create/list/clear/delete. | High risk because clear/delete touches many tables. |
| `backend/app/routers/notes.py` | Source | Note CRUD and extraction job start/status. | Preserve background task status behavior. |
| `backend/app/routers/uploads.py` | Source | File upload to note creation and concept extraction queue. | Be careful with file bytes, extraction, and LLM cost. |
| `backend/app/routers/concepts.py` | Source | Concepts and flashcards. | Keep note/class scoping. |
| `backend/app/routers/practice.py` | Source | Practice, attempts, exams, analytics, flashcards. | High complexity; inspect nearby code before changes. |
| `backend/app/routers/homework.py` | Source | Homework help, chat history, work review, pitfalls. | Privacy-sensitive because it stores user prompts/history/pitfalls. |
| `backend/app/routers/plan.py` | Source | Daily/weekly planner generation. | Keep response shapes compatible with frontend. |
| `backend/app/routers/exam_prep.py` | Source/high-risk | Exam prep materials, question extraction, plans, recommendations, tasks. | Preserve recommendation grounding and class/user scoping. |
| `backend/app/routers/exam_lockdown.py` | Source/high-risk | Exam Lockdown sessions, tutor, attempts, progress. | Preserve selected-question context and attempt/pitfall integrity. |
| `backend/app/routers/performance.py` | Source | Exam performance analysis. | Verify class/user scoping. |

## Backend Services

| Path | Type | Purpose | Edit guidance |
| --- | --- | --- | --- |
| `backend/app/services/auth.py` | Source/security-sensitive | Supabase token verification and dev bypass. | Do not weaken auth without explicit approval. |
| `backend/app/services/llm.py` | Source/LLM | LLM clients, prompts, generation helpers. | High risk. Preserve output schemas and parsing. |
| `backend/app/services/file_extraction.py` | Source/LLM/file handling | PDF/text/PPT/image extraction and optional vision OCR. | Be careful with cost, latency, and uploaded content privacy. |
| `backend/app/services/mastery.py` | Source/learning model | Mastery updates and forgetting. | Keep learning model changes deliberate and documented. |
| `backend/app/services/planner.py` | Source | Planner helper logic. | Preserve frontend response expectations. |
| `backend/app/services/exam_prep.py` | Source/high-risk | Exam prep extraction/ranking/recommendations/day plan logic. | Do not allow hallucinated recommendations. |
| `backend/app/services/exam_lockdown.py` | Source/high-risk | Exam coach prompt and pitfall extraction. | Preserve structured coach method and source context. |

## Frontend

| Path | Type | Purpose | Edit guidance |
| --- | --- | --- | --- |
| `frontend/package.json` | Config | Node dependencies and scripts. | Do not change unless dependency/scripts change intentionally. |
| `frontend/package-lock.json` | Lockfile | npm dependency lock. | Do not edit manually. |
| `frontend/.env.local` | Local secret config | Frontend env values. | Do not commit. |
| `frontend/next.config.ts` | Config | Next.js config. | Change only for framework/build needs. |
| `frontend/tailwind.config.ts` | Config | Tailwind config. | Change only for design system needs. |
| `frontend/tsconfig.json` | Config | TypeScript config. | Change carefully; may affect all frontend typing. |
| `frontend/styles/globals.css` | Source/style | Global styles and app theme. | Avoid broad visual changes unless intended. |
| `frontend/app/` | Source/routes | Next.js pages. | Page-level layout and feature assembly. |
| `frontend/components/` | Source/components | Feature and shared components. | Prefer focused feature components. |
| `frontend/lib/api.ts` | Source/API contract | Typed backend API client. | High risk. Keep synchronized with backend responses. |
| `frontend/lib/auth.ts` | Source/security-sensitive | Auth fetch, token headers, login redirect. | Do not weaken auth/redirect logic casually. |
| `frontend/lib/supabaseClient.ts` | Source/security-sensitive | Supabase client initialization. | Requires public Supabase env vars. |
| `frontend/store/useStore.ts` | Source/state | Global Zustand state. | Preserve selected class/session behavior. |
| `frontend/public/` | Assets | Static SVG assets. | Not central to architecture; avoid heavy generated assets. |
| `frontend/node_modules/` | Generated/dependencies | Installed packages. | Do not edit or commit. |
| `frontend/.next/` | Build output | Next.js build/dev output. | Do not edit or commit. |

## Frontend Feature Areas

| Path | Type | Purpose | Edit guidance |
| --- | --- | --- | --- |
| `frontend/components/exam-prep/` | Source/components | Planner Exam Lockdown setup, materials, plan display. | Preserve upload/extract/generate workflows. |
| `frontend/components/exam-lockdown/` | Source/components | Tutor Exam Lockdown mode and coach response. | Preserve normal Tutor default behavior. |
| `frontend/components/blurting-mindmap/` | Source/components/style | Blurting/mind-map feature UI. | Inspect behavior before changing; backend support unclear. |
| `frontend/components/ui/` | Source/components | Button, card, input, progress, select, tag primitives. | Keep compatible with existing pages. |

## Generated Or Local Files To Avoid

- `.DS_Store`
- `__pycache__/`
- `.next/`
- `node_modules/`
- `backend/venv/`
- `backend/.cache/`
- `frontend/tsconfig.tsbuildinfo`
- `College_AI_resume_audit_context/`
- `College_AI_resume_audit_context.zip`

## Security/Privacy-Sensitive Files

- `backend/.env`
- `frontend/.env.local`
- `backend/app/services/auth.py`
- `frontend/lib/auth.ts`
- `frontend/lib/supabaseClient.ts`
- `backend/app/db.py`
- Upload and tutoring routes that process user educational content:
  - `backend/app/routers/uploads.py`
  - `backend/app/routers/homework.py`
  - `backend/app/routers/exam_prep.py`
  - `backend/app/routers/exam_lockdown.py`
