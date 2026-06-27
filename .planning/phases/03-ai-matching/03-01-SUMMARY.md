---
phase: "03"
plan: "01"
subsystem: "matching"
tags: ["openai", "embeddings", "tenacity", "text-composition", "ats-scoring"]
dependency_graph:
  requires: []
  provides: ["matching.service.get_embedding", "matching.service.build_job_text", "matching.service.build_profile_text", "matching.service.compute_ats_score", "matching.service.compute_skill_gaps"]
  affects: ["phase-3 celery tasks", "phase-3 match router"]
tech_stack:
  added: ["openai==2.44.0", "tenacity==9.1.4"]
  patterns: ["async retry with exponential backoff", "pure function text composition"]
key_files:
  created:
    - src/jobplatform/matching/__init__.py
    - src/jobplatform/matching/service.py
  modified:
    - pyproject.toml
    - uv.lock
    - src/jobplatform/config.py
decisions:
  - "openai_api_key defaults to empty string so tests can mock AsyncOpenAI without env var"
  - "get_embedding uses tenacity retry: 5 attempts, exp backoff 2-60s, reraise=True"
  - "build_job_text truncates description to 3000 chars and requirements JSON to 1000 chars"
  - "compute_skill_gaps accepts both list-under-'skills' key and flat string values in requirements dict"
metrics:
  duration: "~5 minutes"
  completed: "2026-06-27"
  tasks_completed: 2
  files_changed: 5
---

# Phase 3 Plan 01: Embedding Service Summary

JWT auth with refresh rotation using jose library — **OpenAI embedding service with tenacity retry, pure text composition helpers, and ATS scoring utilities for the matching package.**

## What Was Built

Created the `matching` package foundation that all Phase 3 plans depend on:

- **`openai_api_key` setting** in `Settings` class (default `""`, never raises on missing key)
- **`get_embedding(text)`** — async function calling `text-embedding-3-small`, decorated with tenacity retry on `RateLimitError` (5 attempts, exponential backoff 2–60s, reraise=True)
- **`build_job_text(job)`** — composes `title at company in location` + truncated description + requirements JSON
- **`build_profile_text(profile, prefs)`** — composes current role, experience years, skills, work history, and preference fields into a single string
- **`compute_ats_score(profile_skills, job_text)`** — returns fraction of profile skills found in job text (0.0–1.0)
- **`compute_skill_gaps(profile_skills, requirements)`** — returns requirement skills absent from profile, supporting both `{"skills": [...]}` and flat dict formats

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add dependencies and settings key | 6a56d4c | pyproject.toml, uv.lock, config.py |
| 2 | Create matching package with service.py | b5fdb49 | matching/__init__.py, matching/service.py |

## Verification Results

- `from jobplatform.matching.service import get_embedding, build_job_text, build_profile_text, compute_ats_score, compute_skill_gaps` → OK
- `hasattr(settings, 'openai_api_key')` → True, prints `""`
- `uv run pytest tests/ -q --tb=short` → 44 passed, 0 failures

## Deviations from Plan

None - plan executed exactly as written.

Note: `openai 2.44.0` and `tenacity 9.1.4` were installed (plan specified `>=1.35.0` and `>=8.2.0` respectively) — all constraints satisfied.

## Known Stubs

None. The matching service functions are fully implemented. `get_embedding` requires a real OpenAI API key at runtime, but tests will mock `AsyncOpenAI` as specified by the plan.

## Self-Check: PASSED

- src/jobplatform/matching/__init__.py — FOUND
- src/jobplatform/matching/service.py — FOUND
- commit 6a56d4c — verified in git log
- commit b5fdb49 — verified in git log
- 44 tests pass
