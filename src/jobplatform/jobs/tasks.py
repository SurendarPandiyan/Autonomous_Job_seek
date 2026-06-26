import asyncio

import structlog

from jobplatform.celery_app import celery_app
from jobplatform.database import AsyncSessionLocal
from jobplatform.jobs.portals import portal_registry
from jobplatform.jobs.portals.base import JobQuery
from jobplatform.jobs.service import upsert_job
from jobplatform.workers.service import publish_log

logger = structlog.get_logger()


async def _scrape_portal_async(
    portal_id: str,
    keywords: str,
    location: str,
    max_results: int,
    task_id: str,
) -> dict:
    publish_log(task_id, "info", f"Starting scrape: {portal_id}", progress_pct=0.0)
    try:
        adapter = portal_registry.get(portal_id)
    except KeyError:
        publish_log(task_id, "error", f"Unknown portal: {portal_id}", progress_pct=100.0)
        return {"portal_id": portal_id, "total": 0, "created": 0, "errors": 1}
    query = JobQuery(keywords=keywords, location=location, max_results=max_results)

    try:
        raw_jobs = await adapter.search_jobs(query)
    except Exception as exc:
        publish_log(task_id, "error", f"Adapter error: {exc}", progress_pct=100.0)
        return {"portal_id": portal_id, "total": 0, "created": 0, "errors": 1}

    publish_log(task_id, "info", f"Found {len(raw_jobs)} raw jobs", progress_pct=30.0)

    total = len(raw_jobs)
    created = 0
    errors = 0

    async with AsyncSessionLocal() as db:
        for i, raw in enumerate(raw_jobs, 1):
            try:
                _, was_created = await upsert_job(db, raw)
                if was_created:
                    created += 1
            except Exception as exc:
                logger.warning("upsert_failed", title=raw.title, error=str(exc))
                errors += 1
            pct = 30.0 + (i / total) * 70.0
            if i % 5 == 0 or i == total:
                publish_log(task_id, "info", f"Processed {i}/{total} jobs", progress_pct=pct)

    publish_log(task_id, "info", f"Done: {created} new, {errors} errors", progress_pct=100.0)
    return {"portal_id": portal_id, "total": total, "created": created, "errors": errors}


@celery_app.task(name="jobplatform.jobs.tasks.scrape_portal", bind=True)
def scrape_portal(self, portal_id: str, keywords: str, location: str, max_results: int = 50) -> dict:
    task_id = self.request.id or "local"
    return asyncio.run(_scrape_portal_async(portal_id, keywords, location, max_results, task_id))
