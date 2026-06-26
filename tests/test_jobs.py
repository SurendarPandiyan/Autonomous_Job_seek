import pytest
from sqlalchemy import select

from jobplatform.jobs.models import Job, Portal


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
