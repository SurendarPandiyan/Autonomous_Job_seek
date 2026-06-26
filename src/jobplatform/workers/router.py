from fastapi import APIRouter, Depends
from pydantic import BaseModel

from jobplatform.auth.models import User
from jobplatform.dependencies import get_current_user
from jobplatform.jobs.tasks import scrape_portal
from jobplatform.workers.service import get_task_status

router = APIRouter(prefix="/api/v1/workers", tags=["workers"])


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


@router.get("/tasks/{task_id}")
async def task_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    return get_task_status(task_id)
