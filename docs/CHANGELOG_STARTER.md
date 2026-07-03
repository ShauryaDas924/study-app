# Changelog Starter

This file is a starter changelog template. It does not claim historical releases that are not documented in the repository.

## Suggested Format

Use this structure for future entries:

```markdown
## [Unreleased]

### Added
- New features.

### Changed
- Behavior changes.

### Fixed
- Bug fixes.

### Removed
- Removed features or APIs.

### Security
- Security, privacy, auth, data handling, or permission changes.

### Known Issues
- Known limitations or follow-up work.
```

## [Current Repository State] - 2026-07-03

### Added

- Next.js frontend under `frontend/`.
- FastAPI backend under `backend/`.
- Supabase-backed frontend auth helpers and backend token verification.
- Class-scoped notes, concept extraction, flashcards, practice, homework help, planner, analytics, and Exam Lockdown feature areas.
- SQLAlchemy models for classes, notes, concepts, practice, attempts, mastery, pitfalls, exam prep, lockdown, flashcards, and related learning records.
- Exam prep and Exam Lockdown SQL migrations in `backend/migrations/`.
- Exam Lockdown UI components for evidence upload, question extraction, plan generation, recommended questions, tutor coaching, progress, and attempts.
- Documentation set:
  - `README.md`
  - `AI_CONTEXT.md`
  - `docs/PROJECT_OVERVIEW.md`
  - `docs/ARCHITECTURE.md`
  - `docs/SETUP.md`
  - `docs/DEVELOPMENT_GUIDE.md`
  - `docs/FEATURES.md`
  - `docs/FILE_MAP.md`
  - `docs/TROUBLESHOOTING.md`
  - `docs/CHANGELOG_STARTER.md`

### Changed

- Unknown from current repo. No authoritative prior changelog exists.

### Fixed

- Unknown from current repo. No authoritative prior changelog exists.

### Removed

- Unknown from current repo. No authoritative prior changelog exists.

### Security

- Authentication and user scoping are present in backend routes.
- Local env files exist but should not be committed.
- Production security posture is unknown from current repo because no security policy, deployment config, or CI was found.

### Known Issues

- No automated test suite was found.
- Deployment process is unknown.
- Complete base database migration history is unknown.
- License is unknown.
- Privacy and data retention policies are unknown.

## Maintenance Guidance

When updating this changelog:

1. Add newest entries at the top.
2. Keep user-visible changes separate from internal refactors.
3. Mention schema migrations explicitly.
4. Mention auth, privacy, upload, or LLM prompt changes under `Security` when relevant.
5. Include known limitations honestly instead of hiding them.
6. Do not invent version numbers. Use dates or release tags that exist in the repo.
