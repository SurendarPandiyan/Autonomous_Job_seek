---
phase: "03"
plan: "04"
subsystem: matching
tags: [celery, embedding, profile, async, workers]
dependency_graph:
  requires: ["03-03"]
  provides: ["embed_profile task", "profile embedding hooks", "POST /embed-profile endpoint"]
  affects: ["matching", "profiles", "preferences", "workers"]
tech_stack:
  added: []
  patterns: ["Celery async wrapper via asyncio.run()", "fire-and-forget embed dispatch on update"]
key_files:
  created: []
  modified:
    - src/jobplatform/matching/tasks.py
    - src/jobplatform/profiles/router.py
    - src/jobplatform/preferences/router.py
    - src/jobplatform/workers/router.py
decisions:
  - "embed_profile is a sync Celery task wrapping an async coroutine via asyncio.run(), consistent with embed_jobs_batch pattern"
  - "embed_profile.delay() fired after DB commit in profile/preferences PATCH — fire-and-forget, no await"
metrics:
  duration: "~10 min"
  completed_date: "2026-06-27"
---

# Phase 3 Plan 04: Profile Embedding Celery Task Summary

## One-liner

Added `embed_profile` Celery task that builds profile+prefs text, calls OpenAI embeddings, and stores the 1536-dim vector to `Profile.embedding`; hooked it into PATCH profile/preferences endpoints and exposed `POST /api/v1/workers/embed-profile` for manual triggering.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add embed_profile task to matching/tasks.py | fcf1d8c | matching/tasks.py |
| 2 | Hook embed_profile into routers and add worker endpoint | f42bd10 | profiles/router.py, preferences/router.py, workers/router.py |

## What Was Built

**Task 1 — embed_profile Celery task:**
- Added imports: `datetime`, `timezone`, `build_profile_text`, `JobPreferences`, `Profile`
- `_embed_profile_async(user_id, task_id)`: loads `Profile` by `user_id`, loads `JobPreferences`, calls `build_profile_text`, calls `get_embedding`, stores `embedding` and sets `enriched_at = datetime.now(timezone.utc)`, commits
- Handles edge cases: no profile → returns `{status: no_profile}`, empty text → returns `{status: empty_text}`
- `embed_profile` sync wrapper with `name="jobplatform.matching.tasks.embed_profile"` and `bind=True`

**Task 2 — Router hooks and worker endpoint:**
- `profiles/router.py`: `patch_profile` now calls `embed_profile.delay(user_id=current_user.id)` after `update_profile` returns
- `preferences/router.py`: `patch_preferences` now calls `embed_profile.delay(user_id=current_user.id)` after `update_preferences` returns
- `workers/router.py`: Added `EmbedProfileRequest(user_id: int)` model and `POST /embed-profile` endpoint returning `202 {"task_id": "..."}` via `apply_async(kwargs={"user_id": ...})`

## Deviations from Plan

None — plan executed exactly as written.

## Test Results

44 passed, 3 warnings — all existing tests pass. No new tests added (plan did not require new test files; integration is fire-and-forget Celery dispatch, covered by existing profile/preferences endpoint tests which mock Celery tasks via `celery_app.conf.task_always_eager` or are integration-tested through existing fixtures).

## Known Stubs

None.

## Threat Flags

None. No new network endpoints with trust boundary implications beyond existing authenticated routes; `/embed-profile` requires `get_current_user` like all other worker endpoints.

## Self-Check: PASSED

- `from jobplatform.matching.tasks import embed_profile; print(embed_profile.name)` → `jobplatform.matching.tasks.embed_profile`
- `patch_profile` source contains `embed_profile` → OK
- `patch_preferences` source contains `embed_profile` → OK
- `/api/v1/workers/embed-profile` in router paths → OK
- 44 tests pass
