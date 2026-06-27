# Phase 3: AI Matching Engine — Research

**Researched:** 2026-06-27
**Domain:** OpenAI Embeddings + pgvector cosine similarity + Celery async workers + FastAPI
**Confidence:** HIGH

---

## Summary

Phase 3 adds AI-powered job matching on top of the existing FastAPI/SQLAlchemy/Celery stack.
The core machinery is: generate 1536-dim embeddings for jobs and user profiles via OpenAI
`text-embedding-3-small`, store them in the `Vector(1536)` columns already provisioned in
`jobs`, `profiles`, and `resumes` tables, then run pgvector cosine similarity to rank matches
and store results in a new `job_matches` table.

The codebase is clean and well-structured. Every domain follows the same service/router/schemas/tasks
module layout. Phase 3 should add a new `matching/` domain package containing the embedding
service, the match scoring service, Celery tasks, and a router — parallel to the existing
`jobs/`, `profiles/`, `workers/` packages. There is no need to touch existing models beyond
registering the new model in `env.py`.

The two key risks are (1) the Alembic autogenerate does not recognise the pgvector `vector`
type without a patch to `env.py`, and (2) OpenAI rate limits require backoff handling in the
Celery workers. Both are well-understood and have standard mitigations documented below.

**Primary recommendation:** Add a `src/jobplatform/matching/` package with an async embedding
service backed by `AsyncOpenAI` + `tenacity`, a `JobMatch` ORM model, a Celery task for batch
match scoring, and two GET endpoints. Follow existing `asyncio.run(_async_impl)` pattern for
all Celery tasks.

---

## Existing Pattern Analysis

### Module structure (what Phase 3 must mirror)
```
src/jobplatform/
├── jobs/
│   ├── models.py      # SQLAlchemy ORM + helpers
│   ├── service.py     # async DB functions (no HTTP, no Celery)
│   ├── schemas.py     # Pydantic request/response models
│   ├── tasks.py       # Celery tasks — always sync wrapper calling asyncio.run()
│   └── router.py      # FastAPI router — uses Depends(get_current_user), Depends(get_db)
└── workers/
    ├── service.py     # publish_log, get_task_status
    └── router.py      # /workers/scrape, /workers/tasks/{id}
```

### Celery task convention (from `jobs/tasks.py`)
All Celery tasks are synchronous wrappers over an `async def _impl_async(...)` function
called via `asyncio.run()`. The async function opens `AsyncSessionLocal()` as a context
manager to get a DB session. Never pass an `AsyncSession` across the sync/async boundary.

```python
@celery_app.task(name="...", bind=True)
def my_task(self, ...) -> dict:
    task_id = self.request.id or "local"
    return asyncio.run(_my_task_async(..., task_id))

async def _my_task_async(..., task_id: str) -> dict:
    async with AsyncSessionLocal() as db:
        ...
```

### Dependency injection for auth (from `jobs/router.py`)
```python
current_user: User = Depends(get_current_user)
db: AsyncSession = Depends(get_db)
```
Both are imported from `jobplatform.dependencies` and `jobplatform.database`.

### Test patterns (from `tests/conftest.py` and `tests/test_scrape_worker.py`)
- Session-scoped `setup_db` fixture creates/drops all tables on a real test PostgreSQL.
- `db` fixture yields a real `AsyncSession` with rollback after each test.
- `client` fixture overrides `get_db` to inject the test session.
- Celery task tests patch `AsyncSessionLocal` to inject the test `db` fixture.
- OpenAI calls will need `unittest.mock.AsyncMock` patches on `AsyncOpenAI`.

### Config pattern (from `config.py`)
`pydantic-settings` `BaseSettings` with `env_file=".env"`. Add `openai_api_key: str` with
a default of `""` (empty string, so tests without the key still import). Access via
`settings.openai_api_key`.

### Alembic env.py (from `alembic/env.py`)
The `run_migrations_online` function uses `await connection.run_sync(lambda conn: context.configure(conn, ...))`.
The pgvector fix must be applied _inside_ that lambda so the dialect patch is in scope when
the sync configure call reads column types.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|---|---|---|---|
| Embedding text composition | API/Backend service | — | Pure Python, no I/O |
| OpenAI embedding API call | API/Backend service | Celery Worker | Called from both |
| Rate limit retry | API/Backend service | — | tenacity decorator on service fn |
| Job embedding batch | Celery Worker | — | Long-running, async, rate-limited |
| Profile embedding | Celery Worker | — | Same |
| Cosine similarity search | Database (pgvector) | API/Backend | HNSW index accelerated |
| ATS score + skill gap | API/Backend service | — | Pure Python post-query |
| Match upsert | Celery Worker | — | Batch, tied to scoring task |
| Match endpoints | API/Backend router | Database | REST, auth-gated |

---

## Standard Stack

### Core (new packages to add)

| Library | Version | Purpose | Why Standard |
|---|---|---|---|
| `openai` | `>=1.35.0` | AsyncOpenAI client, embeddings.create | Official OpenAI Python SDK [VERIFIED: npm registry / PyPI] |
| `tenacity` | `>=8.2.0` | Retry with exponential backoff on RateLimitError | Standard retry library for Python [VERIFIED: PyPI] |

### Already present (no new install needed)

| Library | Version | Purpose |
|---|---|---|
| `pgvector` | `>=0.2.5` | `Vector(1536)` column type + `.cosine_distance()` ORM method |
| `sqlalchemy[asyncio]` | `>=2.0.30` | Async session + query DSL |
| `celery[redis]` | `>=5.3.6` | Task queue, existing `celery_app` factory |
| `structlog` | `>=24.1.0` | Logging (match existing style) |

**Installation (new deps only):**
```bash
uv add "openai>=1.35.0" "tenacity>=8.2.0"
```

**Version verification:**
- `openai`: latest on PyPI is `1.109.1` as of research date. Pin `>=1.35.0` for AsyncOpenAI stability. [VERIFIED: PyPI]
- `tenacity`: latest is `9.1.4`. Pin `>=8.2.0`. [VERIFIED: PyPI]
- `pgvector`: latest is `0.4.2`, project uses `0.2.5` minimum — current install is sufficient. [VERIFIED: PyPI]

---

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---|---|---|---|---|---|---|
| `openai` | PyPI | ~6 yrs | Very high | github.com/openai/openai-python | [OK] | Approved |
| `tenacity` | PyPI | ~8 yrs | Very high | github.com/jd/tenacity | [OK] | Approved |
| `pgvector` | PyPI | ~3 yrs | High | github.com/pgvector/pgvector-python | [OK] | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### System Architecture Diagram

```
User request (GET /matches/)
        │
        ▼
FastAPI router (matching/router.py)
   get_current_user ──► JWT decode ──► User.id
        │
        ▼
matching/service.py: list_matches(db, user_id)
        │
        ▼
SELECT job_matches WHERE user_id = ? ORDER BY score DESC
        │
        ▼
JSON response (MatchResponse list)


POST /workers/embed-jobs  ──► Celery: embed_jobs_batch
                                        │
                                        ▼
                            SELECT jobs WHERE embedding IS NULL LIMIT 20
                                        │
                                        ▼
                            build_job_text(job) → str
                                        │
                                        ▼
                            AsyncOpenAI.embeddings.create(...)  ◄── tenacity retry
                                        │
                                        ▼
                            UPDATE jobs SET embedding = ?
                                        │
                                        ▼
                            repeat until all embedded


POST /workers/compute-matches  ──► Celery: compute_matches_for_user(user_id)
                                        │
                                        ▼
                            load Profile + JobPreferences
                                        │
                                        ▼
                            build_profile_text(...) → str
                                        │
                                        ▼
                            get_embedding(text) ◄── AsyncOpenAI + tenacity
                                        │
                                        ▼
                            pgvector cosine_distance query (HNSW index)
                            → top-50 (Job, score) rows
                                        │
                                        ▼
                            for each row: ats_score, skill_gaps
                                        │
                                        ▼
                            UPSERT job_matches (user_id, job_id, score, ats_score, skill_gaps)
```

### Recommended Project Structure

```
src/jobplatform/
├── matching/
│   ├── __init__.py
│   ├── models.py        # JobMatch ORM model + MatchStatus enum
│   ├── service.py       # async embedding + match service functions
│   ├── schemas.py       # MatchResponse, MatchStatusUpdate Pydantic models
│   ├── tasks.py         # Celery tasks: embed_jobs_batch, embed_profile, compute_matches_for_user
│   └── router.py        # GET /api/v1/jobs/{id}/match, GET /api/v1/matches/
tests/
└── test_matching.py     # embedding mock + match task + endpoint tests
alembic/versions/
└── 0006_create_job_matches.py   # JobMatch table + HNSW index
```

### Pattern 1: Async OpenAI embedding service with tenacity

```python
# src/jobplatform/matching/service.py
# Source: openai-python docs + tenacity docs
from openai import AsyncOpenAI, RateLimitError
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from jobplatform.config import settings

@retry(
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type(RateLimitError),
    reraise=True,
)
async def get_embedding(text: str) -> list[float]:
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return response.data[0].embedding
```

### Pattern 2: pgvector cosine similarity search (async SQLAlchemy)

```python
# Source: pgvector-python README (github.com/pgvector/pgvector-python)
from sqlalchemy import select
from jobplatform.jobs.models import Job

async def find_similar_jobs(
    db: AsyncSession,
    profile_embedding: list[float],
    limit: int = 50,
) -> list[tuple[Job, float]]:
    stmt = (
        select(Job, (1 - Job.embedding.cosine_distance(profile_embedding)).label("score"))
        .where(Job.is_active == True, Job.embedding.is_not(None))
        .order_by(Job.embedding.cosine_distance(profile_embedding))
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [(row.Job, row.score) for row in result]
```

Note: `cosine_distance` returns 0 (identical) to 2 (opposite). Score = `1 - distance`
gives a 1..−1 similarity where 1 = perfect match.

### Pattern 3: Profile embedding text composition

```python
# Source: domain knowledge [ASSUMED] — adjust based on observed match quality
def build_profile_text(profile: Profile, prefs: JobPreferences | None) -> str:
    parts = []
    if profile.current_role:
        parts.append(f"Current role: {profile.current_role}")
    if profile.years_experience:
        parts.append(f"Years of experience: {profile.years_experience}")
    if profile.skills:
        parts.append(f"Skills: {', '.join(profile.skills)}")
    if profile.experience:
        roles = [
            f"{e.get('title', '')} at {e.get('company', '')}"
            for e in profile.experience
            if e.get("title")
        ]
        if roles:
            parts.append(f"Experience: {'; '.join(roles)}")
    if prefs:
        if prefs.target_roles:
            parts.append(f"Target roles: {', '.join(prefs.target_roles)}")
        if prefs.technologies:
            parts.append(f"Technologies: {', '.join(prefs.technologies)}")
        if prefs.locations:
            parts.append(f"Preferred locations: {', '.join(prefs.locations)}")
    return "\n".join(parts)
```

### Pattern 4: Job embedding text composition

```python
import json

def build_job_text(job: Job) -> str:
    parts = [f"{job.title} at {job.company} in {job.location}"]
    if job.description:
        parts.append(job.description[:3000])  # guard against very long descriptions
    if job.requirements:
        req_str = json.dumps(job.requirements)[:1000]
        parts.append(f"Requirements: {req_str}")
    return "\n".join(parts)
```

### Pattern 5: Celery task following existing asyncio.run() convention

```python
# src/jobplatform/matching/tasks.py
import asyncio
from jobplatform.celery_app import celery_app
from jobplatform.database import AsyncSessionLocal

async def _embed_jobs_batch_async(task_id: str) -> dict:
    async with AsyncSessionLocal() as db:
        ...  # fetch, embed, update

@celery_app.task(name="jobplatform.matching.tasks.embed_jobs_batch", bind=True)
def embed_jobs_batch(self) -> dict:
    return asyncio.run(_embed_jobs_batch_async(self.request.id or "local"))
```

### Pattern 6: ATS score + skill gaps (pure Python, post-query)

```python
def compute_ats_score(profile_skills: list[str], job_text: str) -> float:
    if not profile_skills:
        return 0.0
    job_lower = job_text.lower()
    matched = sum(1 for s in profile_skills if s.lower() in job_lower)
    return round(matched / len(profile_skills), 4)

def compute_skill_gaps(profile_skills: list[str], requirements: dict | None) -> list[str]:
    """Skills listed in job requirements not present in profile."""
    if not requirements:
        return []
    req_text = json.dumps(requirements).lower()
    # Extract requirement skill tokens: look for ARRAY-like values in requirements dict
    req_skills = [
        v for v in requirements.values()
        if isinstance(v, str) and len(v) < 60
    ]
    if isinstance(requirements.get("skills"), list):
        req_skills = requirements["skills"]
    profile_lower = {s.lower() for s in profile_skills}
    return [s for s in req_skills if s.lower() not in profile_lower]
```

### Pattern 7: Alembic migration for job_matches with HNSW index

```python
# alembic/versions/0006_create_job_matches.py
# HNSW index MUST be hand-written — Alembic autogenerate cannot produce it.
def upgrade() -> None:
    op.create_table(
        "job_matches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("ats_score", sa.Float(), nullable=True),
        sa.Column("skill_gaps", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.Enum("new", "saved", "applied", "dismissed", name="matchstatus"), nullable=False, server_default="new"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "job_id", name="uq_job_matches_user_job"),
    )
    op.create_index("ix_job_matches_user_id", "job_matches", ["user_id"])
    op.create_index("ix_job_matches_score", "job_matches", ["score"])
    # HNSW index on jobs.embedding for cosine similarity — cannot be autogenerated
    op.execute(
        "CREATE INDEX IF NOT EXISTS jobs_embedding_hnsw "
        "ON jobs USING hnsw (embedding vector_cosine_ops) "
        "WITH (m=16, ef_construction=64)"
    )
```

### Anti-Patterns to Avoid

- **Calling `asyncio.run()` inside an already-running event loop:** Celery workers are sync, so `asyncio.run()` is correct there. Never use it inside a FastAPI route (already async). Use `await` there.
- **Creating a new `AsyncOpenAI` client per embedding call at scale:** Acceptable for now; avoid in hot paths. Cache client at module level if embedding volume grows.
- **Trusting `alembic revision --autogenerate` for Vector columns:** Autogenerate will not detect Vector column changes. Always write migration by hand for vector-related DDL.
- **Setting `Job.embedding` inside `upsert_job` synchronously:** OpenAI call is async and rate-limited. Never block the upsert. Use a post-upsert Celery task.
- **Returning `embedding` field in API responses:** Vector fields are large (1536 floats ≈ 6KB JSON). Always exclude from response schemas.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| Exponential backoff on rate limits | Custom sleep loop | `tenacity.retry` with `wait_exponential` | Handles jitter, max wait, reraise correctly |
| cosine similarity | NumPy dot products | `Job.embedding.cosine_distance()` (pgvector) | Index-accelerated in DB, no Python loop over rows |
| OpenAI async client | `httpx` direct calls | `openai.AsyncOpenAI` | Handles auth, retries, streaming, model routing |
| Vector DDL in migrations | Raw `op.execute("CREATE TYPE vector...")` | `from pgvector.sqlalchemy import Vector` in migration file | Correct type registration for pgvector |

**Key insight:** The pgvector cosine similarity query runs entirely in PostgreSQL with HNSW
index acceleration — fetching all embeddings into Python and computing similarity there would
be 100-1000x slower and break at any scale.

---

## Common Pitfalls

### Pitfall 1: Alembic autogenerate drops Vector columns
**What goes wrong:** Running `alembic revision --autogenerate` on a database that has
`vector` columns produces a migration that drops and recreates those columns, or produces
`op.alter_column` calls with `NullType`.
**Why it happens:** SQLAlchemy's schema reflection does not know how to interpret the
PostgreSQL `vector` type without the pgvector dialect patch.
**How to avoid:** In `alembic/env.py`, inside `run_migrations_online`, patch the dialect
ischema_names BEFORE calling `context.configure`:

```python
# In the run_sync lambda in run_migrations_online:
async def run_migrations_online() -> None:
    connectable = create_async_engine(_db_url)
    async with connectable.connect() as connection:
        def configure(conn):
            from pgvector.sqlalchemy import Vector
            conn.dialect.ischema_names["vector"] = Vector
            context.configure(conn, target_metadata=target_metadata)
        await connection.run_sync(configure)
        async with connection.begin():
            await connection.run_sync(lambda _: context.run_migrations())
    await connectable.dispose()
```

**Warning signs:** Migration file contains `op.alter_column('jobs', 'embedding', type_=NullType())`.

### Pitfall 2: AsyncMock for OpenAI nested attribute access
**What goes wrong:** `patch("jobplatform.matching.service.AsyncOpenAI")` patches the class,
but the test fails because `mock_instance.embeddings.create` is a regular `MagicMock`, not
an `AsyncMock`, so `await` raises `TypeError`.
**Why it happens:** `MagicMock` auto-specs attribute access but does not know `.create` must
be awaitable.
**How to avoid:** Explicitly set up the mock chain:

```python
from unittest.mock import AsyncMock, MagicMock, patch

FAKE_EMBEDDING = [0.1] * 1536

with patch("jobplatform.matching.service.AsyncOpenAI") as MockClient:
    instance = MagicMock()
    MockClient.return_value = instance
    mock_resp = MagicMock()
    mock_resp.data = [MagicMock(embedding=FAKE_EMBEDDING)]
    instance.embeddings.create = AsyncMock(return_value=mock_resp)

    result = await get_embedding("test text")
assert result == FAKE_EMBEDDING
```

**Warning signs:** `TypeError: object MagicMock can't be used in 'await' expression`.

### Pitfall 3: HNSW index created before table is populated
**What goes wrong:** Creating an HNSW index on an empty `embedding` column works, but if
you create it via `op.execute` without `IF NOT EXISTS`, the migration fails on re-run.
Also, HNSW index build is slow on large tables; do NOT set `ef_construction > 128` for < 100k rows.
**How to avoid:** Always use `CREATE INDEX IF NOT EXISTS`. Keep `m=16, ef_construction=64` for
typical job volumes (< 500k rows).

### Pitfall 4: Profile embedding stale after profile update
**What goes wrong:** User updates skills/experience, but `Profile.embedding` reflects old data.
Match scores stay stale until re-embedded.
**How to avoid:** In `profiles/service.py` `update_profile`, after `await db.commit()`,
dispatch a `embed_profile.delay(user_id=user_id)` Celery task. Similarly for preferences update.
Reset `Profile.enriched_at = None` before dispatch so stale state is detectable.

### Pitfall 5: N+1 queries in match scoring
**What goes wrong:** Loading profile, then preferences, then resumes in separate queries inside
the Celery task is three round-trips.
**How to avoid:** Use `select(Profile).options(selectinload(...))` if relationships are
defined, or issue three targeted `select` calls and collect before the embedding call.
Since the ORM models do not define SQLAlchemy `relationship()` columns, use explicit separate
queries but batch them before starting the embedding step.

### Pitfall 6: Passing `list[float]` instead of numpy array to cosine_distance
**What goes wrong:** pgvector-python 0.2.x required numpy arrays; 0.3.x+ accepts plain Python
lists. Current project pins `>=0.2.5` — if the installed version is 0.2.x, passing `list[float]`
will raise a `TypeError`.
**How to avoid:** The project's installed version should be `>=0.3.0`. Verify with
`uv pip show pgvector`. If stuck on 0.2.x, wrap: `import numpy as np; np.array(embedding, dtype=np.float32)`.
Alternatively, upgrade: `uv add "pgvector>=0.3.0"`.

---

## Implementation Decisions

### REQ-01: Embedding generation

**Profile text:** Concatenate `current_role`, `years_experience`, `skills[]`, `experience[]`
title+company pairs, `target_roles[]` from preferences, `technologies[]` from preferences.
Produces a short (~200-500 token) natural-language summary.

**Job text:** Concatenate `title`, `company`, `location`, `description[:3000]`, and JSON
summary of `requirements`. Cap at ~4000 tokens to stay well under the 8192 token limit.

**Trigger strategy:** Batch workers (`embed_jobs_batch`, `embed_profile`). On job upsert,
the scrape task already exists — add a post-upsert call `embed_jobs_batch.delay()` or
process inline at the end of `_scrape_portal_async`. For profiles, trigger on profile/preferences
update from the respective routers. Batch wins over inline because it handles failures and
rate limits without affecting the write path.

### REQ-02: JobMatch model

```python
class MatchStatus(enum.Enum):
    new = "new"
    saved = "saved"
    applied = "applied"
    dismissed = "dismissed"

class JobMatch(Base):
    __tablename__ = "job_matches"
    __table_args__ = (UniqueConstraint("user_id", "job_id", name="uq_job_matches_user_job"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    score: Mapped[float | None] = mapped_column(Float)       # cosine similarity 0..1
    ats_score: Mapped[float | None] = mapped_column(Float)   # keyword overlap 0..1
    skill_gaps: Mapped[list | None] = mapped_column(JSONB)   # list[str]
    status: Mapped[MatchStatus] = mapped_column(
        SAEnum(MatchStatus), default=MatchStatus.new, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
```

### REQ-03: pgvector cosine similarity

Use `Job.embedding.cosine_distance(profile_vec)` in the ORDER BY. Convert to similarity
score: `score = 1 - distance`. Query only rows where `Job.embedding IS NOT NULL` and
`Job.is_active = True`. HNSW index (`vector_cosine_ops`) created in migration 0006.

### REQ-04: Match scoring Celery task

Task: `compute_matches_for_user(user_id: int) -> dict`
1. Load `Profile` for user; load `JobPreferences` for user.
2. Build profile text string.
3. Call `await get_embedding(profile_text)` → `list[float]`.
4. Run cosine similarity query → top 50 (Job, score) rows.
5. For each: compute `ats_score`, `skill_gaps`.
6. Upsert into `job_matches` (ON CONFLICT (user_id, job_id) DO UPDATE SET score=...).
7. Return `{"user_id": user_id, "matched": N}`.

Use `INSERT ... ON CONFLICT DO UPDATE` via SQLAlchemy's `insert(...).on_conflict_do_update()`
from `sqlalchemy.dialects.postgresql`. This avoids select-then-insert N+1.

### REQ-05: GET /api/v1/jobs/{id}/match

Check for existing `JobMatch` for `(current_user.id, job_id)`. If found, return it.
If not found and `Job.embedding` exists and `Profile.embedding` exists, compute on-demand
(synchronous within the request, acceptable for single-job latency). If either embedding is
null, return `{"status": "pending", "score": null}` with 202.

### REQ-06: GET /api/v1/matches/

Return `job_matches` for `current_user.id`, ordered by `score DESC`, with cursor pagination
using `id` field (matching existing jobs endpoint pattern). Include job snapshot fields
(title, company, url) via a JOIN on `jobs`.

---

## Recommended Plan Split (Wave Grouping)

### Wave 0 — Foundation
- **Plan 03-01:** Settings + embedding service module
  - Add `openai_api_key: str = ""` to `config.py`
  - Add `openai>=1.35.0`, `tenacity>=8.2.0` to `pyproject.toml`
  - Create `src/jobplatform/matching/` package with `service.py` containing:
    - `get_embedding(text: str) -> list[float]` with tenacity retry
    - `build_job_text(job: Job) -> str`
    - `build_profile_text(profile: Profile, prefs: JobPreferences | None) -> str`
    - `compute_ats_score(...)`, `compute_skill_gaps(...)`

- **Plan 03-02:** JobMatch model + Alembic migration
  - Create `src/jobplatform/matching/models.py` with `JobMatch` + `MatchStatus`
  - Register import in `alembic/env.py`
  - Patch `env.py` with `ischema_names["vector"] = Vector` fix
  - Write `alembic/versions/0006_create_job_matches.py` (table + HNSW index on jobs.embedding)
  - Run migration

### Wave 1 — Embedding Workers
- **Plan 03-03:** Job embedding Celery task
  - `src/jobplatform/matching/tasks.py`: `embed_jobs_batch` task
  - Fetches `Job` rows with `embedding IS NULL`, processes in batches of 20
  - Updates `Job.embedding` in DB
  - Exposes via `POST /api/v1/workers/embed-jobs` (new endpoint in `workers/router.py`)
  - Register new task queue route in `celery_app.py`

- **Plan 03-04:** Profile embedding Celery task
  - `embed_profile(user_id: int)` task in `matching/tasks.py`
  - Loads `Profile` + `JobPreferences`, builds text, gets embedding, stores to `Profile.embedding` + updates `Profile.enriched_at`
  - Hook into `profiles/router.py` and `preferences/router.py` to dispatch task on update
  - Expose via `POST /api/v1/workers/embed-profile` trigger endpoint

### Wave 2 — Matching Core
- **Plan 03-05:** Match scoring Celery task
  - `compute_matches_for_user(user_id: int)` task in `matching/tasks.py`
  - Implements cosine similarity query + ats_score + skill_gaps + upsert to job_matches
  - Expose via `POST /api/v1/workers/compute-matches` in `workers/router.py`

- **Plan 03-06:** Match router + schemas
  - Create `src/jobplatform/matching/schemas.py`: `MatchResponse`, `JobMatchResponse`
  - Create `src/jobplatform/matching/router.py`: `GET /api/v1/jobs/{id}/match`, `GET /api/v1/matches/`
  - Register router in `main.py`

### Wave 3 — Tests
- **Plan 03-07:** Test suite `tests/test_matching.py`
  - Unit tests: `get_embedding` mock, `build_profile_text`, `build_job_text`, `compute_ats_score`, `compute_skill_gaps`
  - Integration tests: embed task inserts embedding into DB, match task populates job_matches
  - Endpoint tests: GET /matches/ returns ranked list, GET /jobs/{id}/match returns score

**Total: 7 plans across 4 waves**

---

## Code Examples

### Registering matching router in main.py

```python
# Add to src/jobplatform/main.py
from jobplatform.matching.router import router as matching_router
app.include_router(matching_router)
```

### Celery task queue registration in celery_app.py

```python
celery_app = Celery(
    "jobplatform",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["jobplatform.jobs.tasks", "jobplatform.matching.tasks"],  # add matching
)

celery_app.conf.update(
    ...
    task_routes={
        "jobplatform.jobs.tasks.scrape_portal": {"queue": "scraper"},
        "jobplatform.matching.tasks.embed_jobs_batch": {"queue": "embedder"},
        "jobplatform.matching.tasks.embed_profile": {"queue": "embedder"},
        "jobplatform.matching.tasks.compute_matches_for_user": {"queue": "matcher"},
    },
)
```

### Test: embedding mock pattern

```python
# tests/test_matching.py
from unittest.mock import AsyncMock, MagicMock, patch

FAKE_EMBEDDING = [0.01 * i for i in range(1536)]

async def test_get_embedding_returns_vector():
    with patch("jobplatform.matching.service.AsyncOpenAI") as MockClient:
        instance = MagicMock()
        MockClient.return_value = instance
        mock_resp = MagicMock()
        mock_resp.data = [MagicMock(embedding=FAKE_EMBEDDING)]
        instance.embeddings.create = AsyncMock(return_value=mock_resp)

        from jobplatform.matching.service import get_embedding
        result = await get_embedding("Python developer with 5 years experience")

    assert len(result) == 1536
    assert result == FAKE_EMBEDDING
```

### Test: match endpoint pattern (follows test_jobs.py style)

```python
async def test_list_matches_endpoint(client: AsyncClient, db):
    # Seed: create user, job with embedding, job_match record
    from jobplatform.matching.models import JobMatch, MatchStatus
    ...
    resp = await client.get(
        "/api/v1/matches/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert data[0]["score"] is not None
```

### ON CONFLICT upsert for job_matches

```python
# Source: SQLAlchemy PostgreSQL dialect docs [ASSUMED]
from sqlalchemy.dialects.postgresql import insert as pg_insert
from jobplatform.matching.models import JobMatch

async def upsert_match(db: AsyncSession, user_id: int, job_id: int, **fields) -> None:
    stmt = pg_insert(JobMatch).values(user_id=user_id, job_id=job_id, **fields)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_job_matches_user_job",
        set_={"score": stmt.excluded.score, "ats_score": stmt.excluded.ats_score,
              "skill_gaps": stmt.excluded.skill_gaps, "updated_at": stmt.excluded.updated_at},
    )
    await db.execute(stmt)
    await db.commit()
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|---|---|---|
| IVFFlat index for vectors | HNSW index (pgvector >= 0.5.0) | Better recall at same query speed; no training phase needed |
| `openai` v0.x (global config) | `openai` v1.x (`AsyncOpenAI` instance) | Async-native, no global state, concurrent safe |
| Synchronous embedding + store | Celery task with tenacity | Non-blocking write path, resilient to rate limits |

**Deprecated/outdated:**
- `openai.Embedding.create(...)` (v0.x style): replaced by `client.embeddings.create(...)` in v1.x.
- IVFFlat index with `lists` parameter: HNSW is now preferred for < 1M vector tables because it requires no training and has better recall.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|---|---|---|
| A1 | Profile embedding text composition (concatenating skills, roles, experience) produces semantically meaningful vectors for matching | Implementation Decisions > REQ-01 | Match quality will be poor; text composition would need re-tuning |
| A2 | `skill_gaps` interpretation: skills in job requirements not in user profile | Pattern 6 | Gaps could be inverted (user skills not needed by job); schema direction must be agreed before UI |
| A3 | Top-50 cosine similarity results is sufficient for ranked match list | REQ-04 | May miss relevant jobs if job corpus is large and threshold should be applied instead |
| A4 | `sqlalchemy.dialects.postgresql.insert` ON CONFLICT syntax accepted by async SQLAlchemy 2.x | Code Examples | Upsert pattern would fail; fallback: select + update or merge |
| A5 | pgvector installed version on the project's PostgreSQL server is >= 0.5.0 (for HNSW support) | Pattern 7: migration | HNSW index creation will fail on pgvector < 0.5.0; fall back to IVFFlat |

---

## Open Questions

1. **HNSW vs IVFFlat index**
   - What we know: HNSW is the current recommendation; does not require training.
   - What's unclear: PostgreSQL server's installed pgvector extension version. HNSW requires pgvector >= 0.5.0 (released 2023-07).
   - Recommendation: Add a check in migration: `SELECT extversion FROM pg_extension WHERE extname = 'vector'`. If < 0.5.0, fall back to IVFFlat with `lists=100`.

2. **On-demand vs pre-computed match for GET /jobs/{id}/match**
   - What we know: pre-computed is fast (simple SELECT); on-demand avoids stale scores.
   - What's unclear: user expectation on latency and freshness.
   - Recommendation: Return pre-computed if exists, compute on-demand if embeddings available, 202 if embeddings missing. This gives good UX without a separate polling loop.

3. **Batch size for embedding API calls**
   - What we know: OpenAI allows up to 2048 inputs per request; Tier-1 rate limit is 3000 RPM / 1M TPM.
   - What's unclear: project's OpenAI tier.
   - Recommendation: Process 20 jobs per API call in `embed_jobs_batch`. Add a 0.5s sleep between batches to stay well under rate limits for early-stage usage.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|---|---|---|---|---|
| PostgreSQL | DB layer | ✓ (test DB confirmed in conftest.py) | 15+ assumed | — |
| Redis | Celery broker/backend | ✓ (settings.redis_url configured) | any | — |
| OpenAI API key | Embedding generation | ✗ in test env | — | Mock in tests; set `OPENAI_API_KEY` in `.env` for dev/prod |
| pgvector extension | Vector column + HNSW index | ✓ (migration 0000 already created it) | version unknown | IVFFlat fallback if < 0.5.0 |

**Missing dependencies with no fallback:**
- OpenAI API key in `.env` — required for real embedding generation in dev/prod. Tests mock it.

**Missing dependencies with fallback:**
- pgvector extension version < 0.5.0 → use IVFFlat index (still functional, slower recall).

---

## Validation Architecture

### Test Framework

| Property | Value |
|---|---|
| Framework | pytest + pytest-asyncio 0.23.6 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — `asyncio_mode = "auto"` |
| Quick run command | `uv run pytest tests/test_matching.py -q --tb=short` |
| Full suite command | `cd /home/surendar/Workspace/Projects/AI_System/job-platform && uv run pytest tests/ -q --tb=short` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|---|---|---|---|---|
| REQ-01 | `get_embedding` returns 1536-dim list | unit (mocked) | `uv run pytest tests/test_matching.py::test_get_embedding_returns_vector -x` | Wave 0 |
| REQ-01 | `build_profile_text` produces non-empty string | unit | `uv run pytest tests/test_matching.py::test_build_profile_text -x` | Wave 0 |
| REQ-01 | `build_job_text` includes title and description | unit | `uv run pytest tests/test_matching.py::test_build_job_text -x` | Wave 0 |
| REQ-02 | `JobMatch` row created with all fields | integration | `uv run pytest tests/test_matching.py::test_job_match_model_create -x` | Wave 0 |
| REQ-03 | cosine similarity query returns ranked results | integration | `uv run pytest tests/test_matching.py::test_find_similar_jobs -x` | Wave 1 |
| REQ-04 | `compute_matches_for_user` populates job_matches table | integration (mocked OpenAI) | `uv run pytest tests/test_matching.py::test_compute_matches_task -x` | Wave 2 |
| REQ-05 | GET /jobs/{id}/match returns score for embedded job | endpoint | `uv run pytest tests/test_matching.py::test_get_job_match_endpoint -x` | Wave 2 |
| REQ-06 | GET /matches/ returns ranked list ordered by score | endpoint | `uv run pytest tests/test_matching.py::test_list_matches_endpoint -x` | Wave 2 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_matching.py -q --tb=short`
- **Per wave merge:** Full suite: `uv run pytest tests/ -q --tb=short`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_matching.py` — all matching tests (does not exist yet; create in Plan 03-07)

---

## Sources

### Primary (HIGH confidence)
- pgvector-python GitHub README (github.com/pgvector/pgvector-python) — cosine_distance ORM method, HNSW index creation syntax [VERIFIED: WebFetch official repo]
- PyPI registry — openai 1.109.1, tenacity 9.1.4, pgvector 0.4.2 [VERIFIED: PyPI]
- Existing codebase: `jobs/tasks.py`, `jobs/service.py`, `celery_app.py`, `conftest.py` — patterns extracted directly [VERIFIED: codebase read]

### Secondary (MEDIUM confidence)
- GitHub alembic/alembic discussions #1324, #1367 — pgvector autogenerate fix (ischema_names patch) [CITED: github.com/sqlalchemy/alembic/discussions/1324]
- OpenAI rate limits guide (inference.net/content/openai-rate-limits-guide/) — Tier 1 RPM/TPM figures [CITED: WebSearch verified against official rate limits page]

### Tertiary (LOW confidence)
- ATS score and skill_gaps computation heuristics — domain judgment, no standard algorithm [ASSUMED]
- Top-50 result limit for match scoring — common practice, not benchmarked for this dataset [ASSUMED]

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — packages verified on PyPI, slopcheck OK, official SDK
- Architecture: HIGH — follows existing codebase patterns exactly
- pgvector query syntax: HIGH — verified from official pgvector-python repo
- Alembic pitfall: HIGH — confirmed in official alembic GitHub discussions
- ATS score / skill_gaps: LOW — heuristic; output quality depends on requirements JSONB structure

**Research date:** 2026-06-27
**Valid until:** 2026-07-27 (stable stack; openai SDK updates frequently — re-verify if >30 days)
