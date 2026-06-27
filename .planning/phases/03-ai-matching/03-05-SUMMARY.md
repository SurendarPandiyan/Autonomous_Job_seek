---
phase: "03"
plan: "05"
subsystem: matching
tags: [celery, pgvector, cosine-similarity, upsert, service-layer]
dependency_graph:
  requires: ["03-04"]
  provides: ["03-06"]
  affects: [matching/service.py, matching/tasks.py, workers/router.py]
tech_stack:
  added: [sqlalchemy.dialects.postgresql.insert (pg_insert), pgvector cosine_distance]
  patterns: [ON CONFLICT DO UPDATE upsert, asyncio.run in Celery task]
key_files:
  modified:
    - src/jobplatform/matching/service.py
    - src/jobplatform/matching/tasks.py
    - src/jobplatform/workers/router.py
decisions:
  - "find_similar_jobs uses Job.embedding.cosine_distance in ORDER BY; score = 1 - cosine_distance"
  - "upsert_match uses pg_insert with on_conflict_do_update on uq_job_matches_user_job constraint"
  - "compute_matches_for_user wraps _compute_matches_async via asyncio.run() — Celery tasks are sync"
  - "list_matches, get_job_match are pure DB lookups in service.py for use by matching router (03-06)"
metrics:
  duration: "6 minutes"
  completed_date: "2026-06-27"
  tasks_completed: 2
  files_modified: 3
---

# Phase 3 Plan 05: Match Scoring Celery Task Summary

**One-liner:** pgvector cosine similarity search + ON CONFLICT upsert in Celery task, exposed via POST /workers/compute-matches.

## What Was Built

Added four async DB service functions to `matching/service.py`, a `compute_matches_for_user` Celery task to `matching/tasks.py`, and the `POST /api/v1/workers/compute-matches` endpoint to `workers/router.py`.

### Service functions (matching/service.py)

- `find_similar_jobs(db, profile_embedding, limit=50)` — pgvector cosine distance query filtered to active jobs with non-null embeddings; returns `list[tuple[Job, float]]` ordered by descending similarity score
- `upsert_match(db, user_id, job_id, score, ats_score, skill_gaps)` — PostgreSQL INSERT ... ON CONFLICT DO UPDATE using `pg_insert` and constraint `uq_job_matches_user_job`; never select-then-insert
- `list_matches(db, user_id, limit, cursor)` — ranked match list with cursor-based pagination
- `get_job_match(db, user_id, job_id)` — single match lookup by (user, job) pair

### Celery task (matching/tasks.py)

- `_compute_matches_async(user_id, task_id)` — async orchestrator: fetch profile + prefs, build profile text, get embedding, find similar jobs (top 50), compute ATS score and skill gaps per job, bulk upsert matches, commit
- `compute_matches_for_user` — sync Celery task wrapper calling `asyncio.run(_compute_matches_async(...))`, returns `{"user_id": N, "matched": K}`

### Worker endpoint (workers/router.py)

- `POST /api/v1/workers/compute-matches` with `{"user_id": N}` — dispatches Celery task, returns 202 with `{"task_id": "..."}`

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add DB service functions + Celery task | 3413a0e | matching/service.py, matching/tasks.py |
| 2 | Add /workers/compute-matches endpoint | 9e48a3a | workers/router.py |

## Test Results

44 tests passed, 0 failures. Total coverage: 77%.

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None. No new network endpoints beyond the planned worker route; auth gated by `get_current_user` dependency.

## Self-Check: PASSED

- `find_similar_jobs, upsert_match, list_matches, get_job_match` imports: OK
- `compute_matches_for_user.name` == `jobplatform.matching.tasks.compute_matches_for_user`: OK
- `/api/v1/workers/compute-matches` in router routes: OK
- 44 pytest tests passed
