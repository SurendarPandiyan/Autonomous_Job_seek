import asyncio
import time
from datetime import datetime, timezone

import structlog
from sqlalchemy import select

from jobplatform.celery_app import celery_app
from jobplatform.database import AsyncSessionLocal
from jobplatform.jobs.models import Job
from jobplatform.matching.service import build_job_text, build_profile_text, get_embedding
from jobplatform.preferences.models import JobPreferences
from jobplatform.profiles.models import Profile

logger = structlog.get_logger()


async def _embed_jobs_batch_async(task_id: str) -> dict:
    embedded = 0

    async with AsyncSessionLocal() as db:
        while True:
            stmt = (
                select(Job)
                .where(Job.embedding.is_(None))
                .where(Job.is_active == True)  # noqa: E712
                .limit(20)
            )
            result = await db.scalars(stmt)
            batch = list(result.all())

            if not batch:
                break

            for job in batch:
                text = build_job_text(job)
                embedding = await get_embedding(text)
                job.embedding = embedding

            await db.commit()
            embedded += len(batch)

            logger.info("embed_jobs_batch.progress", embedded=embedded, task_id=task_id)
            time.sleep(0.5)

    return {"embedded": embedded, "skipped": 0}


@celery_app.task(name="jobplatform.matching.tasks.embed_jobs_batch", bind=True)
def embed_jobs_batch(self) -> dict:
    task_id = self.request.id or "local"
    return asyncio.run(_embed_jobs_batch_async(task_id))


async def _embed_profile_async(user_id: int, task_id: str) -> dict:
    async with AsyncSessionLocal() as db:
        profile = await db.scalar(select(Profile).where(Profile.user_id == user_id))
        if not profile:
            logger.warning("embed_profile.no_profile", user_id=user_id)
            return {"user_id": user_id, "status": "no_profile"}

        prefs = await db.scalar(
            select(JobPreferences).where(JobPreferences.user_id == user_id)
        )

        text = build_profile_text(profile, prefs)
        if not text.strip():
            logger.warning("embed_profile.empty_text", user_id=user_id)
            return {"user_id": user_id, "status": "empty_text"}

        embedding = await get_embedding(text)
        profile.embedding = embedding
        profile.enriched_at = datetime.now(timezone.utc)
        await db.commit()

        logger.info("embed_profile.done", user_id=user_id, task_id=task_id)
        return {"user_id": user_id, "status": "ok"}


@celery_app.task(name="jobplatform.matching.tasks.embed_profile", bind=True)
def embed_profile(self, user_id: int) -> dict:
    task_id = self.request.id or "local"
    return asyncio.run(_embed_profile_async(user_id, task_id))
