import bcrypt as _bcrypt_lib
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobplatform.auth.models import User
from jobplatform.auth.schemas import RegisterRequest

_BCRYPT_ROUNDS = 12


def _hash_password(password: str) -> str:
    return _bcrypt_lib.hashpw(password.encode(), _bcrypt_lib.gensalt(rounds=_BCRYPT_ROUNDS)).decode()


def _verify_password(password: str, hashed: str) -> bool:
    return _bcrypt_lib.checkpw(password.encode(), hashed.encode())


async def create_user(db: AsyncSession, data: RegisterRequest) -> User:
    existing = await db.scalar(select(User).where(User.email == data.email))
    if existing:
        raise ValueError("Email already registered")
    user = User(email=data.email, hashed_password=_hash_password(data.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    user = await db.scalar(select(User).where(User.email == email))
    if not user or not _verify_password(password, user.hashed_password):
        raise ValueError("Invalid credentials")
    if not user.is_active:
        raise ValueError("Account deactivated")
    return user


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    return await db.scalar(select(User).where(User.id == user_id))


async def delete_user(db: AsyncSession, user_id: int) -> None:
    from sqlalchemy import delete as sa_delete
    await db.execute(sa_delete(User).where(User.id == user_id))
    await db.commit()
