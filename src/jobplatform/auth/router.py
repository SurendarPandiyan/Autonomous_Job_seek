from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from jobplatform.auth.jwt import create_token, decode_token
from jobplatform.auth.schemas import LoginRequest, RegisterRequest, UserResponse
from jobplatform.auth.service import authenticate_user, create_user, get_user_by_id
from jobplatform.database import get_db
from jobplatform.rate_limiting import limiter

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _issue_tokens(response: Response, user_id: int) -> str:
    access = create_token(str(user_id), "access")
    refresh = create_token(str(user_id), "refresh")
    response.set_cookie(
        "refresh_token", refresh, httponly=True, samesite="lax", max_age=7 * 24 * 3600
    )
    return access


@router.post("/register", status_code=201)
@limiter.limit("5/minute")
async def register(
    request: Request, data: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)
):
    try:
        user = await create_user(db, data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    access = _issue_tokens(response, user.id)
    return {"access_token": access, "token_type": "bearer", "user": UserResponse.model_validate(user)}


@router.post("/login")
@limiter.limit("10/minute")
async def login(
    request: Request, data: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)
):
    try:
        user = await authenticate_user(db, data.email, data.password)
    except ValueError as e:
        raise HTTPException(401, str(e))
    access = _issue_tokens(response, user.id)
    return {"access_token": access, "token_type": "bearer"}


@router.post("/refresh")
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not refresh_token:
        raise HTTPException(401, "No refresh token")
    try:
        user_id = decode_token(refresh_token, "refresh")
    except ValueError:
        raise HTTPException(401, "Invalid refresh token")
    user = await get_user_by_id(db, int(user_id))
    if not user or not user.is_active:
        raise HTTPException(401, "User not found")
    access = _issue_tokens(response, user.id)
    return {"access_token": access, "token_type": "bearer"}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("refresh_token")
    return {"message": "Logged out"}
