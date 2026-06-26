from httpx import AsyncClient


async def _token(client: AsyncClient, email: str) -> str:
    resp = await client.post("/api/v1/auth/register", json={"email": email, "password": "pass"})
    return resp.json()["access_token"]


async def test_get_preferences_returns_defaults(client: AsyncClient):
    token = await _token(client, "pref1@example.com")
    resp = await client.get(
        "/api/v1/users/me/preferences", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["auto_apply"] is False
    assert body["ai_provider_preference"] == "claude"
    assert body["target_roles"] == []


async def test_patch_preferences_updates(client: AsyncClient):
    token = await _token(client, "pref2@example.com")
    resp = await client.patch(
        "/api/v1/users/me/preferences",
        json={
            "target_roles": ["Backend Engineer", "Python Developer"],
            "salary_min": 1200000,
            "salary_max": 2000000,
            "remote_preference": "remote",
            "auto_apply": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "Backend Engineer" in body["target_roles"]
    assert body["salary_min"] == 1200000
    assert body["auto_apply"] is True
    assert body["remote_preference"] == "remote"


async def test_preferences_ai_provider_changeable(client: AsyncClient):
    token = await _token(client, "pref3@example.com")
    resp = await client.patch(
        "/api/v1/users/me/preferences",
        json={"ai_provider_preference": "openai"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["ai_provider_preference"] == "openai"
