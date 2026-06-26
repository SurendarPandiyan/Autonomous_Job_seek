from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from jobplatform.auth.models import User
from jobplatform.database import get_db
from jobplatform.dependencies import get_current_user
from jobplatform.jobs.schemas import JobResponse
from jobplatform.jobs.service import get_job, list_jobs

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.get("/", response_model=list[JobResponse])
async def list_jobs_endpoint(
    portal: str | None = Query(default=None),
    title: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    cursor: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await list_jobs(db, portal=portal, title_search=title, limit=limit, cursor=cursor)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job_endpoint(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_job(db, job_id)
