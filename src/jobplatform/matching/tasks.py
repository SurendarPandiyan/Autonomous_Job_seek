import asyncio
import time

import structlog
from sqlalchemy import select

from jobplatform.celery_app import celery_app
from jobplatform.database import AsyncSessionLocal
from jobplatform.jobs.models import Job
from jobplatform.matching.service import build_job_text, get_embedding

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
