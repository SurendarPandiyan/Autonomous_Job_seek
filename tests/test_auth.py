import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from jobplatform.auth.jwt import create_token, decode_token
from jobplatform.auth.models import User


async def test_user_model_create(db: AsyncSession):
    user = User(email="test@example.com", hashed_password="hashed")
    db.add(user)
    await db.flush()
    assert user.id is not None
    assert user.is_active is True
    assert user.created_at is not None


def test_create_and_decode_access_token():
    token = create_token("42", "access")
    subject = decode_token(token, "access")
    assert subject == "42"


def test_create_and_decode_refresh_token():
    token = create_token("7", "refresh")
    subject = decode_token(token, "refresh")
    assert subject == "7"


def test_wrong_token_type_raises():
    token = create_token("1", "access")
    with pytest.raises(ValueError):
        decode_token(token, "refresh")


def test_invalid_token_raises():
    with pytest.raises(ValueError):
        decode_token("not.a.token", "access")
