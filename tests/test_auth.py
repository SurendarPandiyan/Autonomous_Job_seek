from sqlalchemy.ext.asyncio import AsyncSession

from jobplatform.auth.models import User


async def test_user_model_create(db: AsyncSession):
    user = User(email="test@example.com", hashed_password="hashed")
    db.add(user)
    await db.flush()
    assert user.id is not None
    assert user.is_active is True
    assert user.created_at is not None
