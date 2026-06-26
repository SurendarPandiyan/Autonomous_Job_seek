from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from jobplatform.auth.models import User
from jobplatform.database import get_db
from jobplatform.dependencies import get_current_user
from jobplatform.preferences.schemas import PreferencesResponse, PreferencesUpdate
from jobplatform.preferences.service import get_or_create_preferences, update_preferences

router = APIRouter(prefix="/api/v1/users/me", tags=["preferences"])


@router.get("/preferences", response_model=PreferencesResponse)
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_or_create_preferences(db, current_user.id)


@router.patch("/preferences", response_model=PreferencesResponse)
async def patch_preferences(
    data: PreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await update_preferences(db, current_user.id, data)
