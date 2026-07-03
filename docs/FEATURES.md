# Features

This document lists features supported by visible code in the repository.

## Class Management

### What it does

Users can create, list, clear, and delete classes. Most study data is class-scoped.

### User-facing behavior

The frontend has a courses page and a class selector. Selecting a class controls what notes, practice, tutor, planner, and analytics data is loaded.

### Important files

- `frontend/app/courses/page.tsx`
- `frontend/components/ClassSelector.tsx`
- `frontend/store/useStore.ts`
- `backend/app/routers/classes.py`
- `backend/app/models.py`

### Internal logic summary

`classes.py` creates and lists `Class` rows for the authenticated user. Clear/delete routes explicitly delete many dependent rows for that class.

### Configuration options

Auth depends on Supabase env variables or `DEV_MODE`.

### Edge cases

- Clearing a class is destructive for study data.
- Class ownership must be verified before mutating data.

### Known limitations

Unknown from current repo: soft-delete strategy, archival strategy, or undo support.

## Authentication

### What it does

Frontend uses Supabase sessions. Backend verifies Bearer tokens through Supabase Auth.

### User-facing behavior

Unauthenticated frontend users are routed through login-protected pages with `RequireAuth`.

### Important files

- `frontend/lib/supabaseClient.ts`
- `frontend/lib/auth.ts`
- `frontend/components/RequireAuth.tsx`
- `frontend/app/login/page.tsx`
- `frontend/app/auth/callback/page.tsx`
- `backend/app/services/auth.py`

### Internal logic summary

Frontend attaches the Supabase access token as a Bearer token. Backend calls Supabase `/auth/v1/user` to resolve the user ID unless `DEV_MODE` is enabled.

### Configuration options

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `DEV_MODE`
- `DEV_USER_ID`

### Edge cases

- Missing frontend Supabase vars throw at client initialization.
- Missing backend Supabase vars cause backend auth to return a 500 unless `DEV_MODE` is enabled.
- 401 responses trigger frontend sign-out and login redirect.

### Known limitations

Production auth/session hardening is unknown from current repo.

## Notes And Uploads

### What it does

Users can create notes and upload note files. Uploaded text can queue concept extraction.

### User-facing behavior

The Notes page supports notes and extraction status. Upload components send files to the backend.

### Important files

- `frontend/app/notes/page.tsx`
- `frontend/components/NoteEditor.tsx`
- `frontend/components/UploadNotes.tsx`
- `backend/app/routers/notes.py`
- `backend/app/routers/uploads.py`
- `backend/app/services/file_extraction.py`
- `backend/app/jobs/concept_jobs.py`

### Internal logic summary

Manual note creation writes a `Note` row. Uploading a note reads bytes, extracts text, creates a note row, and queues `concept_extraction_job` through FastAPI `BackgroundTasks`.

### Configuration options

- `OPENAI_API_KEY` for vision/LLM paths.
- Upload behavior can include extraction mode values passed from the frontend.

### Edge cases

- Empty extracted text returns an upload error.
- Stale queued/running extraction states are reset on backend startup.
- PDF/PPT/image extraction quality depends on file content.

### Known limitations

Original file persistence outside extracted text is unknown from current repo.

## Concept Extraction And Flashcards

### What it does

Extracts concepts from notes and provides flashcard routes by class or note.

### User-facing behavior

Users can extract concepts, view concepts, and review flashcards.

### Important files

- `backend/app/routers/concepts.py`
- `backend/app/jobs/concept_jobs.py`
- `backend/app/services/llm.py`
- `frontend/app/flashcards/page.tsx`
- `backend/concept_extraction_prompt.md`
- `backend/concept_extraction_spec.md`

### Internal logic summary

Concept extraction uses background job state and LLM services to create concept and flashcard data.

### Configuration options

- LLM API keys.
- Extraction mode values from note routes.

### Edge cases

- LLM JSON/schema failures need handling.
- Existing extraction jobs can already be queued or running.

### Known limitations

No automated extraction regression tests were found.

## Practice, Exams, Mastery, And Analytics

### What it does

Generates practice questions, records attempts, updates mastery, provides exam sessions, hints, step checks, readiness, dependency graph, and analytics.

### User-facing behavior

Users can generate practice, answer questions, get feedback/hints, run exam sessions, and see analytics.

### Important files

- `frontend/app/practice/page.tsx`
- `frontend/app/exam/page.tsx`
- `frontend/app/analytics/page.tsx`
- `frontend/app/insights/page.tsx`
- `frontend/components/PracticeSetup.tsx`
- `frontend/components/PracticePlayer.tsx`
- `frontend/components/ExamRunner.tsx`
- `frontend/components/KnowledgeGraph.tsx`
- `backend/app/routers/practice.py`
- `backend/app/services/mastery.py`
- `backend/mastery_system.md`
- `backend/practice_engine_spec.md`
- `backend/practice_generation_prompt.md`

### Internal logic summary

Practice routes generate question rows from concepts, accept attempts, update mastery, log mistakes, provide step-level coaching, and expose analytics endpoints.

### Configuration options

- Practice generation payload includes class, difficulty, count, subject tag, and question type.
- Remedial practice payload includes lookback and dependency options.

### Edge cases

- If there are no concepts or attempts, remedial and analytics routes may fall back or return empty data.
- Mastery depends on stored concepts and attempts.

### Known limitations

No test suite was found to verify generated question shape or mastery updates.

## Homework Tutor And Pitfalls

### What it does

Provides homework help, upload-based help, step checking, work review, chat history, and persistent pitfalls.

### User-facing behavior

Users can ask homework questions, upload homework, review their work, check steps, and practice detected weak areas from Tutor.

### Important files

- `frontend/app/homework/page.tsx`
- `frontend/app/tutor/page.tsx`
- `frontend/components/TutorChat.tsx`
- `backend/app/routers/homework.py`

### Internal logic summary

The backend retrieves relevant concepts, builds LLM context, stores chat memory and pitfalls, and supports step/work review sessions.

### Configuration options

- LLM API keys.
- Constants in `backend/app/routers/homework.py`, such as grounding and context limits.

### Edge cases

- File extraction can fail or produce poor text.
- Generated tutor responses depend on available class concepts and uploaded notes.
- Pitfall clearing is destructive for that class.

### Known limitations

No explicit privacy policy or retention policy was found for chat/homework history.

## Planner

### What it does

Generates daily and weekly study plans and hosts the Exam Prep Planner UI.

### User-facing behavior

Users can generate study plans from course context and create planner tasks from exam prep plans.

### Important files

- `frontend/app/planner/page.tsx`
- `frontend/components/StudyPlanGenerator.tsx`
- `frontend/components/WeeklyPlanGenerator.tsx`
- `frontend/components/StudyPlanView.tsx`
- `backend/app/routers/plan.py`
- `backend/app/services/planner.py`
- `backend/study_plan_system.md`

### Internal logic summary

Planner routes generate structured plan JSON from user/class data and LLM services.

### Configuration options

Depends on request payloads and LLM env vars.

### Edge cases

- Missing class data can reduce plan quality.
- LLM output shape must match expected response structures.

### Known limitations

No calendar integration or scheduler was found.

## Exam Lockdown / Evidence-Based Exam Prep

### What it does

Exam Lockdown lets users upload exam prep materials, extract questions, generate evidence-based study plans, and coach exact recommended questions in Tutor.

### User-facing behavior

Planner shows a command-center workflow:

1. Exam setup.
2. Evidence library.
3. Generate evidence-based plan.
4. Generated plan and saved plans.

Tutor has a separate Exam Lockdown mode that loads the active plan, shows today’s block, likely scope, recommended questions, coach controls, and progress.

### Important files

- `frontend/components/exam-prep/ExamPrepPlannerPanel.tsx`
- `frontend/components/exam-prep/ExamPrepMaterialUploader.tsx`
- `frontend/components/exam-prep/ExamPrepMaterialsList.tsx`
- `frontend/components/exam-prep/RecommendedQuestionList.tsx`
- `frontend/components/exam-lockdown/ExamLockdownTutorMode.tsx`
- `frontend/components/exam-lockdown/ExamCoachResponse.tsx`
- `frontend/components/exam-lockdown/LockdownProgressPanel.tsx`
- `backend/app/routers/exam_prep.py`
- `backend/app/routers/exam_lockdown.py`
- `backend/app/services/exam_prep.py`
- `backend/app/services/exam_lockdown.py`
- `backend/migrations/20260506_exam_prep_planner.sql`
- `backend/migrations/20260512_exam_lockdown_materials.sql`
- `backend/migrations/20260515_exam_prep_extracted_question_status.sql`

### Internal logic summary

Exam prep material upload stores material rows and extracted text. Question extraction persists `ExamPrepExtractedQuestion` records. Plan generation ranks topics, selects recommendations from persisted extracted questions, saves `ExamPrepRecommendedQuestion` rows, and can assign questions into day blocks. Tutor loads active plans and calls Exam Lockdown tutor/attempt endpoints.

### Configuration options

- Material type selection in the Planner UI.
- Exam title/date, minutes per day, intensity, target score/grade, current scores, weak topics, selected materials.
- `allow_no_recommendations` exists in the backend request model but should be used carefully.

### Edge cases

- Plans should not silently create no-question active plans unless explicitly allowed by backend behavior.
- Re-extraction uses stale status preservation to avoid deleting recommendation-linked question history.
- Low-quality extraction can reduce recommendation quality.
- Vision OCR behavior is controlled by file extraction options.

### Known limitations

- Adaptive replanning from attempts/pitfalls appears limited.
- Original file page previews/storage are unknown.
- Automated tests for recommendation integrity were not found.

## Blurting Mind Map

### What it does

The frontend contains blurting/mind-map components and a `/blurting` page.

### User-facing behavior

Unknown from current repo beyond the existence of page/components. Inspect `frontend/components/blurting-mindmap/` for current behavior before modifying.

### Important files

- `frontend/app/blurting/page.tsx`
- `frontend/components/blurting-mindmap/`

### Known limitations

Backend persistence for this feature is not obvious from the current repo.
