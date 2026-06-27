from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from jobplatform.applications.schemas import ApplicationCreate, ApplicationResponse
from jobplatform.applications.service import create_application, list_applications
from jobplatform.applications.tasks import tailor_and_apply
from jobplatform.auth.models import User
from jobplatform.database import get_db
from jobplatform.dependencies import get_current_user

router = APIRouter(prefix="/api/v1", tags=["applications"])


@router.post(
    "/applications/",
    response_model=ApplicationResponse,
    status_code=202,
)
async def create_application_endpoint(
    body: ApplicationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApplicationResponse:
    """Create an application and dispatch the Celery tailoring task.

    Returns 202 Accepted immediately. The LLM tailoring runs asynchronously.
    Poll GET /api/v1/applications/ to check status progression.
    """
    app = await create_application(db, current_user.id, body.job_id, body.resume_id)
    tailor_and_apply.delay(app.id)
    return ApplicationResponse.model_validate(app)


@router.get(
    "/applications/",
    response_model=list[ApplicationResponse],
)
async def list_applications_endpoint(
    status: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ApplicationResponse]:
    """List applications for the authenticated user.

    Optional filters:
    - ?status=pending|tailoring|applied|rejected|interview|offer
    - ?cursor=<id>  (for cursor-based pagination, pass last seen id)
    - ?limit=N      (default 20, max 100)
    """
    apps = await list_applications(
        db,
        current_user.id,
        status=status,
        limit=limit,
        cursor=cursor,
    )
    return [ApplicationResponse.model_validate(a) for a in apps]
