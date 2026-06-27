---
phase: "03"
plan: "07"
subsystem: "matching"
tags: ["pytest", "pytest-asyncio", "asyncmock", "pgvector", "integration-tests", "jwt-auth"]
dependency_graph:
  requires: ["03-05", "03-06"]
  provides: ["tests/test_matching.py", "phase-3-test-coverage"]
  affects: []
tech_stack:
  added: []
  patterns: ["asyncmock-openai", "asyncsessionlocal-injection", "real-db-rollback-fixture"]
key_files:
  created:
    - tests/test_matching.py
  modified: []
decisions:
  - "Constructed Profile/Job/JobPreferences via normal SQLAlchemy constructors, not __new__ (plan's __new__ approach crashes: instrumentation state not initialized)"
  - "Patched jobplatform.matching.tasks.AsyncSessionLocal to inject the test db session for task tests (mirrors tests/test_scrape_worker.py); plan omitted this so tasks would hit the app DB not the test DB"
  - "Added on-demand match branch test (router lines 66-88) to cover the 3rd documented branch the plan's must-haves missed"
metrics:
  duration: "~12 minutes"
  completed: "2026-06-27T07:35:00Z"
  tasks_completed: 2
  files_changed: 1
---

# Phase 3 Plan 07: Phase 3 Test Suite Summary

**One-liner:** 15 unit/integration/endpoint tests for AI matching — service helpers, embedding tasks, pgvector similarity, and the three-branch match endpoint — with AsyncOpenAI mocked and a real rollback DB.

## What Was Built

`tests/test_matching.py` (15 tests):

**Unit (service helpers, no DB/network):**
- `test_get_embedding_returns_vector` — AsyncOpenAI mocked, asserts 1536-dim list
- `test_build_profile_text`, `test_build_job_text` — text assembly assertions
- `test_compute_ats_score_full_match` (1.0), `test_compute_ats_score_no_match` (0.0)
- `test_compute_skill_gaps` — returns only missing skills

**Integration (real DB via `db` fixture):**
- `test_job_match_model_create` — insert/retrieve JobMatch
- `test_find_similar_jobs` — pgvector cosine ranking, identical vector ranks first ~1.0
- `test_embed_jobs_batch_task` — task embeds null-embedding jobs
- `test_embed_profile_task` — task embeds profile, status ok
- `test_compute_matches_task` — full match pipeline, rows created with score + ats_score

**Endpoint (ASGI client + JWT):**
- `test_list_matches_endpoint` — GET /api/v1/matches/ → 200 list
- `test_get_job_match_endpoint_returns_stored` — branch 1: cached match → 200
- `test_get_job_match_endpoint_pending` — branch 2: no embedding → 202 pending
- `test_get_job_match_endpoint_on_demand` — branch 3: compute on demand → 200, persisted

## Test Results

59 passed, 0 failures (full suite: Phase 1 + 2 + 3). Up from 44 baseline (+15).

Coverage of Phase 3 code: models 100%, schemas 100%, service 97%, router 98%, tasks 83%
(uncovered tasks lines are celery `@task` decorator wrappers calling `asyncio.run`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan's `__new__` object construction crashes**
- **Found during:** Task 1 (`test_build_profile_text`, `test_build_job_text`)
- **Issue:** `Profile.__new__(Profile)` then setting mapped attributes raises `AttributeError: 'NoneType' object has no attribute 'set'` — SQLAlchemy instrumentation state is never initialized by `__new__`.
- **Fix:** Use normal constructors `Profile(...)`, `Job(...)`, `JobPreferences(...)` (in-memory, not persisted). Triggers declarative `__init__`.
- **Commit:** 77122e5

**2. [Rule 1 - Bug] Task tests would query the wrong database**
- **Found during:** Task 2 (`test_compute_matches_task`)
- **Issue:** Task coroutines open their own `AsyncSessionLocal()` bound to the app DB (`jobplatform`), not the test DB (`jobplatform_test`). Plan ran the task without patching it, so seeded data would be invisible and assertions would fail.
- **Fix:** Patched `jobplatform.matching.tasks.AsyncSessionLocal` to yield the test `db` session via `_inject_session` helper, mirroring `tests/test_scrape_worker.py`. Applied to all three task tests.
- **Commit:** 593d199

### Auto-added Coverage

**3. [Rule 2 - Missing coverage] On-demand match branch untested**
- **Found during:** Task 2 coverage review
- **Issue:** Plan's must-haves listed only stored + pending endpoint branches; the 3rd branch (on-demand cosine compute, router lines 66-88) — explicitly called out in known_pitfalls — was uncovered.
- **Fix:** Added `test_get_job_match_endpoint_on_demand` (profile+job embeddings present, OpenAI mocked) → 200 with computed score ~1.0 and persisted JobMatch. Router coverage 65% → 98%.
- **Commit:** 593d199

Added two extra task tests (`embed_jobs_batch`, `embed_profile`) beyond the plan's 12 must-haves to cover all Phase 3 task code paths (15 total).

## Known Stubs

None.

## Threat Flags

None — test-only changes, no new runtime surface.

## Self-Check

- `tests/test_matching.py` exists → FOUND
- Commit 77122e5 (Task 1) → FOUND
- Commit 593d199 (Task 2) → FOUND
- `uv run pytest tests/ -q` → 59 passed
- Phase 3 coverage: service 97%, router 98%, tasks 83%, models 100%

## Self-Check: PASSED
