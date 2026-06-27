---
phase: "03"
plan: "02"
subsystem: matching
tags: [orm, alembic, pgvector, hnsw, migration]
dependency_graph:
  requires: ["03-01"]
  provides: ["job_matches table", "JobMatch ORM model", "HNSW index on jobs.embedding"]
  affects: ["matching/service.py", "alembic chain"]
tech_stack:
  added: ["pgvector ischema_names patch"]
  patterns: ["Mapped column style", "hand-written Alembic migration", "HNSW index via op.execute"]
key_files:
  created:
    - src/jobplatform/matching/models.py
    - alembic/versions/0006_create_job_matches.py
  modified:
    - alembic/env.py
decisions:
  - "down_revision set to 680fa3a8317e (the actual UUID of 0005_create_jobs) — plan doc said '0005' but alembic uses UUID revisions"
  - "pgvector ischema_names patch placed inside configure() callable passed to run_sync so dialect is patched per-connection"
metrics:
  duration: "~8 min"
  completed: "2026-06-27"
---

# Phase 3 Plan 02: JobMatch Model and Alembic Migration Summary

**One-liner:** JobMatch ORM model with MatchStatus enum, plus hand-written migration 0006 that creates job_matches table and HNSW cosine index on jobs.embedding.

## What Was Built

- `src/jobplatform/matching/models.py` — `MatchStatus` enum (new/saved/applied/dismissed) and `JobMatch` SQLAlchemy model with unique constraint on (user_id, job_id), score/ats_score/skill_gaps columns, and timezone-aware timestamps.
- `alembic/env.py` — Two patches: (1) import `jobplatform.matching.models` to register `JobMatch` with `Base.metadata`; (2) replace the `run_migrations_online` lambda with a named `configure()` function that patches `conn.dialect.ischema_names["vector"] = Vector` before calling `context.configure`, preventing autogenerate from emitting `NullType` for the existing `jobs.embedding` column.
- `alembic/versions/0006_create_job_matches.py` — Hand-written migration: `job_matches` table with all required columns, unique constraint `uq_job_matches_user_job`, indexes on user_id/job_id/score, and HNSW index on `jobs.embedding` via `op.execute("CREATE INDEX IF NOT EXISTS ...")`.

## Verification Results

- `uv run python -c "from jobplatform.matching.models import JobMatch, MatchStatus; print(MatchStatus.new.value)"` → `new`
- `uv run alembic upgrade head` → exit 0
- `uv run alembic current` → `0006 (head)`
- `uv run pytest tests/ -q` → 44 passed, 3 warnings

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed incorrect down_revision in migration 0006**
- **Found during:** Task 2, first migration attempt
- **Issue:** Plan instructed `down_revision = "0005"` but Alembic uses UUID revision IDs. The 0005_create_jobs migration has `revision = "680fa3a8317e"`. Setting `"0005"` caused a `KeyError: '0005'` at runtime.
- **Fix:** Set `down_revision = "680fa3a8317e"` to match the actual UUID.
- **Files modified:** `alembic/versions/0006_create_job_matches.py`
- **Commit:** 39a6643

## Self-Check: PASSED

- [x] `src/jobplatform/matching/models.py` exists
- [x] `alembic/versions/0006_create_job_matches.py` exists
- [x] `alembic/env.py` patched
- [x] Commits 5d4cc88 and 39a6643 exist
- [x] `alembic current` shows `0006 (head)`
- [x] 44 tests pass
