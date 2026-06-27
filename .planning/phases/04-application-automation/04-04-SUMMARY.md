---
phase: "04"
plan: "04-04"
subsystem: "applications"
tags: ["celery", "async", "task", "asyncio-run", "status-transitions"]
dependency_graph:
  requires: ["04-01", "04-02"]
  provides: ["tailor_and_apply Celery task", "applier queue registration"]
  affects: ["celery_app.py", "applications/tasks.py"]
tech_stack:
  added: []
  patterns: ["asyncio.run wrapper for async Celery task", "pending→tailoring→applied status machine"]
key_files:
  created:
    - src/jobplatform/applications/tasks.py
  modified:
    - src/jobplatform/celery_app.py
decisions:
  - "Open AsyncSessionLocal() inside async impl, never pass session across sync/async boundary"
  - "Guard with status != pending check to prevent duplicate execution"
  - "Reset status to pending on exception for clean Celery retry"
metrics:
  duration: "~5 minutes"
  completed: "2026-06-27"
  tasks_completed: 2
  tasks_total: 2
---

# Phase 04 Plan 04: Celery Task tailor_and_apply Summary

## One-liner

Registered applier queue in celery_app.py and created tailor_and_apply Celery task using asyncio.run pattern with pending→tailoring→applied status machine.

## What Was Done

**Task 1 — celery_app.py update (commit b3c8c3e):**
- Added `jobplatform.applications.tasks` to the `include=` list in the Celery constructor
- Added `jobplatform.applications.tasks.tailor_and_apply → applier` queue in `task_routes`
- Only additive changes; no existing entries modified

**Task 2 — tasks.py creation (commit 7624376):**
- Created `src/jobplatform/applications/tasks.py` with sync entry point `tailor_and_apply` decorated `@celery_app.task(bind=True)`
- Delegates to `_tailor_and_apply_async` via `asyncio.run`
- Opens `AsyncSessionLocal()` internally; never accepts a session parameter
- Status transitions: pending → tailoring (committed before LLM call) → applied (on success); resets to pending on any exception
- Calls `extract_resume_text(resume)` and `await tailor_resume(resume_text, job_description)` from service layer
- Skips processing if status is not pending (duplicate-execution guard)

## Verification Results

All self-checks green:
- `tailor_and_apply.name` prints `jobplatform.applications.tasks.tailor_and_apply`
- `celery_app.conf.task_routes` contains the applier queue entry
- `uv run pytest tests/ -q --tb=short` — 59 passed, 0 failed

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — no hardcoded placeholder values or TODO stubs.

## Threat Flags

None — no new network endpoints, auth paths, or trust-boundary changes introduced. Task logic is internal queue processing only.

## Self-Check: PASSED

- [x] `src/jobplatform/applications/tasks.py` created — FOUND
- [x] `src/jobplatform/celery_app.py` modified — FOUND
- [x] Commit b3c8c3e exists — FOUND
- [x] Commit 7624376 exists — FOUND
- [x] All 59 tests pass — CONFIRMED
