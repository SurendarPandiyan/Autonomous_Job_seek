# Roadmap: Job Platform

## Overview

Build a job aggregation + AI matching platform in three phases: auth foundation, job discovery pipeline, and AI-powered match scoring.

## Phases

- [x] **Phase 1: Foundation** - Auth, user profiles, preferences, resume storage
- [x] **Phase 2: Job Discovery** - Portal adapters, scraping workers, jobs API
- [ ] **Phase 3: AI Matching** - Embeddings, pgvector similarity, match scoring, match API

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
- [ ] 03-07-PLAN.md — Integration test suite for all Phase 3 features (13 tests)

## Progress

**Execution Order:** 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 4/4 | Complete | 2026-06-27 |
| 2. Job Discovery | 4/4 | Complete | 2026-06-27 |
| 3. AI Matching | 6/7 | In Progress|  |
