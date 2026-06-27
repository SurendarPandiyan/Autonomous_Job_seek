# Roadmap: Job Platform

## Current Milestone

Next milestone not yet defined. Run `/gsd:new-milestone` to start.

## Shipped Milestones

- **[v1.0 MVP](.planning/milestones/v1.0-ROADMAP.md)** — 4 phases, 21 plans, 72 tests, 3,989 LOC. Auth + portal scraping + AI matching + application automation. Shipped 2026-06-27.

<details>
<summary>v1.0 Phase Details</summary>

### Phase 1: Foundation
**Goal**: Auth system + user profiles + job preferences + resume storage live and tested
**Plans**: 4 (pre-GSD) | **Tests**: 27 | **Coverage**: 95%

- [x] 01-01: Auth endpoints (register/login/refresh/logout)
- [x] 01-02: User profile CRUD
- [x] 01-03: Job preferences CRUD
- [x] 01-04: Resume upload and storage

### Phase 2: Job Discovery
**Goal**: Portal scraping pipeline discovers, deduplicates, and stores jobs from 4 portals
**Plans**: 4 (pre-GSD) | **Tests**: 44 | **Coverage**: 86%

- [x] 02-01: Portal registry + base adapter + 4 adapters
- [x] 02-02: Job model + Alembic migration + upsert service
- [x] 02-03: Celery scrape task + workers API
- [x] 02-04: Jobs API (list + detail)

### Phase 3: AI Matching
**Goal**: AI-powered job matching using pgvector similarity between job and profile embeddings
**Plans**: 7 | **Tests**: 59 | **Coverage**: 87%

- [x] 03-01-PLAN.md — Embedding service (OpenAI, get_embedding, ATS scoring, skill gaps)
- [x] 03-02-PLAN.md — JobMatch model + Alembic migration 0006 + HNSW index
- [x] 03-03-PLAN.md — Job embedding Celery task (embed_jobs_batch)
- [x] 03-04-PLAN.md — Profile embedding Celery task (embed_profile)
- [x] 03-05-PLAN.md — Match scoring Celery task (cosine sim + upsert)
- [x] 03-06-PLAN.md — Match router (GET /api/v1/matches/, GET /api/v1/jobs/{id}/match)
- [x] 03-07-PLAN.md — Integration test suite

### Phase 4: Application Automation
**Goal**: Users can apply to matched jobs with one click, resumes tailored per job, applications tracked
**Plans**: 6 | **Tests**: 72 | **Coverage**: 87%

- [x] 04-01-PLAN.md — Application model + Alembic migration 0007
- [x] 04-02-PLAN.md — Anthropic SDK + tailor_resume service
- [x] 04-03-PLAN.md — Application CRUD service + Pydantic schemas
- [x] 04-04-PLAN.md — Celery tailor_and_apply task + applier queue
- [x] 04-05-PLAN.md — FastAPI router (POST /api/v1/applications/ 202, GET /api/v1/applications/)
- [x] 04-06-PLAN.md — 13 tests covering REQ-07..REQ-11

</details>
