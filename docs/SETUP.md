# Setup Guide

This guide describes what can be verified from the current repository. Deployment-specific setup is unknown because no Dockerfile, CI workflow, process file, or deployment manifest was found.

## Prerequisites

### Frontend

- Node.js compatible with Next.js 16.
- npm, because `frontend/package-lock.json` is present.

### Backend

- Python 3.
- PostgreSQL database reachable through an async SQLAlchemy URL.
- Environment variables for database, Supabase auth, and LLM services.

## Repository Layout

```text
College_AI/
  backend/
  frontend/
  docs/
  README.md
  AI_CONTEXT.md
```

## Backend Installation

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Backend dependencies are listed in `backend/requirements.txt`.

## Backend Environment Variables

The backend uses `python-dotenv` and reads environment variables in these files:

- `backend/app/db.py`
- `backend/app/services/auth.py`
- `backend/app/services/llm.py`
- `backend/app/services/file_extraction.py`

Variables referenced in the repo:

| Variable | Required? | Used by | Notes |
| --- | --- | --- | --- |
| `DATABASE_URL` | Yes | `backend/app/db.py` | Must be an async SQLAlchemy-compatible Postgres URL, for example `postgresql+asyncpg://...`. |
| `SUPABASE_URL` | Required unless `DEV_MODE=true` | `backend/app/services/auth.py` | Used to verify Bearer tokens. |
| `SUPABASE_ANON_KEY` | Required unless `DEV_MODE=true` | `backend/app/services/auth.py` | Sent as Supabase `apikey` header. |
| `DEV_MODE` | Optional | `backend/app/services/auth.py` | If truthy, bypasses Supabase verification and uses `DEV_USER_ID`. |
| `DEV_USER_ID` | Optional | `backend/app/services/auth.py` | Defaults to `00000000-0000-0000-0000-000000000001`. |
| `OPENAI_API_KEY` | Required for LLM/file vision paths | `backend/app/services/llm.py`, `backend/app/services/file_extraction.py` | Used by OpenAI SDK clients. |
| `MOONSHOT_API_KEY` | Referenced | `backend/app/services/llm.py` | Used by a Moonshot/Kimi client. Exact required paths depend on feature usage. |

The repository currently contains local env files (`backend/.env`, `frontend/.env.local`) that should not be committed. No committed `.env.example` file was found.

## Backend Database Setup

SQL migrations found:

- `backend/migrations/20260506_exam_prep_planner.sql`
- `backend/migrations/20260512_exam_lockdown_materials.sql`
- `backend/migrations/20260515_exam_prep_extracted_question_status.sql`

These files include comments saying to apply them manually against the same Postgres database used by `DATABASE_URL`.

Unknown from current repo:

- Complete base schema migration history for tables like `classes`, `notes`, `concepts`, and practice tables.
- Whether migrations are managed by Alembic, Supabase SQL editor, or another workflow.

## Running The Backend

The FastAPI app is defined at `backend/app/main.py`.

```bash
cd backend
uvicorn app.main:app --reload
```

Health check:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"ok": true}
```

## Frontend Installation

```bash
cd frontend
npm install
```

## Frontend Environment Variables

Variables referenced by the frontend:

| Variable | Required? | Used by | Notes |
| --- | --- | --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | Optional | `frontend/lib/auth.ts` | Defaults to `http://localhost:8000`. |
| `NEXT_PUBLIC_SUPABASE_URL` | Yes | `frontend/lib/supabaseClient.ts` | Missing value throws at runtime. |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Yes | `frontend/lib/supabaseClient.ts` | Missing value throws at runtime. |

## Running The Frontend

```bash
cd frontend
npm run dev
```

The default Next.js dev URL is normally `http://localhost:3000`.

## Frontend Commands

Defined in `frontend/package.json`:

```bash
npm run dev
npm run lint
npm run build
npm run start
```

## Running Tests

No dedicated automated test suite or test command was found.

Use available validation:

```bash
cd frontend
npm run lint
npm run build
```

Backend test command: Unknown from current repo.

## Common Setup Mistakes

### `DATABASE_URL missing in .env`

Source: `backend/app/db.py`.

Fix:

- Define `DATABASE_URL` before starting the backend.
- Use a URL supported by SQLAlchemy asyncpg, typically `postgresql+asyncpg://...`.

### `Auth is not configured`

Source: `backend/app/services/auth.py`.

Fix:

- Define `SUPABASE_URL` and `SUPABASE_ANON_KEY`, or use `DEV_MODE=true` for local-only development if that is acceptable for your workflow.

### Missing Supabase frontend env vars

Source: `frontend/lib/supabaseClient.ts`.

Fix:

- Define `NEXT_PUBLIC_SUPABASE_URL`.
- Define `NEXT_PUBLIC_SUPABASE_ANON_KEY`.

### Frontend points to the wrong API

Source: `frontend/lib/auth.ts`.

Fix:

- Set `NEXT_PUBLIC_API_BASE_URL` if the backend is not running on `http://localhost:8000`.

### Exam prep tables missing

Source: `backend/migrations/`.

Fix:

- Apply the exam prep SQL migrations.
- Confirm base tables such as `classes` also exist.

### LLM calls fail

Likely causes:

- `OPENAI_API_KEY` missing or invalid.
- `MOONSHOT_API_KEY` missing for code paths that use `kimi_client`.
- Network/API access unavailable.
- JSON returned by an LLM does not match expected schema.

## Platform-Specific Notes

No iOS, macOS, desktop, browser extension, native messaging, or mobile packaging setup was found.

## Troubleshooting Links

- [Troubleshooting](TROUBLESHOOTING.md)
- [Architecture](ARCHITECTURE.md)
- [Development Guide](DEVELOPMENT_GUIDE.md)
