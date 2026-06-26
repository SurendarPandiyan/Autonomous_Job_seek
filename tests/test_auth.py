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


from httpx import AsyncClient


async def test_register_success(client: AsyncClient):
    resp = await client.post("/api/v1/auth/register", json={"email": "new@example.com", "password": "secret123"})
    assert resp.status_code == 201
    body = resp.json()
    assert "access_token" in body
    assert body["user"]["email"] == "new@example.com"


async def test_register_duplicate_email(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={"email": "dup@example.com", "password": "pass"})
    resp = await client.post("/api/v1/auth/register", json={"email": "dup@example.com", "password": "pass"})
    assert resp.status_code == 400


async def test_login_success(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={"email": "login@example.com", "password": "mypass"})
    resp = await client.post("/api/v1/auth/login", json={"email": "login@example.com", "password": "mypass"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()
    assert "refresh_token" in resp.cookies


async def test_login_wrong_password(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={"email": "pw@example.com", "password": "correct"})
    resp = await client.post("/api/v1/auth/login", json={"email": "pw@example.com", "password": "wrong"})
    assert resp.status_code == 401


async def test_refresh_returns_new_access_token(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={"email": "ref@example.com", "password": "pass"})
    login = await client.post("/api/v1/auth/login", json={"email": "ref@example.com", "password": "pass"})
    refresh_cookie = login.cookies["refresh_token"]
    resp = await client.post("/api/v1/auth/refresh", cookies={"refresh_token": refresh_cookie})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_logout_clears_cookie(client: AsyncClient):
    resp = await client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
    assert resp.cookies.get("refresh_token") is None or resp.cookies["refresh_token"] == ""
