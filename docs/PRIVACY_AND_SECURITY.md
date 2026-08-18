# Privacy and security

This document describes the boundaries visible in the repository. It is not a security certification, privacy policy, data-processing agreement, or promise that the archived MVP is suitable for production use.

## Data the app can handle

Depending on the selected workflow, College AI can process and store:

- uploaded notes, syllabi, slides, problem sets, images, and PDFs;
- extracted text, concepts, embeddings, questions, solutions, and source references;
- answers, correctness, confidence, timing, mistakes, mastery, and review history;
- tutor/homework chat context, work-review images, and derived pitfalls;
- exam dates, targets, plans, tasks, recommendations, and lockdown attempts.

Do not use confidential student records, protected education records, restricted assessments, or material you do not have permission to send to the configured services.

## Where data goes

| Boundary | Data and purpose |
| --- | --- |
| Browser | Supabase session plus `localStorage` drafts/session state. Blurting boards, mind maps, and homework chat display history may contain full user text. |
| FastAPI | Validates identity and input, orchestrates learning logic, and sends selected context to providers. |
| PostgreSQL | Stores server-side course, learning, chat, exam, and derived records. Some work-review records can store base64 image content. |
| Supabase Auth | Receives access tokens for user validation. The configured anonymous key is a public client credential, not a service-role secret. |
| OpenAI | Can receive document images/text, queries, practice/exam context, and embeddings input. |
| Moonshot/Kimi | Can receive notes, homework/performance prompts, and derived learning context. |

Provider behavior, retention, residency, and training controls depend on the account and terms configured by the operator; the repository cannot guarantee them.

## Implemented safeguards

- Backend routes derive the user UUID from a validated bearer token and scope important records by user and course.
- Development authentication bypass is off by default and is rejected outside explicit development/test environments.
- Credentialed CORS accepts an explicit origin allowlist and rejects wildcard configuration.
- Uploads use basename sanitization, extension allowlists, empty-file rejection, and bounded reads.
- Default upload size is 10 MiB. Configuration cannot raise it above 50 MiB.
- Extraction also limits PDF pages, vision-OCR pages, image pixels, and expanded presentation/archive bytes.
- Multiple-choice attempts are graded from stored question data on the server rather than trusting a submitted correctness flag.
- Operational logs are intended to record counts, stages, sizes, and exception types rather than raw uploaded or generated content.
- User-owned classes have clear/delete API paths that remove the application's known related server records in foreign-key-safe order.

These controls reduce obvious risk; they do not establish comprehensive security.

## Deletion and retention

The API provides:

- clear course data while preserving the course row;
- delete a course and its known application records;
- clear stored homework chat history and stored pitfalls for a course;
- clear a flashcard session.

Important qualifications:

- There is no account-wide deletion workflow.
- Server deletion does not clear `localStorage` on every browser/device.
- The code has no formal retention schedule, deletion audit, backup-erasure guarantee, or provider-deletion orchestration.
- Database or provider operators may have backups or logs not represented by this application code.

Accordingly, the repository makes no retention or complete-erasure guarantee.

## Upload threat model

The app validates filename extensions and applies resource limits. It does **not** include antivirus/malware scanning, content-disarm/reconstruction, MIME-signature verification for every format, sandboxed document conversion, or quarantine storage. Treat all uploaded files as untrusted and do not expose this MVP as a public upload service.

Supported extensions are documented in [Features](FEATURES.md). Extension acceptance is not proof that file content is safe or valid.

## Browser storage

`localStorage` is origin-readable, persistent until cleared, and not encrypted by this app. An XSS bug, browser extension, shared browser profile, or another user with device access could expose it. Sign-out removes known app-owned study-state keys from the current browser, but cannot clear other profiles/devices or unknown future keys. Use browser/site-data controls when manual removal is needed.

## Controls not provided or proven

- application/API rate limiting or abuse prevention;
- malware scanning;
- production row-level-security policies;
- CSRF/security-header hardening assessment;
- formal secrets-management integration;
- penetration testing, dependency scanning, SAST/DAST, or threat-model signoff;
- multi-tenant security review;
- audit logging or production monitoring/alerting;
- disaster recovery, backup policy, or high availability;
- formal privacy notice, consent flow, retention policy, or regulatory compliance;
- AI-output benchmark, red-team evaluation, or prompt-injection defense guarantee.

## Before any real deployment

At minimum, an operator should supply a complete migration path; isolate environments and secrets; review every ownership boundary; add database policies where appropriate; add rate limiting, upload scanning/quarantine, security headers, monitoring, backups, and deletion operations; complete dependency and penetration testing; choose provider privacy settings; and publish a real privacy/retention policy.

That work is intentionally outside this archived portfolio repository.
