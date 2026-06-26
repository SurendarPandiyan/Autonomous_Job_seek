from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from jobplatform.auth.jwt import decode_token
from jobplatform.auth.models import User
from jobplatform.auth.service import get_user_by_id
from jobplatform.database import get_db

_bearer = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        user_id = decode_token(credentials.credentials, "access")
    except ValueError:
        raise HTTPException(401, "Invalid token")
    user = await get_user_by_id(db, int(user_id))
    if not user or not user.is_active:
        raise HTTPException(401, "User not found or inactive")
    return user
