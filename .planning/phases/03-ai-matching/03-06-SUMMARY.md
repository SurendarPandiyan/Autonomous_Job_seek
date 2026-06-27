---
phase: "03"
plan: "06"
subsystem: "matching"
tags: ["fastapi", "router", "pydantic", "pgvector", "jwt-auth"]
dependency_graph:
  requires: ["03-04"]
  provides: ["GET /api/v1/matches/", "GET /api/v1/jobs/{job_id}/match"]
  affects: ["main.py"]
tech_stack:
  added: []
  patterns: ["cursor-pagination", "on-demand-cosine-similarity", "pgvector-db-query"]
key_files:
  created:
    - src/jobplatform/matching/schemas.py
    - src/jobplatform/matching/router.py
  modified:
    - src/jobplatform/main.py
decisions:
  - "Used pgvector cosine_distance DB query for on-demand score (not Python numpy) to stay consistent with HNSW index"
  - "Router paths use full /api/v1 prefix inline (no include_router prefix) matching existing job/worker router pattern"
  - "On-demand branch re-fetches match after upsert+commit to return ORM-mode MatchResponse"
metrics:
  duration: "~8 minutes"
  completed: "2026-06-27T07:19:00Z"
  tasks_completed: 2
  files_changed: 3
---

# Phase 3 Plan 06: Match Router and Schemas Summary

**One-liner:** JWT-authenticated match endpoints with cursor pagination and pgvector on-demand cosine scoring.

## What Was Built

- `src/jobplatform/matching/schemas.py` — `MatchResponse` Pydantic model with ORM mode (`from_attributes=True`), fields: id, job_id, score, ats_score, skill_gaps, status, created_at, updated_at
- `src/jobplatform/matching/router.py` — two authenticated GET endpoints using `get_current_user` dependency
- `src/jobplatform/main.py` — `matching_router` imported and registered after `workers_router`

## Endpoints

| Method | Path | Auth | Response |
|--------|------|------|----------|
| GET | `/api/v1/matches/` | JWT required | `list[MatchResponse]` ordered by score DESC, cursor paginated |
| GET | `/api/v1/jobs/{job_id}/match` | JWT required | `MatchResponse` (200), `{"status":"pending"}` (202), 404 if job not found |

## Three-Branch Logic for GET /jobs/{id}/match

1. Pre-computed row exists in `job_matches` → return immediately
2. Job or profile embedding is `None` → 202 with `{"status": "pending", "score": null, "job_id": ...}`
3. Both embeddings present → compute via `SELECT (1 - embedding.cosine_distance(profile_embedding))` scoped to the single job, upsert, commit, return

## Test Results

44 tests passed, 0 failures (full suite including Phase 1 + 2 + 3 tests).

## Deviations from Plan

None - plan executed exactly as written. The pgvector DB approach was used as specified (not the numpy/zip loop variant the plan explicitly deprecated).

## Known Stubs

None.

## Threat Flags

None - endpoints are read-only (GET) and write only to `job_matches` for the authenticated user's own data. Auth gate enforced via `get_current_user` on both endpoints.

## Self-Check

- `from jobplatform.matching.router import router` → OK (verified via python -c)
- Routes `/api/v1/matches/` and `/api/v1/jobs/{job_id}/match` in OpenAPI schema → CONFIRMED
- `uv run pytest tests/ -q --tb=short` → 44 passed
