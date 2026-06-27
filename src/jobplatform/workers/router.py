from fastapi import APIRouter, Depends
from pydantic import BaseModel

from jobplatform.auth.models import User
from jobplatform.dependencies import get_current_user
from jobplatform.jobs.tasks import scrape_portal
from jobplatform.matching.tasks import compute_matches_for_user, embed_jobs_batch, embed_profile
from jobplatform.workers.service import get_task_status

router = APIRouter(prefix="/api/v1/workers", tags=["workers"])


class ComputeMatchesRequest(BaseModel):
    user_id: int


class EmbedProfileRequest(BaseModel):
    user_id: int


class ScrapeRequest(BaseModel):
    portal_id: str
    keywords: str
    location: str
    max_results: int = 50


@router.post("/scrape", status_code=202)
async def trigger_scrape(
    req: ScrapeRequest,
    current_user: User = Depends(get_current_user),
):
    task = scrape_portal.apply_async(
        kwargs={
            "portal_id": req.portal_id,
            "keywords": req.keywords,
            "location": req.location,
            "max_results": req.max_results,
        }
    )
    return {"task_id": task.id}


@router.post("/embed-jobs", status_code=202)
async def trigger_embed_jobs(
    current_user: User = Depends(get_current_user),
):
    task = embed_jobs_batch.apply_async()
    return {"task_id": task.id}


@router.post("/embed-profile", status_code=202)
async def trigger_embed_profile(
    req: EmbedProfileRequest,
    current_user: User = Depends(get_current_user),
):
    task = embed_profile.apply_async(kwargs={"user_id": req.user_id})
    return {"task_id": task.id}


@router.post("/compute-matches", status_code=202)
async def trigger_compute_matches(
    req: ComputeMatchesRequest,
    current_user: User = Depends(get_current_user),
):
    task = compute_matches_for_user.apply_async(kwargs={"user_id": req.user_id})
    return {"task_id": task.id}


@router.get("/tasks/{task_id}")
async def task_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    return get_task_status(task_id)
