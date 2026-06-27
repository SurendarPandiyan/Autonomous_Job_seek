import logging

import structlog
from anthropic import AsyncAnthropic, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from jobplatform.config import settings
from jobplatform.resumes.models import Resume

# Patch target for tests: "jobplatform.applications.service.AsyncAnthropic"
logger = structlog.get_logger()

TAILOR_PROMPT = """\
You are a professional resume writer. Tailor the following resume to the job description.
Preserve all factual content. Emphasize matching skills and experience.
Return ONLY the tailored resume text, no preamble.

JOB DESCRIPTION:
{job_description}

ORIGINAL RESUME:
{resume_text}
"""


@retry(
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type(RateLimitError),
    reraise=True,
)
async def tailor_resume(resume_text: str, job_description: str) -> str:
    """Call Claude claude-haiku-4-5 to tailor resume_text to job_description.

    Retries up to 5 times on RateLimitError with exponential backoff (2s–60s).
    Returns the tailored resume as a plain string.
    """
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": TAILOR_PROMPT.format(
                    job_description=job_description,
                    resume_text=resume_text,
                ),
            }
        ],
    )
    return response.content[0].text


def extract_resume_text(resume: Resume) -> str:
    """Extract resume text from Resume.parsed_data (JSONB dict → string).

    Falls back to empty string if parsed_data is None, and logs a warning so
    the Celery task can still proceed (it will store a placeholder and mark applied).
    """
    if resume.parsed_data is None:
        logger.warning(
            "extract_resume_text.no_parsed_data",
            resume_id=resume.id,
        )
        return ""
    return str(resume.parsed_data)


# ---------------------------------------------------------------------------
# DB CRUD functions (added in Plan 04-03)
# ---------------------------------------------------------------------------
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from jobplatform.applications.models import Application, ApplicationStatus
from jobplatform.jobs.models import Job
from jobplatform.resumes.models import Resume


async def create_application(
    db: AsyncSession,
    user_id: int,
    job_id: int,
    resume_id: int | None,
) -> Application:
    """Create an Application row with status=pending.

    Validates job exists (404), resolves default resume if resume_id is None,
    and catches IntegrityError from the UniqueConstraint → 409 Conflict.
    """
    # Validate job exists
    job = await db.scalar(select(Job).where(Job.id == job_id))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Resolve resume: use provided ID or fall back to default
    resolved_resume_id = resume_id
    if resolved_resume_id is None:
        default_resume = await db.scalar(
            select(Resume).where(
                Resume.user_id == user_id,
                Resume.is_default == True,  # noqa: E712
            )
        )
        if default_resume:
            resolved_resume_id = default_resume.id

    now = datetime.now(timezone.utc)
    app = Application(
        user_id=user_id,
        job_id=job_id,
        resume_id=resolved_resume_id,
        status=ApplicationStatus.pending,
        created_at=now,
        updated_at=now,
    )
    db.add(app)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Already applied to this job")
    await db.refresh(app)
    return app


async def get_application(
    db: AsyncSession,
    application_id: int,
    user_id: int,
) -> Application | None:
    """Fetch a single application owned by user_id, or None if not found."""
    return await db.scalar(
        select(Application).where(
            Application.id == application_id,
            Application.user_id == user_id,
        )
    )


async def list_applications(
    db: AsyncSession,
    user_id: int,
    status: str | None = None,
    limit: int = 20,
    cursor: int | None = None,
) -> list[Application]:
    """List applications for a user, newest first, with optional status filter.

    Cursor pagination: pass the `id` of the last item received to get the next page.
    """
    stmt = (
        select(Application)
        .where(Application.user_id == user_id)
        .order_by(Application.id.desc())
        .limit(limit)
    )
    if cursor is not None:
        stmt = stmt.where(Application.id < cursor)
    if status is not None:
        try:
            status_enum = ApplicationStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid status value: {status!r}. "
                f"Must be one of: {[s.value for s in ApplicationStatus]}",
            )
        stmt = stmt.where(Application.status == status_enum)
    result = await db.scalars(stmt)
    return list(result.all())


async def update_application_status(
    db: AsyncSession,
    application_id: int,
    status: ApplicationStatus,
    **kwargs,
) -> Application:
    """Update status (and any extra keyword fields) on an Application row."""
    app = await db.scalar(
        select(Application).where(Application.id == application_id)
    )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    app.status = status
    app.updated_at = datetime.now(timezone.utc)
    for key, value in kwargs.items():
        setattr(app, key, value)
    await db.commit()
    await db.refresh(app)
    return app
