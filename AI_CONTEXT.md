# AI Context For College AI

This file is written for AI coding agents and future maintainers. Read it before making changes.

Related docs:

- [README.md](README.md)
- [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/SETUP.md](docs/SETUP.md)
- [docs/DEVELOPMENT_GUIDE.md](docs/DEVELOPMENT_GUIDE.md)
- [docs/FEATURES.md](docs/FEATURES.md)
- [docs/FILE_MAP.md](docs/FILE_MAP.md)
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
- [docs/CHANGELOG_STARTER.md](docs/CHANGELOG_STARTER.md)

## 1. Project Identity

Project name: College AI

One-sentence description: College AI is a full-stack AI study app that organizes class-specific learning data, extracts concepts, generates practice, tracks mastery, provides tutoring, and creates evidence-based exam prep plans.

Main purpose: Help students decide what to study next by connecting course materials, practice attempts, mastery, mistakes, planning, and tutoring.

Target users:

- College students studying across multiple classes.
- The original solo developer.
- Future maintainers.
- Recruiters/technical reviewers evaluating the project.
- AI coding agents working safely in the codebase.

Current status: In development / functional MVP. The repository contains substantial app functionality, but production readiness is unknown because automated tests, CI, deployment docs, privacy docs, and security docs are not present.

## 2. What This Project Does

College AI is a web app with a Next.js frontend and FastAPI backend. It is not just a stateless chatbot. It persists learning artifacts and uses them across workflows.

Core workflows:

1. User creates/selects a class.
2. User creates notes or uploads course material.
3. Backend extracts text and concepts.
4. Concepts support flashcards, practice generation, dependency graphs, and mastery.
5. User answers practice questions.
6. Backend records attempts, mistakes, confidence, and mastery changes.
7. Planner creates study schedules from class context.
8. Homework/Tutor flows use class concepts and saved pitfalls.
9. Exam Lockdown uses uploaded exam materials to generate evidence-based plans and tutor exact recommended questions.

Major features:

- Class/course management.
- Notes and uploads.
- Concept extraction.
- Flashcards.
- Practice and remedial practice.
- Step coaching and hints.
- Exam sessions.
- Mastery tracking.
- Homework tutor and work review.
- Pitfall storage.
- Study planner.
- Exam Lockdown / evidence-based exam prep.
- Analytics and insights.
- Blurting/mind-map frontend components.

Success for the project means:

- Students can understand their weak areas.
- Students can generate relevant practice.
- Students can see what to study next.
- Exam prep recommendations are tied to uploaded evidence.
- Tutor can teach selected questions with source context.

Do not misunderstand this project as:

- A generic chat-only wrapper.
- A static note-taking app.
- A production-hardened SaaS system.
- A fully tested system.
- A repository with complete deployment documentation.

## 3. Architecture Summary

### Main Components

```text
frontend/
  Next.js app routes
  React feature components
  typed API client
  Supabase client/auth fetch helpers
  Zustand state

backend/
  FastAPI app
  async SQLAlchemy DB layer
  routers by feature area
  services for LLM/extraction/mastery/planner/exam prep
  background concept extraction job
  SQL migrations for exam prep additions
```

### Entry Points

- Frontend layout: `frontend/app/layout.tsx`
- Frontend routes: `frontend/app/*/page.tsx`
- Frontend API client: `frontend/lib/api.ts`
- Frontend auth helpers: `frontend/lib/auth.ts`, `frontend/lib/supabaseClient.ts`
- Backend FastAPI app: `backend/app/main.py`
- Backend database setup: `backend/app/db.py`
- Backend models: `backend/app/models.py`

### Data Flow

Authenticated frontend requests:

1. Frontend gets Supabase session.
2. `frontend/lib/auth.ts` attaches Bearer token.
3. Backend `get_current_user_id` verifies token with Supabase unless `DEV_MODE=true`.
4. Backend route queries/mutates rows scoped by `user_id` and usually `class_id`.
5. Backend returns JSON to typed frontend API helpers.

Learning data flow:

```text
Notes/uploads
-> text extraction
-> concept extraction
-> concepts/flashcards
-> practice generation
-> attempts/mistakes
-> mastery/readiness
-> planner/tutor/analytics
```

Exam Lockdown data flow:

```text
Exam prep material upload
-> exam_prep_materials
-> explicit question extraction
-> exam_prep_extracted_questions
-> plan generation
-> exam_prep_plans + topic predictions + recommended questions
-> Tutor Exam Lockdown
-> exam coach response
-> attempts/progress/pitfalls
```

### State Flow

Frontend state:

- Server state: TanStack Query.
- Auth state: Supabase client.
- App state: Zustand in `frontend/store/useStore.ts`.

Important Zustand state:

- `selectedClassId`
- `selectedNoteId`
- `practice`
- `exam`
- `currentQuestion`
- `examTimer`
- `masteryProgress`

### Storage/Persistence

Persistent schema is modeled in `backend/app/models.py`.

Important data categories:

- User classes.
- Notes and concepts.
- Practice sets/questions/attempts.
- Mistake logs.
- Mastery and mastery history.
- Tutor/chat memories.
- Homework and exam pitfalls.
- Flashcards and flashcard sessions.
- Exam prep materials, extracted questions, plans, topic predictions, tasks, and recommended questions.
- Exam Lockdown sessions, attempts, and pitfalls.

Original uploaded file storage outside extracted database text is unknown from current repo.

### Background Processes

Background work uses FastAPI `BackgroundTasks`, especially `concept_extraction_job` in `backend/app/jobs/concept_jobs.py`.

Startup behavior in `backend/app/main.py` resets notes stuck in `queued` or `running` extraction states to `idle`.

No external queue, cron, scheduler, or worker process was found.

### External Integrations

- Supabase Auth.
- PostgreSQL.
- OpenAI SDK.
- Moonshot/Kimi API client reference.
- PyMuPDF/Pillow/python-pptx for file extraction.

### Permission-Sensitive Areas

This is a web app, not a browser extension or native app. No extension/native permission files were found.

Permission-sensitive behavior is application-level:

- Supabase auth.
- Backend user ID resolution.
- Class ownership checks.
- User/class scoped queries.

### Security-Sensitive Areas

- `backend/app/services/auth.py`
- `frontend/lib/auth.ts`
- `frontend/lib/supabaseClient.ts`
- `backend/app/db.py`
- `backend/.env`
- `frontend/.env.local`
- Upload and tutoring routes that process user content.

### Privacy-Sensitive Areas

The app can store:

- Notes and uploaded material text.
- Homework questions and user prompts.
- Chat memory.
- Mistakes and pitfalls.
- Attempts and confidence.
- Exam prep materials and extracted questions.

No privacy policy or retention policy was found.

## 4. Codebase Map For AI Agents

### Important Folders

| Path | What it controls |
| --- | --- |
| `frontend/app/` | Route-level pages. |
| `frontend/components/` | Feature UI and shared components. |
| `frontend/components/exam-prep/` | Planner Exam Lockdown setup and plan UI. |
| `frontend/components/exam-lockdown/` | Tutor Exam Lockdown mode. |
| `frontend/lib/api.ts` | Frontend/backend API contract. |
| `frontend/lib/auth.ts` | Authenticated fetch behavior and 401 handling. |
| `frontend/store/useStore.ts` | Global selected class/session state. |
| `backend/app/routers/` | API endpoints. |
| `backend/app/services/` | Business logic, LLM logic, extraction, mastery, planning. |
| `backend/app/models.py` | Persistent data model. |
| `backend/migrations/` | SQL schema changes. |

### Where To Make Common Changes

| Task | Likely files |
| --- | --- |
| Add frontend API call | `frontend/lib/api.ts` |
| Add page UI | `frontend/app/<route>/page.tsx`, `frontend/components/` |
| Add backend endpoint | relevant `backend/app/routers/*.py` |
| Add backend service logic | relevant `backend/app/services/*.py` |
| Change auth behavior | `frontend/lib/auth.ts`, `backend/app/services/auth.py` |
| Change selected class behavior | `frontend/store/useStore.ts`, `frontend/components/ClassSelector.tsx` |
| Change note extraction | `backend/app/routers/notes.py`, `backend/app/routers/uploads.py`, `backend/app/jobs/concept_jobs.py` |
| Change practice/mastery | `backend/app/routers/practice.py`, `backend/app/services/mastery.py` |
| Change homework tutor | `backend/app/routers/homework.py`, `frontend/components/TutorChat.tsx`, `frontend/app/tutor/page.tsx` |
| Change Exam Prep Planner | `backend/app/routers/exam_prep.py`, `backend/app/services/exam_prep.py`, `frontend/components/exam-prep/` |
| Change Tutor Exam Lockdown | `backend/app/routers/exam_lockdown.py`, `backend/app/services/exam_lockdown.py`, `frontend/components/exam-lockdown/` |
| Change DB schema | `backend/app/models.py`, `backend/migrations/`, serializers, `frontend/lib/api.ts` |

### Where Not To Make Casual Changes

Do not casually edit:

- `backend/app/services/auth.py`
- `backend/app/db.py`
- `backend/app/models.py`
- `backend/app/routers/classes.py`
- `backend/app/services/llm.py`
- `backend/app/services/file_extraction.py`
- `frontend/lib/api.ts`
- `frontend/lib/auth.ts`
- `frontend/lib/supabaseClient.ts`
- `frontend/store/useStore.ts`

### Generated Or Distribution Files To Avoid

Do not edit unless explicitly asked:

- `frontend/node_modules/`
- `frontend/.next/`
- `backend/venv/`
- `backend/.cache/`
- `__pycache__/`
- `.DS_Store`
- `frontend/tsconfig.tsbuildinfo`
- `College_AI_resume_audit_context/`
- `College_AI_resume_audit_context.zip`

## 5. Critical Behavior Rules

Only include rules supported by current repo evidence.

### Auth Rules

- Backend routes that read/write user data should use `Depends(get_current_user_id)`.
- Do not remove Supabase token verification.
- Do not broaden `DEV_MODE` usage.
- Do not treat `DEV_MODE` as production-safe.
- Frontend authenticated requests should keep using auth helpers or equivalent Bearer-token behavior.

### Class/User Scoping Rules

- Preserve `user_id` checks.
- Preserve `class_id` checks for class-scoped data.
- When adding routes, verify class ownership using the pattern in existing routers.
- Do not return cross-class data accidentally.
- Do not clear/delete data without class ownership verification.

### Data Integrity Rules

- Do not change persistent model fields without a migration and API update.
- Do not hard-delete recommendation-linked extracted questions in Exam Lockdown; current design uses `status` to preserve history.
- Do not create hallucinated Exam Lockdown recommendations. Recommended questions should link to persisted extracted question records.
- Do not break existing plan/recommendation response shapes expected by frontend components.

### LLM Rules

- Do not assume LLM responses are valid unless existing parsing/repair/validation handles that case.
- Preserve structured JSON expectations where services depend on them.
- Do not remove grounding/source context from tutor or exam prep flows.
- Do not add expensive OCR/vision calls to upload paths without being explicit about latency and cost.

### Privacy Rules

- Do not commit `.env` files.
- Do not log secrets.
- Be cautious with uploaded content, notes, homework questions, chat memory, pitfalls, and attempts.
- Avoid adding broad logging of full user content unless explicitly needed and reviewed.

### Backward Compatibility Rules

- Normal Tutor must remain usable when Exam Lockdown changes.
- Existing Planner behavior should remain usable when Exam Prep changes.
- Existing notes, homework, practice, flashcards, and analytics flows should not be broken by unrelated changes.
- Frontend API types should stay aligned with backend serializers.

## 6. AI Coding Instructions

Future AI agents should:

1. Read this file first.
2. Read `README.md` and `docs/ARCHITECTURE.md` before major changes.
3. Inspect the files directly involved in the request before editing.
4. Do not invent architecture, endpoints, environment variables, tests, or deployment details.
5. Do not remove auth, class scoping, data validation, or source-grounding logic.
6. Do not weaken restrictions without explicit user approval.
7. Do not change storage formats casually.
8. Do not break existing user data.
9. Preserve existing behavior unless the user explicitly requests a behavior change.
10. Prefer small, focused patches.
11. Update docs when behavior changes.
12. Run available validation commands or explain why they could not run.
13. Explain assumptions clearly.
14. Mark unknowns as unknown instead of guessing.

## 7. Common Modification Guide

### To add a feature

Inspect:

- Similar frontend page/component.
- Relevant backend router.
- Relevant service module.
- `frontend/lib/api.ts`.
- `backend/app/models.py` if persistence is needed.

### To change UI

Inspect:

- Route page in `frontend/app/`.
- Feature components in `frontend/components/`.
- Shared primitives in `frontend/components/ui/`.
- Global styling in `frontend/styles/globals.css`.

Do not change backend unless the UI needs new data or behavior.

### To change storage

Inspect:

- `backend/app/models.py`
- `backend/migrations/`
- Serializers in relevant backend routers.
- Types in `frontend/lib/api.ts`.
- Class clear/delete logic in `backend/app/routers/classes.py`.

Add migration files rather than silently relying on model changes.

### To change auth

Inspect:

- `backend/app/services/auth.py`
- `frontend/lib/auth.ts`
- `frontend/lib/supabaseClient.ts`
- `frontend/components/RequireAuth.tsx`

Do not weaken auth behavior unless explicitly requested.

### To change LLM behavior

Inspect:

- `backend/app/services/llm.py`
- `backend/app/services/exam_prep.py`
- `backend/app/services/exam_lockdown.py`
- Prompt/spec docs in `backend/*.md`

Preserve response formats expected by downstream code.

### To change file extraction

Inspect:

- `backend/app/services/file_extraction.py`
- `backend/app/routers/uploads.py`
- `backend/app/routers/exam_prep.py`

Be explicit about whether a path calls vision OCR or an LLM.

### To change Exam Lockdown

Inspect:

- `backend/app/routers/exam_prep.py`
- `backend/app/services/exam_prep.py`
- `backend/app/routers/exam_lockdown.py`
- `backend/app/services/exam_lockdown.py`
- `frontend/components/exam-prep/`
- `frontend/components/exam-lockdown/`
- `frontend/lib/api.ts`

Regression checks:

- Upload materials.
- Extract questions.
- Generate plan with recommendations.
- Open Tutor Exam Lockdown.
- Select and coach a question.
- Save attempt/progress.
- Re-extract material and confirm old recommendations do not disappear unexpectedly.

### To change tests

No test suite exists. If adding tests, first decide where they belong:

- Frontend component/unit tests: unknown framework from current repo.
- Backend API/service tests: unknown framework from current repo.

Do not invent a test setup without adding the needed dependencies/config intentionally.

### To change release/package behavior

Unknown from current repo. No Docker, CI, Vercel config, or backend deployment manifest was found. Ask the user before adding release infrastructure.

## 8. Testing And Validation

Existing frontend validation commands:

```bash
cd frontend
npm run lint
npm run build
```

Existing backend run command supported by app layout:

```bash
cd backend
uvicorn app.main:app --reload
```

Health check:

```bash
curl http://localhost:8000/health
```

No automated tests were found.

### Manual Regression Checklist

After changes, manually check affected areas. For broad changes, check:

1. Login/auth flow.
2. Class creation and selection.
3. Notes page loads selected class data.
4. Note upload and extraction status.
5. Concept/flashcard display.
6. Practice generation and attempt submission.
7. Tutor normal mode.
8. Homework pitfalls and clear behavior.
9. Planner page.
10. Exam Lockdown material upload/extraction/plan generation.
11. Tutor Exam Lockdown recommendation display, coach response, attempt save.
12. Analytics pages that use practice endpoints.

### Areas Needing Extra Caution

- Auth.
- Class deletion/clear.
- LLM JSON parsing.
- File extraction and OCR.
- Exam Lockdown recommendation persistence.
- Database schema changes.
- Frontend API response types.

## 9. Known Unknowns

| Unknown | What would resolve it |
| --- | --- |
| Production deployment target | Deployment docs, Dockerfile, CI workflow, hosting config, or author input. |
| Complete database migration history | Base schema migrations or Supabase migration history. |
| Automated test strategy | Test folders, test framework config, or author input. |
| Supported Python version | Runtime docs, `.python-version`, `pyproject.toml`, or deployment config. |
| License | `LICENSE` file or author input. |
| Privacy/data retention policy | Privacy docs or product policy docs. |
| Original file storage strategy | Storage service code/config or author input. |
| Observability/logging setup | Logging config, deployment docs, or monitoring integration files. |
| Production CORS policy | Deployment config or explicit backend settings for production. |
| Exact status of blurting/mind-map feature | Product docs or backend persistence docs. |

## 10. Suggested First Prompt For Future AI Work

“Before making changes, read AI_CONTEXT.md, README.md, docs/ARCHITECTURE.md, and the files directly involved in my request. Then explain the relevant current behavior, identify the safest files to edit, make the smallest correct patch, and update documentation if behavior changes.”
