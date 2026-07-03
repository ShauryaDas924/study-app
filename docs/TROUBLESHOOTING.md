# Troubleshooting

This guide covers problems that can be inferred from the current repository.

## Backend Startup

### `DATABASE_URL missing in .env`

Source: `backend/app/db.py`.

Cause:

- `DATABASE_URL` is not defined in the backend environment.

Fix:

```bash
cd backend
# define DATABASE_URL in your shell or backend/.env
uvicorn app.main:app --reload
```

Use an async PostgreSQL URL such as:

```text
postgresql+asyncpg://USER:PASSWORD@HOST:5432/DATABASE
```

### Backend cannot authenticate requests

Possible errors:

- `Missing Bearer token`
- `Invalid or expired token`
- `Auth is not configured`

Sources:

- `backend/app/services/auth.py`
- `frontend/lib/auth.ts`

Fix:

- Ensure frontend is sending a Supabase session token.
- Ensure backend has `SUPABASE_URL` and `SUPABASE_ANON_KEY`.
- For local-only bypass, set `DEV_MODE=true` and a valid `DEV_USER_ID`. Use this carefully.

### Database connection issues

Source: `backend/app/db.py`.

Checks:

- Confirm `DATABASE_URL`.
- Confirm database is reachable.
- Confirm required tables exist.
- Confirm exam prep SQL migrations were applied if using Exam Lockdown.

The engine uses `NullPool`, `pool_pre_ping=True`, connection timeout, and statement timeout settings. This appears designed for hosted Postgres poolers.

## Frontend Startup

### Missing Supabase env vars

Source: `frontend/lib/supabaseClient.ts`.

Error:

```text
Missing Supabase env vars. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.
```

Fix:

- Define `NEXT_PUBLIC_SUPABASE_URL`.
- Define `NEXT_PUBLIC_SUPABASE_ANON_KEY`.

### Frontend calls wrong backend URL

Source: `frontend/lib/auth.ts`.

Default:

```text
http://localhost:8000
```

Fix:

- Set `NEXT_PUBLIC_API_BASE_URL` to the backend URL.

### 401 redirects to login

Source: `frontend/lib/auth.ts`.

Behavior:

- `authFetch` signs out and redirects to `/login` on 401.

Fix:

- Check Supabase session.
- Check backend Supabase env vars.
- Check token expiration.

## Install Issues

### Frontend dependency install

Use npm because `frontend/package-lock.json` is present:

```bash
cd frontend
npm install
```

Unknown from current repo:

- pnpm/yarn support.

### Backend dependency install

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

If `PyMuPDF`, `Pillow`, or `python-pptx` fail to install, check Python version and platform-specific package requirements. Exact supported Python version is unknown from current repo.

## Build And Lint Issues

Frontend commands:

```bash
cd frontend
npm run lint
npm run build
```

No backend lint/build script was found.

## Upload And Extraction Issues

### Uploaded file has no text

Source: `backend/app/routers/uploads.py`.

Behavior:

- Upload returns a 400 if no text could be extracted.

Fix:

- Try a text-based PDF, TXT, Markdown, or supported PPT file.
- For image/PDF OCR paths, verify `OPENAI_API_KEY` if vision OCR is used.

### PDF math/OCR is slow or incomplete

Source: `backend/app/services/file_extraction.py`.

Possible causes:

- PDF text extraction is poor.
- Vision OCR path is disabled or unavailable.
- LLM/API credentials are missing.

Fix:

- Confirm whether the route allows vision OCR.
- Confirm `OPENAI_API_KEY`.
- Try a cleaner source file.

## Concept Extraction Issues

Sources:

- `backend/app/routers/notes.py`
- `backend/app/jobs/concept_jobs.py`
- `backend/app/services/llm.py`

Checks:

- Note exists and belongs to current user.
- Extraction is not already queued/running.
- LLM key is configured.
- Backend logs show job progress.

Startup behavior:

- `backend/app/main.py` resets notes stuck in `queued` or `running` to `idle` with an error that the server restarted before extraction finished.

## Exam Lockdown Issues

### Materials upload but no recommendations appear

Check:

1. Materials exist for selected class.
2. Questions were extracted from selected materials.
3. Plan generation completed after extraction.
4. `exam_prep_recommended_questions` rows exist for the plan.
5. Tutor is loading the active plan and `/plan/exam-prep/plans/{plan_id}/questions`.

Important files:

- `backend/app/routers/exam_prep.py`
- `frontend/components/exam-prep/ExamPrepMaterialsList.tsx`
- `frontend/components/exam-lockdown/ExamLockdownTutorMode.tsx`

### Plan generation blocked by missing extracted questions

Source: `backend/app/routers/exam_prep.py`.

Behavior:

- The request model includes `allow_no_recommendations`, defaulting to false.
- Plan generation is intended to use persisted extracted question IDs for recommendations.

Fix:

- Extract questions from selected evidence first.
- Regenerate the plan.

### Re-extraction could affect old plans

Source:

- `backend/migrations/20260515_exam_prep_extracted_question_status.sql`
- `backend/app/routers/exam_prep.py`

Current design:

- Extracted questions can have `status`.
- Stale status helps preserve old recommendation links.

Regression check:

- After re-extracting a material, old plans should still show their saved recommended questions or stale source status.

## Practice/Mastery Issues

Sources:

- `backend/app/routers/practice.py`
- `backend/app/services/mastery.py`

Checks:

- Selected class has concepts.
- Generated questions are persisted.
- Attempts include concept IDs where required.
- Mastery rows exist for concepts being updated.

## No Test Suite Found

No test folders or `*.test.*` / `*.spec.*` files were found.

Use manual validation plus:

```bash
cd frontend
npm run lint
npm run build
```

Backend automated validation is unknown from current repo.

## Packaging/Release Issues

Unknown from current repo:

- Production deployment command.
- CI/CD provider.
- Docker setup.
- Vercel configuration.
- Backend hosting platform.
- Release process.

## Debugging Checklist

1. Confirm selected class in UI.
2. Confirm auth session exists.
3. Confirm frontend API base URL.
4. Confirm backend `/health`.
5. Confirm database env and migrations.
6. Confirm user/class ownership checks.
7. Confirm LLM keys for LLM-backed features.
8. Confirm relevant rows exist in database.
9. Read browser network response bodies.
10. Read backend terminal logs.

## Log Locations

Unknown from current repo. The backend uses `print` statements in several places. No structured logging or external log sink was found.
