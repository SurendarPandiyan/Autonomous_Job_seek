---
phase: "03"
plan: "03-03"
subsystem: "matching"
tags: ["celery", "embeddings", "openai", "workers"]
dependency_graph:
  requires: ["03-01", "03-02"]
  provides: ["embed_jobs_batch Celery task", "POST /api/v1/workers/embed-jobs"]
  affects: ["matching", "workers", "celery"]
tech_stack:
  added: []
  patterns: ["asyncio.run() Celery wrapper", "batch-process with rate-limit sleep"]
key_files:
  created:
    - src/jobplatform/matching/tasks.py
  modified:
    - src/jobplatform/celery_app.py
    - src/jobplatform/workers/router.py
decisions:
  - "asyncio.run(_embed_jobs_batch_async) pattern mirrors jobs/tasks.py for consistency"
  - "Pre-registered embed_profile and compute_matches_for_user routes in celery_app.py for 03-04/03-05"
metrics:
  duration: "~10 min"
  completed: "2026-06-27"
---

# Phase 3 Plan 03: Job Embedding Celery Task Summary

## One-liner

Celery task `embed_jobs_batch` batch-embeds NULL-embedding jobs via OpenAI text-embedding-3-small, exposed via `POST /api/v1/workers/embed-jobs`.

## What Was Built

### Task 1: `src/jobplatform/matching/tasks.py`

Created the `embed_jobs_batch` Celery task:
- `_embed_jobs_batch_async(task_id)`: async inner function that queries `Job.embedding IS NULL AND is_active = True` in batches of 20, calls `build_job_text` + `get_embedding` per job, writes embedding back, commits per batch, sleeps 0.5 s between batches
- `embed_jobs_batch`: synchronous Celery task with name `jobplatform.matching.tasks.embed_jobs_batch` using `asyncio.run()` wrapper
- Returns `{"embedded": N, "skipped": 0}`

### Task 2: celery_app.py + workers/router.py

- `celery_app.py`: added `jobplatform.matching.tasks` to `include`; added task routes for `embed_jobs_batch` (queue: embedder), `embed_profile` (queue: embedder), `compute_matches_for_user` (queue: matcher)
- `workers/router.py`: imported `embed_jobs_batch`; added `POST /api/v1/workers/embed-jobs` returning 202 `{"task_id": "..."}`

## Verification Results

- Import check: `embed_jobs_batch.name == "jobplatform.matching.tasks.embed_jobs_batch"` — PASSED
- Celery include check: `matching.tasks` in `celery_app.conf.include` — PASSED
- Router check: `/api/v1/workers/embed-jobs` in router routes — PASSED
- Full test suite: 44 passed, 0 failed — PASSED

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- src/jobplatform/matching/tasks.py: FOUND (commit 6171b9a)
- src/jobplatform/celery_app.py updated: FOUND (commit 61c222c)
- src/jobplatform/workers/router.py updated: FOUND (commit 61c222c)
- All 44 tests pass
