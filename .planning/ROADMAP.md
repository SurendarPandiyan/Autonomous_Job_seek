# Roadmap: Job Platform

## Overview

Build a job aggregation + AI matching platform in three phases: auth foundation, job discovery pipeline, and AI-powered match scoring.

## Phases

- [x] **Phase 1: Foundation** - Auth, user profiles, preferences, resume storage
- [x] **Phase 2: Job Discovery** - Portal adapters, scraping workers, jobs API
- [x] **Phase 3: AI Matching** - Embeddings, pgvector similarity, match scoring, match API
- [ ] **Phase 4: Application Automation** - One-click apply, ATS resume tailoring, application tracking

## Phase Details

### Phase 1: Foundation
**Goal**: Auth system + user profiles + job preferences + resume storage live and tested
**Depends on**: Nothing (first phase)
**Requirements**: (pre-GSD)
**Success Criteria** (what must be TRUE):
  1. User can register, login, and manage JWT sessions
  2. User profiles, preferences, and resumes are stored and retrievable
  3. 27 tests pass, 95% coverage
**Plans**: 4 plans (completed pre-GSD)

Plans:
- [x] 01-01: Auth endpoints (register/login/refresh/logout)
- [x] 01-02: User profile CRUD
- [x] 01-03: Job preferences CRUD
- [x] 01-04: Resume upload and storage

### Phase 2: Job Discovery
**Goal**: Portal scraping pipeline discovers, deduplicates, and stores jobs from 4 portals
**Depends on**: Phase 1
**Requirements**: (pre-GSD)
**Success Criteria** (what must be TRUE):
  1. Scrape worker runs for Naukri, LinkedIn, Indeed, Wellfound portals
  2. Jobs are deduplicated by SHA-256 hash and stored in DB
  3. GET /api/v1/jobs/ and POST /workers/scrape endpoints work
  4. 44 tests pass, 86% coverage
**Plans**: 4 plans (completed pre-GSD)

Plans:
- [x] 02-01: Portal registry + base adapter + 4 adapters
- [x] 02-02: Job model + alembic migration + upsert service
- [x] 02-03: Celery scrape task + workers API
- [x] 02-04: Jobs API (list + detail)

### Phase 3: AI Matching
**Goal**: AI-powered job matching using pgvector similarity between job and profile embeddings
**Depends on**: Phase 2
**Requirements**: REQ-01, REQ-02, REQ-03, REQ-04, REQ-05, REQ-06
**Success Criteria** (what must be TRUE):
  1. Jobs and user profiles have embeddings generated via OpenAI text-embedding-3-small
  2. JobMatch records created with cosine similarity score, ATS score, skill gaps
  3. Match scoring Celery worker enqueues and runs asynchronously
  4. GET /api/v1/matches/ returns ranked matches for authenticated user
  5. GET /api/v1/jobs/{id}/match returns match score for a specific job
**Plans**: 7 plans

Plans:
- [x] 03-01-PLAN.md — Embedding service (OpenAI client, get_embedding, build_job_text, build_profile_text, compute_ats_score, compute_skill_gaps)
- [x] 03-02-PLAN.md — JobMatch model + Alembic migration 0006 + HNSW index on jobs.embedding
- [x] 03-03-PLAN.md — Job embedding Celery task (embed_jobs_batch, batches jobs missing embeddings)
- [x] 03-04-PLAN.md — Profile embedding Celery task (embed_profile, hooks into profile/preferences update endpoints)
- [x] 03-05-PLAN.md — Match scoring Celery task (compute_matches_for_user, cosine sim + ATS + skill gaps + upsert)
- [x] 03-06-PLAN.md — Match router (GET /api/v1/matches/, GET /api/v1/jobs/{id}/match, schemas)
- [x] 03-07-PLAN.md — Integration test suite for all Phase 3 features (13 tests)

### Phase 4: Application Automation
**Goal**: Users can apply to matched jobs with one click, with resumes tailored per job and applications tracked
**Depends on**: Phase 3
**Requirements**: REQ-07, REQ-08, REQ-09, REQ-10, REQ-11
**Success Criteria** (what must be TRUE):
  1. User can trigger application to a job from the matches list
  2. Resume is tailored to job description using LLM before applying
  3. Application status tracked (pending/applied/rejected/interview)
  4. GET /api/v1/applications/ lists all user applications with status
  5. Application history persisted and queryable
**Plans**: 6 plans

Plans:
- [x] 04-01-PLAN.md — Application model (ApplicationStatus enum + Application ORM) + Alembic migration 0007
- [x] 04-02-PLAN.md — Anthropic SDK install + settings key + tailor_resume + extract_resume_text service functions
- [x] 04-03-PLAN.md — Application CRUD service (create/get/list/update_status) + Pydantic schemas
- [x] 04-04-PLAN.md — Celery tailor_and_apply task (pending→tailoring→applied transitions) + applier queue
- [x] 04-05-PLAN.md — FastAPI router (POST /api/v1/applications/ 202, GET /api/v1/applications/) + main.py
- [x] 04-06-PLAN.md — 13 pytest-asyncio tests covering REQ-07 through REQ-11

## Progress

**Execution Order:** 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 4/4 | Complete | 2026-06-27 |
| 2. Job Discovery | 4/4 | Complete | 2026-06-27 |
| 3. AI Matching | 7/7 | Complete | 2026-06-27 |
| 4. Application Automation | 6/6 | Complete | 2026-06-27 |
