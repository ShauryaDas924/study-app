# Development Guide

This guide is for developers and AI coding agents working on College AI.

## Working Principles

- Read [AI_CONTEXT.md](../AI_CONTEXT.md) before making non-trivial changes.
- Preserve user/class scoping.
- Preserve authenticated request behavior.
- Inspect existing route/service/component patterns before adding new ones.
- Keep patches focused.
- Do not change storage formats or schema casually.
- Do not commit local env files, dependency folders, build outputs, caches, or generated audit artifacts.
- Update docs when behavior changes.

## Coding Conventions Inferred From The Repo

### Frontend

- Uses Next.js App Router with route files under `frontend/app/**/page.tsx`.
- Uses `"use client"` for interactive components.
- Uses TypeScript interfaces in `frontend/lib/api.ts` for API payloads and responses.
- Uses TanStack Query for server state in many components.
- Uses Zustand in `frontend/store/useStore.ts` for selected class and session state.
- Uses small shared UI primitives in `frontend/components/ui/`.
- Uses Tailwind CSS classes and global theme styles in `frontend/styles/globals.css`.

### Backend

- Uses FastAPI routers by feature area under `backend/app/routers/`.
- Uses async SQLAlchemy sessions through `Depends(get_db)`.
- Uses `Depends(get_current_user_id)` for auth.
- Uses `HTTPException` for API errors.
- Uses SQLAlchemy ORM models in `backend/app/models.py`.
- Uses service modules for LLM, planner, file extraction, mastery, and exam prep logic.
- Uses manual SQL migration files in `backend/migrations/` for exam prep additions.

## Where To Add New Features

| Change type | Start by inspecting |
| --- | --- |
| New frontend route | `frontend/app/`, `frontend/components/Navbar.tsx`, `frontend/components/RequireAuth.tsx` |
| New API client function | `frontend/lib/api.ts` |
| New shared UI | `frontend/components/ui/` and existing feature components |
| New backend endpoint | Relevant `backend/app/routers/*.py` file |
| New backend business logic | Relevant `backend/app/services/*.py` file |
| New persistent data | `backend/app/models.py` and migrations |
| New class-scoped feature | `backend/app/routers/classes.py`, auth/class checks in existing routers |
| New Exam Lockdown behavior | `backend/app/routers/exam_prep.py`, `backend/app/services/exam_prep.py`, `frontend/components/exam-prep/`, `frontend/components/exam-lockdown/` |
| New Tutor behavior | `backend/app/routers/homework.py`, `frontend/components/TutorChat.tsx`, `frontend/app/tutor/page.tsx` |
| New practice behavior | `backend/app/routers/practice.py`, `backend/app/services/mastery.py`, `frontend/components/Practice*` |

## Where Not To Add Features Casually

Avoid casual edits in these high-risk areas:

- `backend/app/db.py`: database engine/session lifecycle.
- `backend/app/services/auth.py`: auth enforcement and dev bypass.
- `backend/app/models.py`: persistent schema contracts.
- `backend/app/routers/classes.py`: class deletion/clear behavior.
- `backend/app/services/llm.py`: prompt contracts and JSON parsing.
- `backend/app/services/file_extraction.py`: file parsing and optional vision OCR behavior.
- `frontend/lib/api.ts`: frontend/backend API contract.
- `frontend/lib/auth.ts`: auth headers and unauthorized redirects.
- `frontend/store/useStore.ts`: global UI/session state.

## Debugging

### Backend

- Start with `uvicorn app.main:app --reload`.
- Check endpoint-level errors in terminal logs.
- Use `/health` to verify the app is running.
- Check auth failures against `backend/app/services/auth.py`.
- Check database connection failures against `backend/app/db.py`.
- Check extraction and LLM failures in `backend/app/services/file_extraction.py` and `backend/app/services/llm.py`.

### Frontend

- Start with `npm run dev`.
- Inspect network calls made through `frontend/lib/api.ts`.
- Auth redirects are controlled by `frontend/lib/auth.ts`.
- Missing Supabase env vars throw from `frontend/lib/supabaseClient.ts`.
- Use React Query state and component-level mutation errors for debugging UI failures.

## Testing Changes

No test suite was found. Use the available validation commands:

```bash
cd frontend
npm run lint
npm run build
```

Manual validation should cover any touched feature. For backend changes, run the backend and exercise affected endpoints manually or through a small client script.

## Common Development Workflows

### Add a backend route

1. Inspect the closest existing router.
2. Add request/response Pydantic models if needed.
3. Use `Depends(get_db)` and `Depends(get_current_user_id)`.
4. Verify class ownership for class-scoped data.
5. Keep business logic in services if it is substantial.
6. Add a typed frontend API helper in `frontend/lib/api.ts`.
7. Update docs if behavior changes.

### Add a frontend feature

1. Identify the page under `frontend/app/`.
2. Add or update focused components under `frontend/components/`.
3. Use existing UI primitives where possible.
4. Use `frontend/lib/api.ts` instead of ad hoc fetch calls when practical.
5. Preserve normal mode/default behavior for pages with multiple modes, such as Tutor.
6. Validate with lint/build.

### Change database schema

1. Inspect `backend/app/models.py`.
2. Add an idempotent migration under `backend/migrations/`.
3. Preserve existing data where possible.
4. Update serializers and API types.
5. Update docs and manual verification steps.

## Review Checklist Before Committing

- Did the change preserve auth and class scoping?
- Did the change avoid committing `.env`, `.next`, `node_modules`, `venv`, `__pycache__`, or generated audit ZIPs?
- Did the change avoid weakening safety or evidence-grounding logic?
- Did frontend API types still match backend responses?
- Did any schema change include a migration?
- Did docs change if behavior changed?
- Did `npm run lint` and `npm run build` pass, or are failures documented?
- Are unknowns called out instead of guessed?

## Documentation Expectations

Update documentation when changing:

- Setup commands or env variables.
- Auth behavior.
- Database schema.
- API routes or response shapes.
- Exam Lockdown workflow.
- LLM prompt contracts.
- File upload/extraction behavior.
- Testing/deployment workflow.
