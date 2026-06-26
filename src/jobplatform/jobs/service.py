from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobplatform.jobs.models import Job, Portal, make_dedup_hash
from jobplatform.jobs.portals.base import RawJob


async def upsert_job(db: AsyncSession, raw: RawJob) -> tuple[Job, bool]:
    dedup_hash = make_dedup_hash(raw.title, raw.company, raw.location)
    existing = await db.scalar(select(Job).where(Job.dedup_hash == dedup_hash))
    if existing:
        return existing, False
    job = Job(
        portal=Portal(raw.portal_id),
        external_id=raw.external_id,
        url=raw.url,
        title=raw.title,
        company=raw.company,
        location=raw.location,
        description=raw.description,
        requirements=raw.requirements,
        salary_min=raw.salary_min,
        salary_max=raw.salary_max,
        employment_type=raw.employment_type,
        posted_at=raw.posted_at,
        dedup_hash=dedup_hash,
        raw_data=raw.raw_data,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job, True


async def list_jobs(
    db: AsyncSession,
    portal: str | None = None,
    title_search: str | None = None,
    limit: int = 50,
    cursor: int | None = None,
) -> list[Job]:
    q = select(Job).where(Job.is_active == True).order_by(Job.id.desc()).limit(limit)
    if portal:
        q = q.where(Job.portal == Portal(portal))
    if title_search:
        q = q.where(Job.title.ilike(f"%{title_search}%"))
    if cursor:
        q = q.where(Job.id < cursor)
    result = await db.scalars(q)
    return list(result.all())


async def get_job(db: AsyncSession, job_id: int) -> Job:
    job = await db.scalar(select(Job).where(Job.id == job_id))
    if not job:
        raise HTTPException(404, "Job not found")
    return job
