# Job Platform

## What This Is

A job-applying portal that aggregates listings from Naukri, LinkedIn, Indeed, and Wellfound, scores them against user profiles using AI embeddings, and surfaces the best matches for the user. Built for solo job seekers who want smart filtering without manual browsing.

## Core Value

Surface the most relevant job matches to the user automatically, ranked by fit.

## Requirements

### Validated

- Auth + user profiles + job preferences + resume storage (Phase 1 — 27 tests, 95% cov)
- Portal scraping + job discovery + deduplication + jobs API (Phase 2 — 44 tests, 86% cov)

### Active

- REQ-01: Generate embeddings for jobs and user profiles using OpenAI text-embedding-3-small
- REQ-02: JobMatch model storing user_id, job_id, score, ats_score, skill_gaps, status
- REQ-03: pgvector cosine similarity search matching profiles to jobs
- REQ-04: Match scoring Celery worker that runs asynchronously
- REQ-05: GET /api/v1/jobs/{id}/match endpoint returning match score for a job
- REQ-06: GET /api/v1/matches/ endpoint listing ranked matches for current user

### Out of Scope

- Multi-user job application tracking — out of scope for Phase 3; deferred to Phase 4
- Resume parsing/extraction — user provides structured data directly

## Context

- FastAPI + SQLAlchemy async + PostgreSQL + pgvector + Celery 5 + Redis
- Python 3.12, uv, pytest-asyncio
- Phase 2 left Vector(1536) slots ready in jobs.embedding; no embedding values yet
- Profile data in users/profiles/preferences/resumes tables from Phase 1
- Alembic migration chain: 0000→a4cc→0002→0003→0004→0005

## Constraints

- **Tech stack**: OpenAI embeddings (text-embedding-3-small, 1536 dims) — matches Vector(1536) in jobs table
- **Async**: All DB and HTTP operations must be async
- **Testing**: pytest-asyncio with real DB (no mocks for DB layer)
- **Package manager**: uv

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Embedding model | text-embedding-3-small | 1536 dims matches existing Vector slot; cost-effective |
| Similarity metric | cosine | Standard for semantic similarity with normalized embeddings |
| Match storage | Materialized in JobMatch table | Enables offline ranking, status tracking, ATS scoring |
| Dedup strategy | SHA-256 hash on title+company+location | Already live from Phase 2 |
