import asyncio
from datetime import datetime, timezone

import structlog
from sqlalchemy import select

from jobplatform.applications.models import Application, ApplicationStatus
from jobplatform.applications.service import extract_resume_text, tailor_resume
from jobplatform.celery_app import celery_app
from jobplatform.database import AsyncSessionLocal
from jobplatform.jobs.models import Job
from jobplatform.resumes.models import Resume

logger = structlog.get_logger()


async def _tailor_and_apply_async(application_id: int, task_id: str) -> dict:
    """Async implementation: open own session, drive status transitions, call Claude.

    Status flow:
      pending → tailoring  (task starts; committed before LLM call)
      tailoring → applied  (LLM succeeded; applied_at set)
      tailoring → pending  (on exception; allows clean Celery retry)

    Never accepts an AsyncSession parameter — opens AsyncSessionLocal() internally
    to avoid pickling issues across the sync/async Celery boundary.
    """
    async with AsyncSessionLocal() as db:
        app = await db.scalar(
            select(Application).where(Application.id == application_id)
        )
        if not app:
            logger.warning(
                "tailor_and_apply.not_found", application_id=application_id
            )
            return {"application_id": application_id, "status": "not_found"}

        if app.status != ApplicationStatus.pending:
            logger.info(
                "tailor_and_apply.skipped",
                application_id=application_id,
                current_status=app.status.value,
            )
            return {"application_id": application_id, "status": "skipped"}

        # Transition 1: pending → tailoring
        app.status = ApplicationStatus.tailoring
        app.updated_at = datetime.now(timezone.utc)
        await db.commit()

        try:
            # Fetch related Job and Resume rows
            job = await db.scalar(select(Job).where(Job.id == app.job_id))
            resume = (
                await db.scalar(select(Resume).where(Resume.id == app.resume_id))
                if app.resume_id is not None
                else None
            )

            # Extract resume text from parsed_data (JSONB → string)
            resume_text = extract_resume_text(resume) if resume else ""

            # Call Claude claude-haiku-4-5 (retried by tailor_resume via tenacity)
            job_description = job.description or "" if job else ""
            tailored = await tailor_resume(resume_text, job_description)

            # Transition 2: tailoring → applied
            app.tailored_resume_text = tailored
            app.status = ApplicationStatus.applied
            app.applied_at = datetime.now(timezone.utc)
            app.updated_at = datetime.now(timezone.utc)
            await db.commit()

            logger.info(
                "tailor_and_apply.applied",
                application_id=application_id,
                task_id=task_id,
            )
            return {"application_id": application_id, "status": "applied"}

        except Exception as exc:
            logger.error(
                "tailor_and_apply.failed",
                application_id=application_id,
                task_id=task_id,
                error=str(exc),
            )
            # Reset to pending so the task can be retried cleanly
            app.status = ApplicationStatus.pending
            app.updated_at = datetime.now(timezone.utc)
            await db.commit()
            raise


@celery_app.task(
    name="jobplatform.applications.tasks.tailor_and_apply",
    bind=True,
)
def tailor_and_apply(self, application_id: int) -> dict:
    """Sync Celery entry point. Delegates to async implementation via asyncio.run."""
    task_id = self.request.id or "local"
    return asyncio.run(_tailor_and_apply_async(application_id, task_id))
