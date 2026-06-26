from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobplatform.preferences.models import JobPreferences
from jobplatform.preferences.schemas import PreferencesUpdate


async def get_or_create_preferences(db: AsyncSession, user_id: int) -> JobPreferences:
    prefs = await db.scalar(select(JobPreferences).where(JobPreferences.user_id == user_id))
    if not prefs:
        prefs = JobPreferences(user_id=user_id)
        db.add(prefs)
        await db.commit()
        await db.refresh(prefs)
    # Ensure list fields are never None (ARRAY server_default may not populate Python-side)
    for field in (
        "target_roles", "technologies", "locations", "employment_type",
        "company_size", "industries", "excluded_companies", "whitelisted_companies",
    ):
        if getattr(prefs, field) is None:
            setattr(prefs, field, [])
    return prefs


async def update_preferences(db: AsyncSession, user_id: int, data: PreferencesUpdate) -> JobPreferences:
    prefs = await get_or_create_preferences(db, user_id)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(prefs, field, value)
    await db.commit()
    await db.refresh(prefs)
    # Ensure list fields are never None after refresh
    for field in (
        "target_roles", "technologies", "locations", "employment_type",
        "company_size", "industries", "excluded_companies", "whitelisted_companies",
    ):
        if getattr(prefs, field) is None:
            setattr(prefs, field, [])
    return prefs
