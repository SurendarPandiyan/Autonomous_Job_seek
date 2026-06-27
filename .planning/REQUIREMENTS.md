# Requirements

## Phase 4: Application Automation

- REQ-07: Application model (user_id, job_id, status, tailored_resume_text, applied_at)
- REQ-08: LLM-powered resume tailoring per job description before applying
- REQ-09: One-click apply endpoint that submits tailored resume to portal
- REQ-10: Application status tracking (pending/applied/rejected/interview/offer)
- REQ-11: GET /api/v1/applications/ listing all user applications with status and job details

## Phase 3: AI Matching Engine

- REQ-01: Generate embeddings for jobs and user profiles using OpenAI text-embedding-3-small
- REQ-02: JobMatch model storing user_id, job_id, score, ats_score, skill_gaps, status
- REQ-03: pgvector cosine similarity search matching profiles to jobs
- REQ-04: Match scoring Celery worker that runs asynchronously
- REQ-05: GET /api/v1/jobs/{id}/match endpoint returning match score for a job
- REQ-06: GET /api/v1/matches/ endpoint listing ranked matches for current user
