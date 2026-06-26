import io
import os
import tempfile

from httpx import AsyncClient

from jobplatform.resumes.storage import LocalFileStorage


async def _token(client: AsyncClient, email: str) -> str:
    resp = await client.post("/api/v1/auth/register", json={"email": email, "password": "pass"})
    return resp.json()["access_token"]


async def test_local_storage_save_and_delete():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalFileStorage(tmpdir)
        content = b"PDF content here"
        path = await storage.save(content, "resume.pdf")
        assert os.path.exists(path)
        assert path.endswith(".pdf")
        url = storage.url(path)
        assert url.startswith("/uploads/")
        await storage.delete(path)
        assert not os.path.exists(path)


async def test_local_storage_delete_nonexistent_is_noop():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalFileStorage(tmpdir)
        await storage.delete("/nonexistent/path.pdf")  # must not raise


async def test_upload_resume(client: AsyncClient):
    token = await _token(client, "r1@example.com")
    pdf_bytes = b"%PDF-1.4 fake pdf content"
    resp = await client.post(
        "/api/v1/resumes/",
        files={"file": ("my_resume.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        data={"label": "v1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["label"] == "v1"
    assert body["file_type"] == "pdf"
    assert body["is_default"] is True  # first upload is default


async def test_list_resumes(client: AsyncClient):
    token = await _token(client, "r2@example.com")
    pdf_bytes = b"%PDF-1.4 content"
    await client.post(
        "/api/v1/resumes/",
        files={"file": ("a.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = await client.get("/api/v1/resumes/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_get_resume_by_id(client: AsyncClient):
    token = await _token(client, "r3@example.com")
    upload = await client.post(
        "/api/v1/resumes/",
        files={"file": ("b.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    resume_id = upload.json()["id"]
    resp = await client.get(f"/api/v1/resumes/{resume_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["id"] == resume_id


async def test_delete_resume(client: AsyncClient):
    token = await _token(client, "r4@example.com")
    upload = await client.post(
        "/api/v1/resumes/",
        files={"file": ("c.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    resume_id = upload.json()["id"]
    resp = await client.delete(f"/api/v1/resumes/{resume_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 204
    resp2 = await client.get(f"/api/v1/resumes/{resume_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp2.status_code == 404


async def test_upload_invalid_type_rejected(client: AsyncClient):
    token = await _token(client, "r5@example.com")
    resp = await client.post(
        "/api/v1/resumes/",
        files={"file": ("bad.txt", io.BytesIO(b"text"), "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
