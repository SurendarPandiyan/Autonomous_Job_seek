from httpx import AsyncClient


async def _register_and_token(client: AsyncClient, email: str = "p@example.com") -> str:
    resp = await client.post("/api/v1/auth/register", json={"email": email, "password": "pass"})
    return resp.json()["access_token"]


async def test_get_profile_creates_empty_profile(client: AsyncClient):
    token = await _register_and_token(client, "gp@example.com")
    resp = await client.get("/api/v1/users/me/profile", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] is not None
    assert body["skills"] == []


async def test_patch_profile_updates_fields(client: AsyncClient):
    token = await _register_and_token(client, "pp@example.com")
    resp = await client.patch(
        "/api/v1/users/me/profile",
        json={"full_name": "Surendar", "skills": ["Python", "FastAPI"], "years_experience": 3},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["full_name"] == "Surendar"
    assert "Python" in body["skills"]
    assert body["years_experience"] == 3


async def test_profile_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/users/me/profile")
    assert resp.status_code == 403
