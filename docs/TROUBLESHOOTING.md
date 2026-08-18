# Troubleshooting

## The backend fails during import or startup

Check `backend/.env` first.

- `DATABASE_URL` must use the async SQLAlchemy form, such as `postgresql+asyncpg://...`.
- The current service modules construct OpenAI and Moonshot-compatible clients during import. Set both `OPENAI_API_KEY` and `MOONSHOT_API_KEY` for a normal application run, even if you do not immediately use every AI feature.
- `DEV_MODE=true` is rejected unless `APP_ENV` is exactly `development` or `test`.
- `DEV_USER_ID` must be a valid UUID.
- `CORS_ORIGINS` must contain explicit `http` or `https` origins with no path. `*` is rejected.

Use synthetic/placeholder provider values only for deterministic tests; provider calls will fail with them.

## PostgreSQL reports a missing table or column

The repository does not contain a base migration and does not create tables at startup. Its three SQL migrations are incremental Exam Prep/Lockdown changes. A blank database will fail.

Confirm that you have the owner-compatible baseline schema and that the incremental files in `backend/migrations/` were applied in filename-date order. Do not infer a complete schema by applying only those three files.

Also verify that the PostgreSQL `vector` extension is available for the `Vector(1536)` concept column.

## Authentication returns 401

- Confirm the browser signed in and has a current Supabase session.
- Confirm frontend and backend point to the same Supabase project.
- Use the public anonymous key in both apps; do not expose a service-role key.
- Confirm the request targets `NEXT_PUBLIC_API_BASE_URL`. The client intentionally does not attach the token to another origin.
- An expired/invalid token causes sign-out and cleanup of known app-owned browser study state.

For isolated direct API development, `APP_ENV=development` plus `DEV_MODE=true` enables a fixed backend user. It does not bypass the frontend's Supabase route guard.

## The browser reports a CORS error

Set the exact frontend origin in `CORS_ORIGINS`, with entries separated by commas:

```dotenv
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

Origins are scheme + hostname + optional port only. Do not include a path or trailing wildcard. Restart FastAPI after changing the environment.

## An upload returns 413, 415, or “No text could be extracted”

- `413`: the file exceeds `MAX_UPLOAD_BYTES` (10 MiB by default).
- `415`: its extension is not accepted for that route.
- Empty/invalid document: the extension passed but the extractor found no usable text.

Common format surprises:

- Legacy `.ppt` is unsupported; convert it to `.pptx` or PDF.
- Exam Prep materials accept `.pdf`, `.txt`, `.md`, and `.pptx`, not images.
- Syllabi accept `.pdf`, `.txt`, and `.md`.
- Images are accepted only by the document/work-review routes that enable image extraction.
- A PDF, image, or presentation can also exceed its page, pixel, OCR-page, or expanded-size limit.

These checks are not malware scanning. Do not expose the uploader to untrusted public traffic.

## Concept extraction is queued, interrupted, or appears stuck

Heavy concept extraction runs inside the FastAPI process, one job at a time per process. A second note waits for the semaphore. There is no Redis/external worker.

- Keep the API process running until the job reaches `completed` or `failed`.
- Poll the note extraction-status endpoint rather than assuming the original request owns the work.
- On restart, queued/running notes are reset to `idle` with an interruption error. Start extraction again from the UI/API.
- Check provider availability and quota without logging or sharing the document content.
- Lower `CONCEPT_CHUNK_CONCURRENCY` if the provider or local environment is resource-constrained.

## Exam Prep cannot generate a source-question plan

- Select a course.
- Upload a supported syllabus if syllabus evidence is desired.
- Upload at least one Exam Prep material file.
- Wait until material text extraction succeeds.
- Run question extraction so the selected material has active persisted questions.
- Select those materials before generating the plan.

The planner can return warnings or require an explicit no-recommendations override when evidence is insufficient. That behavior is deliberate: it avoids presenting invented source questions as grounded recommendations.

## The daily or weekly planner component is missing

This is expected in the current UI. `/planner` mounts the Exam Prep planner only. The earlier `/plan/generate` and `/plan/weekly-generate` endpoints and corresponding React components remain in the codebase but are not mounted.

## Browser-only work disappeared or remains after server deletion

Blurting/mind-map boards and homework chat display history use `localStorage`, not PostgreSQL. They are specific to a browser profile and do not sync across devices.

Sign-out clears known app-owned study-state keys on that browser. Server-side class clear/delete does not independently reach other browser profiles or devices. Use the browser's site-data controls if manual removal is needed.

## Frontend environment or build errors

`NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` are required when the Supabase client module is evaluated, including during a production build. Copy `frontend/.env.example` to `.env.local` for local work. CI supplies safe placeholders.

Run the same checks as CI:

```bash
cd frontend
npm ci
npm run lint
npm run typecheck
npm run build
```

If `eslint`, `next`, or `tsc` is not found, dependencies were not installed; run `npm ci` from `frontend/`, not the repository root.

## Backend tests try to use a live service

The committed deterministic tests should not call PostgreSQL, Supabase, OpenAI, or Moonshot. Install the development dependency set and run from `backend/`:

```bash
python -m pip install --requirement requirements-dev.txt
python -m compileall -q app tests
python -m pytest -q
```

If a new test reaches a service, isolate the deterministic function or mock the narrow boundary. Do not add real credentials to CI.

## AI output is incomplete or incorrect

Model output is probabilistic. Retry only when appropriate, inspect the stored source link/evidence, and treat mastery, topic confidence, plans, grading assistance, and tutor feedback as aids rather than authoritative academic judgments. This repository includes no formal AI-quality benchmark.
