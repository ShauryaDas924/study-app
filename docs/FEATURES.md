# Features and implementation status

This is a code-oriented inventory of the archived MVP. “Live” means reachable from the current frontend navigation; it does not mean production-ready.

| Area | Status | Implementation notes and limits |
| --- | --- | --- |
| Supabase authentication | Live | Browser session becomes a bearer token; FastAPI verifies it with Supabase. The explicit `DEV_MODE` bypass is allowed only when `APP_ENV` is `development` or `test`. |
| Courses | Live | User-scoped create/list plus server-side clear/delete across known related tables. Browser-only drafts are separate. |
| Notes | Live | Manual editing and file ingestion. Uploaded text is returned to the browser and stored in PostgreSQL. |
| Concept extraction | Live | FastAPI background task, one heavy job at a time per API process, persisted progress/failure status, structured LLM output, embeddings, and flashcards. Not durable across restart. |
| Flashcards | Live | Generated cards and server review/session state; the notes screen also keeps a local card cache. |
| Practice | Live | Open and MCQ questions, weak-concept selection, attempts, confidence, timing, mistake logs, hints, and automatic remedial sets. AI output may be wrong. |
| Attempt grading | Live | MCQ correctness is recomputed server-side from stored options/index. Other question types use the student's self-report. |
| Mastery/readiness | Live | Initial value `0.35`; attempt-time forgetting plus Bayesian-style update; history and review date stored. Readiness is a simple average of stored values. |
| Tutor | Live | Course-aware responses use concepts and stored memory; provider context may include course material and prior struggles. |
| Homework/work review | Live | Text/file help, step coaching, chat memory, work-image/PDF review, and pitfall memory. Some chat display history is local to the browser. |
| Analytics and insights | Live | Readiness, mistake heatmap, weakness/tag summaries, mastery displays, and graph views derived from stored data. |
| Exam runner | Live | Practice exam sessions, timing, attempts, and reports. This is not proctoring software. |
| Exam Prep planner | Live | Syllabus parsing, material selection, extracted questions, topic scoring, minimum/strong schedules, tasks, warnings, and persisted plan retrieval. Predictions are estimates. |
| Exam Lockdown tutor | Live | Loads an active plan and exact recommended/source question, records attempts and pitfalls, and reports progress. “Lockdown” describes a focused study mode, not device or browser restriction. |
| Blurting board | Live | Browser-only board keyed by course in `localStorage`; no backend sync or encryption. |
| Mind map | Live | Browser-only node graph keyed by course in `localStorage`; no backend sync or encryption. |
| Daily/weekly planner | Code retained, UI inactive | Deterministic endpoints and components exist, but the current Planner page mounts only Exam Prep. See the [planning implementation note](../backend/study_plan_system.md). |

## Upload matrix

Every upload uses the configured `MAX_UPLOAD_BYTES` limit: 10 MiB by default, configurable up to an absolute 50 MiB ceiling.

| Route family | Accepted filename extensions |
| --- | --- |
| Notes and general homework documents | `.pdf`, `.txt`, `.md`, `.pptx`, `.png`, `.jpg`, `.jpeg` |
| Exam Prep materials | `.pdf`, `.txt`, `.md`, `.pptx` |
| Exam Prep syllabi | `.pdf`, `.txt`, `.md` |
| Work review and performance images | `.pdf`, `.png`, `.jpg`, `.jpeg` |

Extensions are an allowlist, not a malware or content-safety guarantee. Legacy PowerPoint `.ppt` is not supported. Exam Prep material does not accept images because that extraction path does not use vision OCR.

## AI-provider roles

The implementation uses both configured providers; they are not interchangeable environment labels.

- **OpenAI:** embeddings, vision-assisted document extraction, practice/tutoring operations, and Exam Prep/Lockdown services.
- **Moonshot/Kimi:** note refinement/concept processing and several homework/performance flows.

The exact model names are implementation details in the relevant services. Running a feature requires the key for the provider that feature calls. Course content, questions, answers, or derived context may be included in provider requests.

## Persistence summary

PostgreSQL stores courses, notes, extracted concepts, embeddings, flashcards, questions, attempts, mastery/history, mistakes, tutor memory, work review, exams, Exam Prep data, and Lockdown data. Browser `localStorage` stores selected UI state and some full-content drafts, including blurting/mind-map boards and homework chat display history.

See [Privacy and security](PRIVACY_AND_SECURITY.md) before using real data.
