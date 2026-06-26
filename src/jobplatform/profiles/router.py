from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from jobplatform.auth.models import User
from jobplatform.database import get_db
from jobplatform.dependencies import get_current_user
from jobplatform.profiles.schemas import ProfileResponse, ProfileUpdate
from jobplatform.profiles.service import get_or_create_profile, update_profile

router = APIRouter(prefix="/api/v1/users/me", tags=["profiles"])


@router.get("/profile", response_model=ProfileResponse)
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_or_create_profile(db, current_user.id)


@router.patch("/profile", response_model=ProfileResponse)
async def patch_profile(
    data: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await update_profile(db, current_user.id, data)
