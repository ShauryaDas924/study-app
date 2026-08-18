# Development guide

This guide is for code review and maintenance of the archived MVP. Start with [Setup](SETUP.md); a compatible pre-existing database schema is required for end-to-end use.

## Repository layout

```text
backend/
  app/
    jobs/          in-process concept extraction
    routers/       HTTP endpoints and ownership boundaries
    services/      auth, providers, extraction, mastery, planning, exam logic
    db.py          async SQLAlchemy engine/session dependency
    models.py      PostgreSQL domain model
    main.py        FastAPI startup, CORS, router registration
  migrations/      incremental Exam Prep/Lockdown SQL only
  tests/            deterministic pytest foundation

frontend/
  app/              Next.js route pages
  components/       shared and feature UI
  lib/api.ts        typed REST client/contracts
  lib/auth.ts       session-aware fetch wrapper
  lib/privacy.ts    known app-owned browser-state cleanup
  store/            Zustand state
```

## Backend conventions

- Route dependencies provide `AsyncSession` and the authenticated `user_id`.
- A client-supplied user ID must never choose ownership. Fetch the parent class/record with both its ID and `user_id` before operating on nested data.
- Keep async database access scoped and close sessions before slow provider calls when practical.
- The OpenAI SDK clients are synchronous. Existing async paths use thread-pool wrappers in several services; new async endpoints should not add direct blocking calls.
- Convert provider output into a bounded, validated domain shape before saving or using it. Preserve a clear failure state instead of accepting malformed output silently.
- Do not log prompts, uploads, answers, chat text, tokens, or raw provider responses. Counts, durations, stages, byte sizes, and exception classes are usually sufficient.
- Use `read_upload_limited` with the narrowest existing extension set. Adding a UI `accept` value does not secure the API.
- Avoid claiming a job is durable. `BackgroundTasks`, the live status map, and the semaphore belong to one FastAPI process.

## Frontend conventions

- Put endpoint and response types in `frontend/lib/api.ts`; keep those types aligned with the actual Pydantic/JSON response, including nullable and optional fields.
- Use `authFetch` for API requests so bearer tokens are attached only to the configured API origin and `401` triggers sign-out cleanup.
- Gate authenticated pages with `RequireAuth` and avoid firing private queries while auth is unresolved.
- Treat query data as server state and invalidate the narrowest relevant TanStack Query keys after mutations.
- Mark browser-only data clearly. Course-keyed `localStorage` is not a server persistence or authorization mechanism.
- Keep accepted upload formats synchronized with the backend route-specific allowlist.
- Do not print extracted text, request bodies, provider output, answers, or full API responses in browser logs.

## Learning-state changes

Before changing mastery or planning behavior, read:

- [`backend/mastery_system.md`](../backend/mastery_system.md)
- [`backend/study_plan_system.md`](../backend/study_plan_system.md)
- [`backend/learning_loop.md`](../backend/learning_loop.md)

The current mastery update is not the earlier additive-delta design. It applies attempt-time decay and a Bayesian-style posterior. The live Planner UI is Exam Prep; the generic daily/weekly plan code is unmounted. Update code, tests, and these notes together if either changes.

## Adding an authenticated nested endpoint

1. Define bounded Pydantic inputs.
2. Resolve `user_id` with `get_current_user_id`.
3. Fetch the parent object with both its ID and `user_id` (and course ID when applicable).
4. Return `404` for inaccessible/missing records rather than exposing existence across users.
5. Scope every child query/update/delete to the same ownership boundary.
6. Add a deterministic regression test where the logic can be isolated without a live database/provider.
7. Update `frontend/lib/api.ts` and the relevant documentation.

## Validation before review

```bash
cd backend
python -m compileall -q app tests
python -m pytest -q

cd ../frontend
npm ci
npm run lint
npm run typecheck
npm run build

cd ..
git diff --check
git status --short
```

CI runs the same compile/test/lint/type-check/build categories with Python 3.12 and Node 22. It deliberately uses placeholders and does not call providers, Supabase, PostgreSQL, or a deployment target.

## Documentation rules

- Source code wins when implementation and prose disagree.
- Describe current behavior separately from retained experiments and future work.
- Do not call the MVP production-grade, distributed, real-time, or secure without evidence.
- Say `pgvector storage with application-side NumPy ranking`, not `pgvector search`.
- Say `process-local FastAPI background task`, not `queue worker` or `Redis`.
- Keep the archived/discontinued status visible in the root README.

## Scope of this public repository

The repository is intentionally inspectable proof of code. It includes real model/provider orchestration and learning logic, while excluding private agent instructions, generated resume material, credentials, and deployment/account configuration. No license is granted by repository visibility.
