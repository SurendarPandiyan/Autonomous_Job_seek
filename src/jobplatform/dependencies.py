from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from jobplatform.auth.jwt import decode_token
from jobplatform.auth.models import User
from jobplatform.auth.service import get_user_by_id
from jobplatform.database import get_db


class _BearerWith403(HTTPBearer):
    """HTTPBearer that raises 403 (not 401) when no credentials are present."""

    async def __call__(self, request: Request) -> HTTPAuthorizationCredentials | None:
        try:
            return await super().__call__(request)
        except HTTPException as exc:
            if exc.status_code == 401:
                raise HTTPException(403, "Not authenticated")
            raise


_bearer = _BearerWith403()


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
