"""Phase 4 — Application Automation tests.

Covers: REQ-07 (model), REQ-08 (LLM tailoring), REQ-09 (POST endpoint),
        REQ-10 (status tracking), REQ-11 (GET listing + filter).
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from jobplatform.applications.models import Application, ApplicationStatus
from jobplatform.applications.service import extract_resume_text
from jobplatform.auth.models import User
from jobplatform.jobs.portals.base import RawJob
from jobplatform.jobs.service import upsert_job
from jobplatform.resumes.models import Resume, FileType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_anthropic(MockClient, tailored_text: str = "Tailored resume content") -> None:
    """Wire a patched AsyncAnthropic so .messages.create returns tailored_text."""
    instance = MagicMock()
    MockClient.return_value = instance
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text=tailored_text)]
    instance.messages.create = AsyncMock(return_value=mock_resp)


def _inject_session(mock_session_cls, db) -> None:
    """Wire a patched AsyncSessionLocal to yield the test db session."""
    mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=db)
    mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)


async def _register_and_login(client, email: str, password: str = "Pass1234!") -> dict:
    """Register + login, return headers dict with Authorization bearer token."""
    await client.post(
        "/api/v1/auth/register", json={"email": email, "password": password}
    )
    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _seed_job(db) -> "jobplatform.jobs.models.Job":
    raw = RawJob(
        portal_id="naukri",
        external_id=f"app-test-{datetime.now().timestamp()}",
        url=f"https://naukri.com/{datetime.now().timestamp()}",
        title="Python Engineer",
        company="TestCo",
        location="Remote",
        description="We need a Python expert.",
    )
    job, _ = await upsert_job(db, raw)
    return job


async def _seed_resume(db, user_id: int) -> Resume:
    resume = Resume(
        user_id=user_id,
        version=1,
        label="main",
        is_default=True,
        file_path="/tmp/test_resume.pdf",
        file_type=FileType.pdf,
        parsed_data={"name": "Test User", "skills": ["Python", "FastAPI"]},
    )
    db.add(resume)
    await db.flush()
    return resume


# ---------------------------------------------------------------------------
# Unit tests: service helpers (no DB, no network)
# ---------------------------------------------------------------------------


def test_extract_resume_text_with_data():
    resume = Resume(
        id=1,
        user_id=1,
        version=1,
        file_path="/tmp/r.pdf",
        file_type=FileType.pdf,
        parsed_data={"name": "Alice", "skills": ["Python"]},
    )
    result = extract_resume_text(resume)
    assert "Alice" in result
    assert "Python" in result


def test_extract_resume_text_no_data():
    resume = Resume(
        id=2,
        user_id=1,
        version=1,
        file_path="/tmp/r.pdf",
        file_type=FileType.pdf,
        parsed_data=None,
    )
    result = extract_resume_text(resume)
    assert result == ""


async def test_tailor_resume():
    from jobplatform.applications.service import tailor_resume

    with patch("jobplatform.applications.service.AsyncAnthropic") as MockClient:
        _mock_anthropic(MockClient, tailored_text="Customized for you")
        result = await tailor_resume("My resume", "Python developer job")

    assert result == "Customized for you"
    # Verify the mock was called with claude-haiku-4-5
    call_kwargs = MockClient.return_value.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-haiku-4-5"
    assert "Python developer job" in call_kwargs["messages"][0]["content"]


# ---------------------------------------------------------------------------
# Model integration test (real DB via db fixture)
# ---------------------------------------------------------------------------


async def test_create_application_model(db, setup_db):
    user = User(email="app_model@example.com", hashed_password="x", is_active=True)
    db.add(user)
    await db.flush()

    job = await _seed_job(db)
    resume = await _seed_resume(db, user.id)

    now = datetime.now(timezone.utc)
    app = Application(
        user_id=user.id,
        job_id=job.id,
        resume_id=resume.id,
        status=ApplicationStatus.pending,
        created_at=now,
        updated_at=now,
    )
    db.add(app)
    await db.commit()

    retrieved = await db.scalar(
        select(Application).where(
            Application.user_id == user.id, Application.job_id == job.id
        )
    )
    assert retrieved is not None
    assert retrieved.status == ApplicationStatus.pending
    assert retrieved.tailored_resume_text is None
    assert retrieved.applied_at is None


# ---------------------------------------------------------------------------
# Endpoint integration tests (real DB + ASGI client + JWT auth)
# ---------------------------------------------------------------------------


async def test_create_application_success(client, db, setup_db):
    headers = await _register_and_login(client, "app_post@example.com")
    user = await db.scalar(select(User).where(User.email == "app_post@example.com"))
    job = await _seed_job(db)
    await db.commit()

    with patch("jobplatform.applications.router.tailor_and_apply") as mock_task:
        mock_task.delay = MagicMock()
        resp = await client.post(
            "/api/v1/applications/",
            json={"job_id": job.id},
            headers=headers,
        )

    assert resp.status_code == 202
    data = resp.json()
    assert data["job_id"] == job.id
    assert data["status"] == "pending"
    assert "id" in data

    # Confirm row in DB
    app = await db.scalar(
        select(Application).where(
            Application.user_id == user.id, Application.job_id == job.id
        )
    )
    assert app is not None


async def test_create_application_dispatches_task(client, db, setup_db):
    headers = await _register_and_login(client, "app_dispatch@example.com")
    job = await _seed_job(db)
    await db.commit()

    with patch("jobplatform.applications.router.tailor_and_apply") as mock_task:
        mock_task.delay = MagicMock()
        resp = await client.post(
            "/api/v1/applications/",
            json={"job_id": job.id},
            headers=headers,
        )
        assert resp.status_code == 202
        app_id = resp.json()["id"]
        mock_task.delay.assert_called_once_with(app_id)


async def test_duplicate_application_409(client, db, setup_db):
    headers = await _register_and_login(client, "app_dup@example.com")
    job = await _seed_job(db)
    await db.commit()

    with patch("jobplatform.applications.router.tailor_and_apply") as mock_task:
        mock_task.delay = MagicMock()
        r1 = await client.post(
            "/api/v1/applications/", json={"job_id": job.id}, headers=headers
        )
        assert r1.status_code == 202

        r2 = await client.post(
            "/api/v1/applications/", json={"job_id": job.id}, headers=headers
        )
        assert r2.status_code == 409
        assert "already applied" in r2.json()["detail"].lower()


async def test_create_application_job_not_found(client, db, setup_db):
    headers = await _register_and_login(client, "app_404@example.com")

    with patch("jobplatform.applications.router.tailor_and_apply") as mock_task:
        mock_task.delay = MagicMock()
        resp = await client.post(
            "/api/v1/applications/",
            json={"job_id": 999999},
            headers=headers,
        )

    assert resp.status_code == 404


async def test_list_applications_empty(client, db, setup_db):
    headers = await _register_and_login(client, "app_list_empty@example.com")
    resp = await client.get("/api/v1/applications/", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_applications_returns_user_apps(client, db, setup_db):
    headers = await _register_and_login(client, "app_list_filled@example.com")
    user = await db.scalar(
        select(User).where(User.email == "app_list_filled@example.com")
    )
    job = await _seed_job(db)
    await db.commit()

    with patch("jobplatform.applications.router.tailor_and_apply") as mock_task:
        mock_task.delay = MagicMock()
        create_resp = await client.post(
            "/api/v1/applications/", json={"job_id": job.id}, headers=headers
        )
    assert create_resp.status_code == 202

    list_resp = await client.get("/api/v1/applications/", headers=headers)
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert len(data) >= 1
    assert data[0]["job_id"] == job.id


async def test_list_applications_status_filter(client, db, setup_db):
    headers = await _register_and_login(client, "app_filter@example.com")
    user = await db.scalar(
        select(User).where(User.email == "app_filter@example.com")
    )
    job = await _seed_job(db)
    await db.commit()

    # Create application directly in DB with status=applied
    now = datetime.now(timezone.utc)
    app = Application(
        user_id=user.id,
        job_id=job.id,
        status=ApplicationStatus.applied,
        applied_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(app)
    await db.commit()

    # Filter by applied → should return our row
    resp = await client.get(
        "/api/v1/applications/?status=applied", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert all(d["status"] == "applied" for d in data)

    # Filter by pending → should return empty (we only have applied)
    resp2 = await client.get(
        "/api/v1/applications/?status=pending", headers=headers
    )
    assert resp2.status_code == 200
    assert resp2.json() == []


# ---------------------------------------------------------------------------
# Task integration tests (async inner function, mocked session + Claude)
# ---------------------------------------------------------------------------


async def test_tailor_and_apply_status_transitions(db, setup_db):
    from jobplatform.applications.tasks import _tailor_and_apply_async

    user = User(email="task_trans@example.com", hashed_password="x", is_active=True)
    db.add(user)
    await db.flush()

    job = await _seed_job(db)
    resume = await _seed_resume(db, user.id)

    now = datetime.now(timezone.utc)
    app = Application(
        user_id=user.id,
        job_id=job.id,
        resume_id=resume.id,
        status=ApplicationStatus.pending,
        created_at=now,
        updated_at=now,
    )
    db.add(app)
    await db.commit()

    with patch("jobplatform.applications.tasks.AsyncSessionLocal") as mock_session_cls, \
         patch("jobplatform.applications.service.AsyncAnthropic") as MockClient:
        _inject_session(mock_session_cls, db)
        _mock_anthropic(MockClient, tailored_text="Tailored resume for Python job")

        result = await _tailor_and_apply_async(app.id, "test-task-id")

    assert result["status"] == "applied"

    await db.refresh(app)
    assert app.status == ApplicationStatus.applied
    assert app.tailored_resume_text == "Tailored resume for Python job"
    assert app.applied_at is not None


async def test_tailor_and_apply_error_resets_to_pending(db, setup_db):
    from jobplatform.applications.tasks import _tailor_and_apply_async

    user = User(email="task_err@example.com", hashed_password="x", is_active=True)
    db.add(user)
    await db.flush()

    job = await _seed_job(db)
    resume = await _seed_resume(db, user.id)

    now = datetime.now(timezone.utc)
    app = Application(
        user_id=user.id,
        job_id=job.id,
        resume_id=resume.id,
        status=ApplicationStatus.pending,
        created_at=now,
        updated_at=now,
    )
    db.add(app)
    await db.commit()

    with patch("jobplatform.applications.tasks.AsyncSessionLocal") as mock_session_cls, \
         patch("jobplatform.applications.service.AsyncAnthropic") as MockClient:
        _inject_session(mock_session_cls, db)
        # Make the LLM call raise an exception
        instance = MagicMock()
        MockClient.return_value = instance
        instance.messages.create = AsyncMock(side_effect=RuntimeError("LLM error"))

        with pytest.raises(RuntimeError, match="LLM error"):
            await _tailor_and_apply_async(app.id, "err-task-id")

    await db.refresh(app)
    # Status must be reset to pending to allow Celery retry
    assert app.status == ApplicationStatus.pending
