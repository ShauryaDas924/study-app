# Local setup

College AI has separate `backend/` and `frontend/` applications. CI uses Python 3.12 and Node.js 22; those are the recommended local versions.

## Prerequisites

- Python 3.12
- Node.js 22 and npm
- PostgreSQL with the `pgvector` extension
- A Supabase project for the normal browser login flow
- OpenAI and Moonshot API keys for the complete AI-backed feature set

## Database prerequisite

The repository does **not** contain a complete base-schema migration. It includes SQLAlchemy model declarations and these incremental migrations only:

1. `backend/migrations/20260506_exam_prep_planner.sql`
2. `backend/migrations/20260512_exam_lockdown_materials.sql`
3. `backend/migrations/20260515_exam_prep_extracted_question_status.sql`

There is no startup `create_all` call. A blank PostgreSQL database therefore cannot be initialized solely from this repository. Obtain a compatible baseline schema from the owner, then apply the incremental SQL files in order using your normal database administration tool. Do not apply them blindly to an unrelated database.

This is the largest reproducibility gap in the archived MVP.

## Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install --requirement requirements-dev.txt
cp .env.example .env
```

Edit `backend/.env` with values from accounts you control. Never commit that file.

### Backend environment

| Variable | Requirement | Purpose |
| --- | --- | --- |
| `APP_ENV` | Recommended | Runtime classification. Defaults to `production`; use `development` locally or `test` in tests. |
| `DATABASE_URL` | Required | Async SQLAlchemy URL, normally `postgresql+asyncpg://...`. |
| `SUPABASE_URL` | Required for normal auth | Supabase project URL used for token validation. |
| `SUPABASE_ANON_KEY` | Required for normal auth | Public/anonymous client key used with the bearer token. Never substitute a service-role key. |
| `OPENAI_API_KEY` | Full app | OpenAI models, embeddings, and vision extraction. Provider clients are currently initialized during module import, so set this for a normal API run. |
| `MOONSHOT_API_KEY` | Full app | Moonshot/Kimi-compatible model calls. Also currently initialized during module import. |
| `CORS_ORIGINS` | Optional | Comma-separated browser origins. Defaults to local ports `localhost:3000` and `127.0.0.1:3000`; wildcard is rejected. |
| `MAX_UPLOAD_BYTES` | Optional | Per-upload byte limit; default 10 MiB, allowed range 1 byte–50 MiB. |
| `MAX_PDF_PAGES` | Optional | PDF page cap; default 100, allowed range 1–500. |
| `MAX_VISION_OCR_PAGES` | Optional | Maximum pages sent through vision OCR; default 10, allowed range 0–50. |
| `MAX_IMAGE_PIXELS` | Optional | Image pixel cap; default 25,000,000. |
| `MAX_ARCHIVE_UNCOMPRESSED_BYTES` | Optional | Expanded presentation/archive cap; default 100 MiB. |
| `CONCEPT_CHUNK_CONCURRENCY` | Optional | Concurrent chunk-level concept calls, from 1 to 20; default 3. Heavy note jobs are still serialized per API process. |
| `ENABLE_REFINEMENT_CACHE` | Optional | Enables the process-local refinement cache when `true`; default `false`. |
| `DEV_MODE` | Development only | Fixed-user backend auth bypass. Defaults `false` and is rejected outside `development`/`test`. |
| `DEV_USER_ID` | With `DEV_MODE` | Valid UUID returned by the bypass. |

Use placeholders only for deterministic tests. A placeholder provider key does not make live AI features work.

### Development authentication

The normal and recommended path is Supabase login. For isolated backend/API work, the bypass can be enabled deliberately:

```dotenv
APP_ENV=development
DEV_MODE=true
DEV_USER_ID=00000000-0000-0000-0000-000000000001
```

The browser app still initializes Supabase and protects its authenticated routes, so this bypass does not replace the frontend login experience. Never enable it on a shared host or internet-facing environment.

### Start the API

```bash
uvicorn app.main:app --reload
```

Check `http://localhost:8000/health`. Interactive OpenAPI documentation is available at `http://localhost:8000/docs` while the development server is running.

## Frontend

```bash
cd frontend
npm ci
cp .env.example .env.local
```

Edit `frontend/.env.local`:

| Variable | Requirement | Purpose |
| --- | --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | Recommended | FastAPI origin; defaults to `http://localhost:8000`. |
| `NEXT_PUBLIC_SUPABASE_URL` | Required | Browser-visible Supabase project URL. |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Required | Browser-visible public/anonymous key. Never put service-role or secret keys in a `NEXT_PUBLIC_*` variable. |

Then start Next.js:

```bash
npm run dev
```

Open `http://localhost:3000`. Ensure the same origin appears in backend `CORS_ORIGINS`.

## Supported uploads and limits

| Workflow | Extensions |
| --- | --- |
| Notes/general homework | `.pdf`, `.txt`, `.md`, `.pptx`, `.png`, `.jpg`, `.jpeg` |
| Exam Prep material | `.pdf`, `.txt`, `.md`, `.pptx` |
| Exam Prep syllabus | `.pdf`, `.txt`, `.md` |
| Work review/performance | `.pdf`, `.png`, `.jpg`, `.jpeg` |

All use `MAX_UPLOAD_BYTES`. Legacy `.ppt` is unsupported. Exam Prep material does not accept images. File extensions and size limits are defensive input checks, not malware scanning.

## Validation

Backend:

```bash
cd backend
python -m compileall -q app tests
python -m pytest -q
```

Frontend:

```bash
cd frontend
npm ci
npm run lint
npm run typecheck
npm run build
```

These commands match `.github/workflows/ci.yml`. Tests do not need live providers, Supabase, or PostgreSQL. They do not validate the full database schema, provider behavior, or browser flows.

## First-use sequence

After both applications start and the compatible schema is available:

1. Sign in with Supabase.
2. Create a course.
3. Add a note or supported upload.
4. Start concept extraction and wait for a terminal status.
5. Inspect concepts/flashcards and generate practice.
6. For Exam Prep, upload a syllabus and supported exam material before generating a plan.

Provider-backed operations spend API quota and may send course content to the configured provider. Use synthetic data for evaluation.
