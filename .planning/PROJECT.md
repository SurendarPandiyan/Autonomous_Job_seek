# Job Platform

## What This Is

A job-applying portal that aggregates listings from Naukri, LinkedIn, Indeed, and Wellfound, scores them against user profiles using AI embeddings, and surfaces the best matches. Users can apply with LLM-tailored resumes in one click. Built for solo job seekers who want smart filtering without manual browsing.

## Current State (v1.0 — Shipped 2026-06-27)

**All 4 phases complete. 21 plans. 72 tests. 3,989 LOC.**

- Auth + user profiles + preferences + resume storage (Phase 1)
- Portal registry + Celery scraping + jobs API (Phase 2)
- OpenAI embeddings + pgvector HNSW + match scoring + match API (Phase 3)
- Application model + LLM resume tailoring + Celery applier + applications API (Phase 4)

**Live endpoints:**
- `POST /api/v1/auth/register` + `POST /api/v1/auth/login`
- `GET/PUT /api/v1/profiles/me`
- `GET/PUT /api/v1/preferences/`
- `POST /api/v1/resumes/`
- `GET /api/v1/jobs/` + `GET /api/v1/jobs/{id}`
- `POST /workers/scrape` + `POST /workers/embed-jobs` + `POST /workers/embed-profile`
- `GET /api/v1/matches/` + `GET /api/v1/jobs/{id}/match`
- `POST /api/v1/applications/` (202 Accepted, queues LLM tailoring)
- `GET /api/v1/applications/`

## Core Value

Surface the most relevant job matches to the user automatically, ranked by fit.

## Stack

- FastAPI + SQLAlchemy async + asyncpg + PostgreSQL + pgvector
- Celery 5 + Redis (scraper queue, embedder queue, applier queue)
- OpenAI text-embedding-3-small (1536 dims) for job + profile embeddings
- Anthropic claude-haiku-4-5 for resume tailoring
- Alembic migration chain: 0000→a4cc→0002→0003→0004→0005→0006→0007
- Python 3.12, uv, pytest-asyncio

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| ORM | SQLAlchemy async + asyncpg | Non-blocking DB in FastAPI |
| Migrations | Alembic explicit (no autogenerate) | Avoids pgvector ischema_names issues |
| Embedding model | text-embedding-3-small | 1536 dims matches Vector slot; cost-effective |
| Similarity | pgvector cosine_distance | Standard for semantic similarity |
| Match storage | Materialized JobMatch table | Enables offline ranking, ATS scoring |
| Celery async | asyncio.run() wrapper | Bridges sync Celery with async service layer |
| LLM tailoring | claude-haiku-4-5 | Cost-effective, sufficient quality |
| Apply pattern | 202 Accepted + Celery | Never blocks request path on LLM |

## Next Milestone

Not yet defined. Candidates:
- Real portal scraping (replace mock adapters with actual httpx+BS4)
- Actual portal submission for REQ-09
- Resume parsing from PDF upload
- Job alert notifications
- Dashboard / status UI

Run `/gsd:new-milestone` to start planning v1.1.

<details>
<summary>v1.0 Requirements (archived)</summary>

See [.planning/milestones/v1.0-REQUIREMENTS.md](.planning/milestones/v1.0-REQUIREMENTS.md)

</details>
