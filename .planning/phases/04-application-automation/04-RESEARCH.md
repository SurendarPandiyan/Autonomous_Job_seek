# Phase 4: Application Automation — Research

**Researched:** 2026-06-27
**Domain:** Claude API (Anthropic SDK) + SQLAlchemy async + Celery + FastAPI
**Confidence:** HIGH

---

## Summary

Phase 4 adds the full application lifecycle on top of the existing FastAPI/SQLAlchemy/Celery
stack. Core machinery: create an `Application` ORM row (status=pending), dispatch a Celery task
that calls the Claude API (`claude-3-5-haiku-20241022`) to tailor the user's resume to the job
description, stores the result as TEXT in `tailored_resume_text`, then stubs portal submission
(marks status=applied, records `applied_at`). Two API endpoints expose the lifecycle.

Phase 4 does NOT include Playwright-based form submission — that is Phase 5+ scope. The
`BasePortalAdapter` already carries `supports_auto_apply: bool = False` which signals stub-only
apply for all current portals.

The codebase is well-structured and all four prior phases follow the same
`models / service / schemas / tasks / router` module layout. Phase 4 adds a new
`applications/` domain package mirroring this pattern exactly.

**Primary recommendation:** Add `src/jobplatform/applications/` with Anthropic SDK tailoring
service, Celery task (asyncio.run pattern), CRUD service, Pydantic schemas, and FastAPI router.
Add Alembic migration 0007. No existing files need structural changes — only `config.py`,
`pyproject.toml`, `celery_app.py`, `alembic/env.py`, and `main.py` require additive changes.

---

## Codebase Pattern Analysis (from direct file reads — graphify disabled)

### Module structure (Phase 4 must mirror exactly)
```
src/jobplatform/
├── matching/
│   ├── models.py      # SAEnum, JSONB, Mapped/mapped_column, UniqueConstraint
│   ├── service.py     # async def functions, AsyncSession param, tenacity retry
│   ├── schemas.py     # Pydantic BaseModel, ConfigDict(from_attributes=True)
│   ├── tasks.py       # sync wrapper → asyncio.run(_async_impl), bind=True
│   └── router.py      # APIRouter, Depends(get_current_user), Depends(get_db)
└── applications/      # Phase 4 adds this
    ├── __init__.py
    ├── models.py
    ├── service.py
    ├── schemas.py
    ├── tasks.py
    └── router.py
```

### Celery convention (from jobs/tasks.py + matching/tasks.py)
- Always: `sync def task(self, ...) → asyncio.run(_async_impl(...))`
- Never pass `AsyncSession` across sync/async boundary — open `AsyncSessionLocal()` inside
  the async inner function
- `bind=True` on all tasks; `self.request.id or "local"` for task_id
- Named explicitly: `name="jobplatform.applications.tasks.tailor_and_apply"`
- Routed to a dedicated queue: `"applier"`

### Auth + DB injection (from dependencies.py + every router)
```python
current_user: User = Depends(get_current_user)
db: AsyncSession = Depends(get_db)
```

### Alembic migration convention (from 0006_create_job_matches.py)
- File: `alembic/versions/0007_create_applications.py`
- `revision = "0007"`, `down_revision = "0006"`
- Explicit `op.create_table(...)`, `op.create_index(...)` — NO autogenerate
- Enum type created inline via `sa.Enum(...)`, dropped in `downgrade()` via `op.execute("DROP TYPE IF EXISTS applicationstatus")`
- `env.py` requires manual import of new model: `import jobplatform.applications.models  # noqa: F401`

### Config extension pattern (from config.py)
```python
# add to Settings class:
anthropic_api_key: str = ""
```

### Tenacity retry pattern (from matching/service.py)
```python
from anthropic import AsyncAnthropic, RateLimitError

@retry(
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type(RateLimitError),
    reraise=True,
)
async def tailor_resume(resume_text: str, job_description: str) -> str:
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=4096,
        messages=[{"role": "user", "content": TAILOR_PROMPT.format(...)}],
    )
    return response.content[0].text
```

### Test isolation pattern (from tests/conftest.py)
- Per-test transaction rollback via `conn.rollback()` — tests never commit to the DB
- `app.dependency_overrides[get_db] = override_get_db` inside `client` fixture
- External API calls (OpenAI in Phase 3) mocked with `unittest.mock.AsyncMock + patch`
- Same pattern for Anthropic in Phase 4 tests

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Application CRUD | API / Backend | — | DB write; auth-gated |
| Resume tailoring (LLM) | API / Backend (Celery) | — | Async CPU-bound; not in request thread |
| Portal apply stub | API / Backend (Celery) | — | In-task after tailoring completes |
| Status tracking | API / Backend | Database / Storage | status column + applied_at timestamp |
| Application listing | API / Backend | Database / Storage | Paginated query by user_id |

---

## Implementation Decisions

### REQ-07: Application Model

**Schema:**
```python
class ApplicationStatus(enum.Enum):
    pending   = "pending"    # created, awaiting Celery task
    tailoring = "tailoring"  # Celery task running
    applied   = "applied"    # stub-submitted (intent recorded)
    rejected  = "rejected"
    interview = "interview"
    offer     = "offer"

class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("user_id", "job_id", name="uq_applications_user_job"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    resume_id: Mapped[int | None] = mapped_column(ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[ApplicationStatus] = mapped_column(SAEnum(ApplicationStatus), default=ApplicationStatus.pending, nullable=False, index=True)
    tailored_resume_text: Mapped[str | None] = mapped_column(Text)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
```

**`tailored_resume_text` type rationale:** TEXT, not JSONB. It is a prose string, not structured
data. JSONB adds quoting overhead and forces serialisation with no benefit. TEXT is what Phase 3
also uses for job `description`.

**`resume_id` FK rationale:** `SET NULL` on delete (not CASCADE) — if a resume is deleted, the
application record should survive with `resume_id=NULL`. Tailored text already captured in
`tailored_resume_text`.

**Status `tailoring` rationale:** Distinguishes "queued but not started" (pending) from "LLM
call in progress" (tailoring). Prevents duplicate Celery task dispatch on retry.

### REQ-08: LLM Resume Tailoring

**SDK:** `anthropic` (AsyncAnthropic) — NOT OpenAI. Reason: requirements specify Claude API.
[VERIFIED: npm registry] — slopcheck [OK] for `anthropic` on PyPI; version 0.112.0 available.

**Model:** `claude-3-5-haiku-20241022`
- [ASSUMED] — training knowledge. claude-3-5-haiku is fast (seconds vs 10+s for Sonnet),
  low-cost, sufficient for resume tailoring text transformation. If higher quality needed,
  swap to `claude-3-5-sonnet-20241022` in config.

**Streaming:** No. Result stored in DB; user polls GET /api/v1/applications/{id}.
Streaming adds complexity for no UX benefit in an async pipeline.

**Prompt pattern:**
```python
TAILOR_PROMPT = """\
You are a professional resume writer. Tailor the following resume to the job description.
Preserve all factual content. Emphasize matching skills and experience.
Return ONLY the tailored resume text, no preamble.

JOB DESCRIPTION:
{job_description}

ORIGINAL RESUME:
{resume_text}
"""
```

**Source for resume text:** `Resume.parsed_data` (JSONB, already stored in Phase 1). If
`parsed_data` is None, fall back to reading `Resume.file_path` via `aiofiles`. However,
`parsed_data` is the preferred source — it already exists and avoids disk I/O in Celery.
If `parsed_data` is None and no file read is implemented yet, fail gracefully with status=pending
and a logged error.

**Simplest viable approach:** Extract `parsed_data` as JSON string, pass as resume_text.
No PDF parsing needed — `parsed_data` already contains structured resume content from Phase 1
upload.

### REQ-09: POST /api/v1/applications/

**Request body:**
```python
class ApplicationCreate(BaseModel):
    job_id: int
    resume_id: int | None = None  # None → use default resume
```

**Flow:**
```
POST /api/v1/applications/
  → validate job exists (404 if not)
  → resolve resume: use provided resume_id OR query default resume (is_default=True)
  → if UniqueConstraint would fire: 409 Conflict ("Already applied to this job")
  → create Application(status=pending, resume_id=resolved_id)
  → db.commit()
  → dispatch Celery task: tailor_and_apply.delay(application_id)
  → return 202 with ApplicationResponse
```

**Why 202:** LLM tailoring takes 2-10s; caller polls status via GET. Matches Phase 2's scrape
worker pattern (dispatch + return task_id equivalent via application_id).

### REQ-10: Application Status Tracking

Status transitions (Celery task controls):
```
pending → tailoring (task starts)
tailoring → applied  (stub apply succeeds)
tailoring → pending  (on error — allows retry)
applied → rejected / interview / offer  (manual PATCH, Phase 5+)
```

Phase 4 implements the machine transitions. PATCH /api/v1/applications/{id}/status is Phase 5+
scope — not in REQ-10. REQ-10 only requires the status field exists and is returned.

### REQ-11: GET /api/v1/applications/

**Response:** list of ApplicationResponse, ordered by created_at DESC.
**Pagination:** cursor-based (follow matching/service.py list_matches pattern).
**Filter:** by `status` query param (optional).

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `anthropic` | `>=0.112.0` | Claude API async client | Official SDK; AsyncAnthropic for async tasks |
| SQLAlchemy | `>=2.0.30` (already in pyproject) | ORM + async session | Already in stack |
| Celery | `>=5.3.6` (already in pyproject) | Async task execution | Already in stack |
| tenacity | `>=8.2.0` (already in pyproject) | Retry with backoff | Already in stack, used in matching |

### No New Supporting Libraries
All other requirements covered by existing stack.

**Installation (additive only):**
```bash
uv add "anthropic>=0.112.0"
```

---

## Package Legitimacy Audit

| Package | Registry | Age | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|
| `anthropic` | PyPI | ~3 yrs | [OK] | Approved |

**Packages removed:** none
**Packages flagged as suspicious:** none

[VERIFIED: PyPI] — `pip index versions anthropic` confirms 0.112.0 current.
[CITED: https://github.com/anthropics/anthropic-sdk-python] — official Anthropic SDK.

---

## Architecture Patterns

### System Architecture Diagram

```
POST /api/v1/applications/
       │
       ▼
  ApplicationRouter
       │
       ├─── validate job exists (DB)
       ├─── resolve resume (DB)
       ├─── create Application(status=pending) → DB commit
       └─── tailor_and_apply.delay(app_id) → Redis
                    │
                    ▼
            Celery Worker [applier queue]
                    │
                    ├─── update status=tailoring → DB commit
                    ├─── fetch Application + Job + Resume → DB
                    ├─── AsyncAnthropic.messages.create(haiku) → Claude API
                    ├─── store tailored_resume_text → DB
                    ├─── stub apply (log intent, check portal.supports_auto_apply)
                    └─── status=applied, applied_at=now → DB commit

GET /api/v1/applications/
       │
       ▼
  ApplicationRouter → list_applications(db, user_id) → DB → ApplicationResponse[]
```

### Recommended Project Structure
```
src/jobplatform/applications/
├── __init__.py
├── models.py      # Application + ApplicationStatus enum
├── service.py     # create_application, get_application, list_applications, update_application_status
├── schemas.py     # ApplicationCreate, ApplicationResponse
├── tasks.py       # tailor_and_apply Celery task
└── router.py      # POST /api/v1/applications/, GET /api/v1/applications/

alembic/versions/
└── 0007_create_applications.py
```

### Pattern: Celery Task with Status Transitions
```python
# [CITED: matching/tasks.py — existing asyncio.run pattern]
@celery_app.task(name="jobplatform.applications.tasks.tailor_and_apply", bind=True)
def tailor_and_apply(self, application_id: int) -> dict:
    task_id = self.request.id or "local"
    return asyncio.run(_tailor_and_apply_async(application_id, task_id))

async def _tailor_and_apply_async(application_id: int, task_id: str) -> dict:
    async with AsyncSessionLocal() as db:
        app = await db.scalar(select(Application).where(Application.id == application_id))
        if not app or app.status != ApplicationStatus.pending:
            return {"application_id": application_id, "status": "skipped"}

        # Transition: pending → tailoring
        app.status = ApplicationStatus.tailoring
        await db.commit()

        try:
            job = await db.scalar(select(Job).where(Job.id == app.job_id))
            resume = await db.scalar(select(Resume).where(Resume.id == app.resume_id))
            resume_text = str(resume.parsed_data) if resume and resume.parsed_data else ""

            tailored = await tailor_resume(resume_text, job.description or "")
            app.tailored_resume_text = tailored

            # Stub apply
            app.status = ApplicationStatus.applied
            app.applied_at = datetime.now(timezone.utc)
            await db.commit()

            return {"application_id": application_id, "status": "applied"}

        except Exception as exc:
            logger.error("tailor_and_apply.failed", application_id=application_id, error=str(exc))
            app.status = ApplicationStatus.pending  # allow retry
            await db.commit()
            raise
```

### Anti-Patterns to Avoid
- **Inline LLM call in router:** `AsyncAnthropic.messages.create` takes 2-10s — never block
  the request thread. Always dispatch to Celery.
- **Passing AsyncSession to Celery:** Sessions are not picklable. Always open a new session
  inside the `asyncio.run(...)` async inner function.
- **Autogenerate for Alembic:** pgvector `vector` type breaks autogenerate. Use explicit
  `op.create_table(...)` as in 0005/0006.
- **CASCADE on resume FK:** If resume deleted, application should survive. Use SET NULL.
- **Missing UniqueConstraint:** Without `uq_applications_user_job`, duplicate applications
  are possible under concurrent requests. Add constraint + handle IntegrityError as 409.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| LLM rate-limit retry | Custom sleep loop | `tenacity` (already in stack) | Exponential backoff, max attempts |
| LLM API call | Custom HTTP client | `anthropic.AsyncAnthropic` | Token counting, error types, streaming if needed |
| DB upsert on conflict | Manual SELECT+INSERT | `pg_insert().on_conflict_do_update()` | Race-condition safe (see matching/service.py) |

---

## Common Pitfalls

### Pitfall 1: Missing `tailoring` queue in celery_app.py
**What goes wrong:** Task dispatched but no worker listening on `"applier"` queue → sits in
Redis forever.
**Prevention:** Add to `task_routes` in `celery_app.py` AND update `include=` list.
**Warning signs:** Application stays `pending` indefinitely.

### Pitfall 2: Resume has no parsed_data
**What goes wrong:** `resume.parsed_data` is None → empty resume text → Claude returns
generic output → stored but not useful.
**Prevention:** Fallback: if `parsed_data` is None, log warning, store a placeholder, still
mark applied. Do NOT crash the task.

### Pitfall 3: Alembic env.py missing model import
**What goes wrong:** `alembic upgrade head` runs but `applications` table never created — the
migration file exists but `Base.metadata` doesn't know about the model.
**Prevention:** Add `import jobplatform.applications.models  # noqa: F401` to `alembic/env.py`
(same line pattern as matching.models on line 16).

### Pitfall 4: IntegrityError on duplicate application
**What goes wrong:** If user posts twice before DB commit returns, UniqueConstraint fires and
leaks a 500 instead of 409.
**Prevention:** Wrap `db.commit()` in `try/except IntegrityError` in `create_application`
service function; raise `HTTPException(409, "Already applied to this job")`.

### Pitfall 5: Test mocking wrong module path
**What goes wrong:** `patch("anthropic.AsyncAnthropic")` patches the SDK namespace, not the
imported reference; real API called in tests.
**Prevention:** Patch at import site: `patch("jobplatform.applications.service.AsyncAnthropic")`.
(Matches Phase 3 pattern: `patch("jobplatform.matching.service.AsyncOpenAI")`.)

### Pitfall 6: Status race on Celery retry
**What goes wrong:** Celery retries a task; if status was already set to `tailoring`, the
guard `if app.status != ApplicationStatus.pending` skips it → zombie application.
**Prevention:** On exception, reset status to `pending` before `raise` (see task pattern above).
This allows clean retry.

---

## Code Examples

### ApplicationCreate + ApplicationResponse schemas
```python
# [CITED: matching/schemas.py pattern]
from pydantic import BaseModel, ConfigDict
from datetime import datetime

class ApplicationCreate(BaseModel):
    job_id: int
    resume_id: int | None = None

class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    resume_id: int | None
    status: str
    tailored_resume_text: str | None
    applied_at: datetime | None
    created_at: datetime
    updated_at: datetime
```

### POST router endpoint
```python
# [CITED: matching/router.py + jobs/router.py patterns]
@router.post("/api/v1/applications/", response_model=ApplicationResponse, status_code=202)
async def create_application_endpoint(
    body: ApplicationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Application:
    app = await create_application(db, current_user.id, body.job_id, body.resume_id)
    tailor_and_apply.delay(app.id)
    return app
```

### Alembic 0007 skeleton
```python
# alembic/versions/0007_create_applications.py
revision = "0007"
down_revision = "0006"

def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resume_id", sa.Integer(), sa.ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.Enum("pending","tailoring","applied","rejected","interview","offer", name="applicationstatus"), nullable=False, server_default="pending"),
        sa.Column("tailored_resume_text", sa.Text(), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "job_id", name="uq_applications_user_job"),
    )
    op.create_index("ix_applications_user_id", "applications", ["user_id"])
    op.create_index("ix_applications_job_id", "applications", ["job_id"])
    op.create_index("ix_applications_status", "applications", ["status"])

def downgrade() -> None:
    op.drop_index("ix_applications_status", table_name="applications")
    op.drop_index("ix_applications_job_id", table_name="applications")
    op.drop_index("ix_applications_user_id", table_name="applications")
    op.drop_table("applications")
    op.execute("DROP TYPE IF EXISTS applicationstatus")
```

---

## Plan Breakdown

**6 plans, 3 waves** (mirroring Phase 3's structure).

### Wave 0 — Foundation (no dependencies)

**04-01: Application Model + Alembic 0007**
- Files: `src/jobplatform/applications/__init__.py`, `models.py`, `alembic/versions/0007_create_applications.py`, `alembic/env.py`
- Create `ApplicationStatus` enum + `Application` ORM model
- Write migration 0007 explicitly (no autogenerate)
- Register model in `alembic/env.py`
- Verify: `uv run alembic upgrade head` succeeds; `applications` table visible in psql
- Requirements: REQ-07

**04-02: Anthropic SDK + Resume Tailoring Service**
- Files: `pyproject.toml`, `src/jobplatform/config.py`, `src/jobplatform/applications/service.py` (tailoring functions only)
- `uv add "anthropic>=0.112.0"`
- Add `anthropic_api_key: str = ""` to Settings
- Implement `tailor_resume(resume_text, job_description) -> str` with tenacity retry on `RateLimitError`
- Implement `extract_resume_text(resume: Resume) -> str` (parsed_data JSON → string; fallback warning)
- No DB calls in this service module — pure LLM + text functions
- Requirements: REQ-08

### Wave 1 — Core Logic (depends on Wave 0)

**04-03: Application CRUD Service**
- Files: `src/jobplatform/applications/service.py` (DB functions added), `src/jobplatform/applications/schemas.py`
- Implement: `create_application`, `get_application`, `list_applications`, `update_application_status`
- Handle `IntegrityError` → 409 in `create_application`
- Default resume resolution: query `Resume.is_default == True` if `resume_id` is None
- Requirements: REQ-07, REQ-09, REQ-10, REQ-11

**04-04: Celery Task `tailor_and_apply`**
- Files: `src/jobplatform/applications/tasks.py`, `src/jobplatform/celery_app.py`
- `asyncio.run(_tailor_and_apply_async(...))` pattern
- Status transitions: pending → tailoring → applied (or reset to pending on error)
- Add `"applier"` queue in `celery_app.py` task_routes + include list
- Requirements: REQ-08, REQ-09, REQ-10

### Wave 2 — API + Tests (depends on Wave 1)

**04-05: Router + main.py Integration**
- Files: `src/jobplatform/applications/router.py`, `src/jobplatform/main.py`
- `POST /api/v1/applications/` → 202 ApplicationResponse
- `GET /api/v1/applications/` → list[ApplicationResponse] with `?status=` filter + cursor pagination
- Register `applications_router` in `main.py`
- Requirements: REQ-09, REQ-11

**04-06: Test Suite**
- Files: `tests/test_applications.py`
- Unit tests: `tailor_resume` (mock AsyncAnthropic), `extract_resume_text`, `create_application` (IntegrityError path)
- Integration tests: POST creates row + dispatches task (mock `.delay`), GET lists by user, status filter
- Task test: `_tailor_and_apply_async` with mocked Claude → verify status transitions
- Target: ≥85% coverage on `applications/` package
- Requirements: REQ-07 through REQ-11

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (already configured) |
| Config file | `pyproject.toml` — `asyncio_mode = "auto"` |
| Quick run | `uv run pytest tests/test_applications.py -q --tb=short` |
| Full suite | `uv run pytest tests/ -q --tb=short` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Command |
|--------|----------|-----------|---------|
| REQ-07 | Application row created with correct fields | integration | `pytest tests/test_applications.py::test_create_application_model` |
| REQ-08 | tailor_resume calls Claude, returns string | unit (mock) | `pytest tests/test_applications.py::test_tailor_resume` |
| REQ-09 | POST /api/v1/applications/ returns 202, dispatches task | integration | `pytest tests/test_applications.py::test_post_application` |
| REQ-09 | Duplicate application → 409 | integration | `pytest tests/test_applications.py::test_duplicate_application` |
| REQ-10 | Status transitions pending→tailoring→applied in task | unit (mock) | `pytest tests/test_applications.py::test_tailor_and_apply_task` |
| REQ-11 | GET /api/v1/applications/ returns user's applications | integration | `pytest tests/test_applications.py::test_list_applications` |
| REQ-11 | GET with ?status=applied filters correctly | integration | `pytest tests/test_applications.py::test_list_applications_filter` |

### Wave 0 Gaps
- [ ] `tests/test_applications.py` — created in Plan 04-06

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL | DB layer | ✓ (jobplatform_test DB exists per prior phases) | 15.x | — |
| Redis | Celery broker | ✓ (used by Phase 2+3) | — | — |
| `anthropic` PyPI package | REQ-08 | ✓ (pip index confirms 0.112.0) | 0.112.0 | — |
| `ANTHROPIC_API_KEY` env var | REQ-08 | unknown — not in config.py yet | — | Empty string → tests mock, prod requires real key |

**Missing dependencies with no fallback:**
- `ANTHROPIC_API_KEY` must be set in `.env` for production tailoring; tests mock the client

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `claude-3-5-haiku-20241022` is the current model ID for Haiku | Decisions | Wrong model ID → API 404; fix: use verified model ID from Anthropic docs |
| A2 | `Resume.parsed_data` contains enough text to produce meaningful tailoring | REQ-08 | Poor output quality; mitigated by Phase 1 parse pipeline |
| A3 | Phase 4 scope excludes Playwright portal apply (stub only) | Plan Breakdown | If real apply required in Phase 4, task scope increases significantly |

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Synchronous LLM calls in request handlers | Celery task + poll pattern | No request timeouts from slow LLM |
| OpenAI for all LLM work | Anthropic Claude for generation, OpenAI for embeddings | Two API keys required |

---

## Sources

### Primary (HIGH confidence)
- Direct reads of `src/jobplatform/matching/` — patterns for service/tasks/router/schemas
- Direct reads of `alembic/versions/0006_create_job_matches.py` — migration pattern
- Direct reads of `tests/conftest.py` and `tests/test_matching.py` — test isolation pattern
- `pip index versions anthropic` — confirms 0.112.0 on PyPI [VERIFIED: PyPI]
- slopcheck `[OK]` on `anthropic` package [VERIFIED: slopcheck]

### Secondary (MEDIUM confidence)
- `anthropic.AsyncAnthropic` + `client.messages.create` API pattern [ASSUMED from training — Anthropic SDK well-established]
- `claude-3-5-haiku-20241022` model ID [ASSUMED from training — verify against Anthropic docs before use]

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified on PyPI, patterns confirmed from codebase
- Architecture: HIGH — mirrors Phase 3 exactly, all patterns confirmed from source
- Pitfalls: HIGH — drawn from codebase analysis of existing error handling patterns
- Model ID (A1): MEDIUM — training knowledge, verify before implementation

**Research date:** 2026-06-27
**Valid until:** 2026-07-27 (stable stack; anthropic SDK minor version may update)
