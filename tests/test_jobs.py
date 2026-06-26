import pytest
from sqlalchemy import select

from jobplatform.jobs.models import Job, Portal
from jobplatform.jobs.portals.base import RawJob
from jobplatform.jobs.service import upsert_job, list_jobs, get_job


async def test_job_model_create(db):
    job = Job(
        portal=Portal.naukri,
        external_id="naukri-123",
        url="https://naukri.com/job/123",
        title="Python Developer",
        company="Acme Corp",
        location="Bengaluru",
        description="We need Python skills",
        dedup_hash="abc123",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    assert job.id is not None
    assert job.is_active is True
    assert job.portal == Portal.naukri


async def test_upsert_job_creates_new(db):
    raw = RawJob(
        portal_id="naukri",
        external_id="u-001",
        url="https://naukri.com/u-001",
        title="SRE Engineer",
        company="BigCo",
        location="Hyderabad",
    )
    job, created = await upsert_job(db, raw)
    assert created is True
    assert job.id is not None
    assert job.title == "SRE Engineer"


async def test_upsert_job_deduplicates(db):
    raw = RawJob(
        portal_id="naukri",
        external_id="u-002",
        url="https://naukri.com/u-002",
        title="Go Engineer",
        company="MegaCo",
        location="Chennai",
    )
    job1, created1 = await upsert_job(db, raw)
    job2, created2 = await upsert_job(db, raw)
    assert created1 is True
    assert created2 is False
    assert job1.id == job2.id


async def test_list_jobs_returns_all(db):
    raw = RawJob(
        portal_id="linkedin",
        external_id="l-001",
        url="https://linkedin.com/l-001",
        title="Frontend Dev",
        company="StartupX",
        location="Remote",
    )
    await upsert_job(db, raw)
    jobs = await list_jobs(db)
    assert any(j.title == "Frontend Dev" for j in jobs)


async def test_get_job_not_found_raises(db):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await get_job(db, 999999)
    assert exc.value.status_code == 404
