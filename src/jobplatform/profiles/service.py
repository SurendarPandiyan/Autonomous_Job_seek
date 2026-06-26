from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobplatform.profiles.models import Profile
from jobplatform.profiles.schemas import ProfileUpdate


async def get_or_create_profile(db: AsyncSession, user_id: int) -> Profile:
    profile = await db.scalar(select(Profile).where(Profile.user_id == user_id))
    if not profile:
        profile = Profile(user_id=user_id)
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    # Guard against None for ARRAY columns on a fresh record
    if profile.skills is None:
        profile.skills = []
    if profile.education is None:
        profile.education = []
    if profile.experience is None:
        profile.experience = []
    if profile.certifications is None:
        profile.certifications = []
    return profile


async def update_profile(db: AsyncSession, user_id: int, data: ProfileUpdate) -> Profile:
    profile = await get_or_create_profile(db, user_id)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(profile, field, value)
    await db.commit()
    await db.refresh(profile)
    # Guard against None for ARRAY columns
    if profile.skills is None:
        profile.skills = []
    if profile.education is None:
        profile.education = []
    if profile.experience is None:
        profile.experience = []
    if profile.certifications is None:
        profile.certifications = []
    return profile
