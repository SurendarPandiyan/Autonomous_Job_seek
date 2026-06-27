from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from jobplatform.auth.models import User
from jobplatform.jobs.portals.base import RawJob
from jobplatform.jobs.service import upsert_job
from jobplatform.matching.models import JobMatch, MatchStatus
from jobplatform.matching.service import (
    build_job_text,
    build_profile_text,
    compute_ats_score,
    compute_skill_gaps,
    get_embedding,
)
from jobplatform.preferences.models import JobPreferences
from jobplatform.profiles.models import Profile, ProfileSource

# 1536-dim sentinel vector reused across every test needing an embedding.
FAKE_EMBEDDING: list[float] = [0.01 * i for i in range(1536)]


# ---------------------------------------------------------------------------
# Unit tests: service helpers (no DB, no network)
# ---------------------------------------------------------------------------


async def test_get_embedding_returns_vector():
    with patch("jobplatform.matching.service.AsyncOpenAI") as MockClient:
        instance = MagicMock()
        MockClient.return_value = instance
        mock_resp = MagicMock()
        mock_resp.data = [MagicMock(embedding=FAKE_EMBEDDING)]
        instance.embeddings.create = AsyncMock(return_value=mock_resp)

        result = await get_embedding("Python developer with 5 years experience")

    assert len(result) == 1536
    assert result == FAKE_EMBEDDING


def test_build_profile_text():
    # Construct in-memory (not persisted) so SQLAlchemy instrumentation is set up.
    profile = Profile(
        current_role="Backend Engineer",
        years_experience=5,
        skills=["Python", "FastAPI"],
        experience=[{"title": "Engineer", "company": "Acme"}],
    )

    prefs = JobPreferences(
        target_roles=["Senior Engineer"],
        technologies=["PostgreSQL"],
        locations=["Bengaluru"],
    )

    text = build_profile_text(profile, prefs)
    assert "Backend Engineer" in text
    assert "Python" in text
    assert "Senior Engineer" in text


def test_build_job_text():
    from jobplatform.jobs.models import Job

    job = Job(
        title="Software Engineer",
        company="Acme",
        location="Remote",
        description="We are looking for a Python developer.",
        requirements={"skills": ["Python", "SQL"]},
    )

    text = build_job_text(job)
    assert "Software Engineer" in text
    assert "Acme" in text
    assert "Python developer" in text


def test_compute_ats_score_full_match():
    skills = ["Python", "FastAPI"]
    job_text = "We need Python and FastAPI experience."
    assert compute_ats_score(skills, job_text) == 1.0


def test_compute_ats_score_no_match():
    assert compute_ats_score([], "any text") == 0.0


def test_compute_skill_gaps():
    profile_skills = ["Python", "FastAPI"]
    requirements = {"skills": ["Python", "FastAPI", "Kubernetes"]}
    gaps = compute_skill_gaps(profile_skills, requirements)
    assert "Kubernetes" in gaps
    assert "Python" not in gaps
    assert "FastAPI" not in gaps


# ---------------------------------------------------------------------------
# Model integration test (real DB via `db` fixture)
# ---------------------------------------------------------------------------


async def test_job_match_model_create(db, setup_db):
    user = User(email="match_test@example.com", hashed_password="x", is_active=True)
    db.add(user)
    await db.flush()

    raw = RawJob(
        portal_id="naukri",
        external_id="jm-001",
        url="https://naukri.com/jm-001",
        title="ML Engineer",
        company="TechCorp",
        location="Bengaluru",
    )
    job, _ = await upsert_job(db, raw)

    match = JobMatch(
        user_id=user.id,
        job_id=job.id,
        score=0.85,
        ats_score=0.75,
        skill_gaps=["Kubernetes"],
        status=MatchStatus.new,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(match)
    await db.commit()

    retrieved = await db.scalar(
        select(JobMatch).where(JobMatch.user_id == user.id, JobMatch.job_id == job.id)
    )
    assert retrieved is not None
    assert retrieved.score == pytest.approx(0.85)
    assert retrieved.status == MatchStatus.new
    assert "Kubernetes" in retrieved.skill_gaps


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _inject_session(mock_session_cls, db):
    """Wire a patched AsyncSessionLocal to yield the test `db` session.

    Task coroutines open their own `AsyncSessionLocal()` (bound to the app DB,
    not the test DB). Patching it to return the test session — mirroring
    tests/test_scrape_worker.py — keeps reads/writes inside the rolled-back
    transaction and visible to the test's seeded data.
    """
    mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=db)
    mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)


def _mock_openai(MockClient):
    """Configure a patched AsyncOpenAI so `.embeddings.create` is awaitable."""
    instance = MagicMock()
    MockClient.return_value = instance
    mock_resp = MagicMock()
    mock_resp.data = [MagicMock(embedding=FAKE_EMBEDDING)]
    instance.embeddings.create = AsyncMock(return_value=mock_resp)


# ---------------------------------------------------------------------------
# Service / task integration tests (real DB)
# ---------------------------------------------------------------------------


async def test_find_similar_jobs(db, setup_db):
    from jobplatform.matching.service import find_similar_jobs

    raw1 = RawJob(portal_id="naukri", external_id="sim-001", url="https://x.com/1",
                  title="Python Dev", company="A", location="Remote")
    raw2 = RawJob(portal_id="naukri", external_id="sim-002", url="https://x.com/2",
                  title="Java Dev", company="B", location="Remote")
    job1, _ = await upsert_job(db, raw1)
    job2, _ = await upsert_job(db, raw2)

    # Give both jobs embeddings; job1 identical to the query vector.
    job1.embedding = FAKE_EMBEDDING
    job2.embedding = [0.5] * 1536
    await db.commit()

    results = await find_similar_jobs(db, FAKE_EMBEDDING, limit=10)

    job_ids = [j.id for j, _ in results]
    assert job1.id in job_ids
    # Identical vector → cosine distance 0 → highest similarity, ranks first.
    assert results[0][0].id == job1.id
    assert results[0][1] == pytest.approx(1.0, abs=0.01)


async def test_embed_jobs_batch_task(db, setup_db):
    from jobplatform.matching.tasks import _embed_jobs_batch_async

    raw = RawJob(portal_id="naukri", external_id="batch-001", url="https://x.com/b1",
                 title="Batch Engineer", company="BatchCo", location="Remote",
                 description="Python needed")
    job, _ = await upsert_job(db, raw)
    await db.commit()
    assert job.embedding is None

    with patch("jobplatform.matching.tasks.AsyncSessionLocal") as mock_session_cls, \
         patch("jobplatform.matching.service.AsyncOpenAI") as MockClient:
        _inject_session(mock_session_cls, db)
        _mock_openai(MockClient)
        result = await _embed_jobs_batch_async("batch-task-id")

    assert result["embedded"] >= 1
    await db.refresh(job)
    assert job.embedding is not None
    assert len(job.embedding) == 1536


async def test_embed_profile_task(db, setup_db):
    from jobplatform.matching.tasks import _embed_profile_async

    user = User(email="embed_profile@example.com", hashed_password="x", is_active=True)
    db.add(user)
    await db.flush()

    profile = Profile(
        user_id=user.id,
        current_role="Engineer",
        skills=["Python"],
        source=ProfileSource.manual,
    )
    db.add(profile)
    await db.commit()
    assert profile.embedding is None

    with patch("jobplatform.matching.tasks.AsyncSessionLocal") as mock_session_cls, \
         patch("jobplatform.matching.service.AsyncOpenAI") as MockClient:
        _inject_session(mock_session_cls, db)
        _mock_openai(MockClient)
        result = await _embed_profile_async(user.id, "embed-task-id")

    assert result["status"] == "ok"
    await db.refresh(profile)
    assert profile.embedding is not None
    assert len(profile.embedding) == 1536


async def test_compute_matches_task(db, setup_db):
    from jobplatform.matching.tasks import _compute_matches_async

    user = User(email="task_test@example.com", hashed_password="x", is_active=True)
    db.add(user)
    await db.flush()

    profile = Profile(
        user_id=user.id,
        current_role="Engineer",
        skills=["Python"],
        source=ProfileSource.manual,
    )
    db.add(profile)

    raw = RawJob(portal_id="naukri", external_id="task-001", url="https://x.com/t1",
                 title="Python Engineer", company="Co", location="Remote",
                 description="Python needed", requirements={"skills": ["Python"]})
    job, _ = await upsert_job(db, raw)
    job.embedding = FAKE_EMBEDDING
    await db.commit()

    with patch("jobplatform.matching.tasks.AsyncSessionLocal") as mock_session_cls, \
         patch("jobplatform.matching.service.AsyncOpenAI") as MockClient:
        _inject_session(mock_session_cls, db)
        _mock_openai(MockClient)
        result = await _compute_matches_async(user.id, "test-task-id")

    assert result["user_id"] == user.id
    assert result["matched"] >= 1

    match = await db.scalar(
        select(JobMatch).where(JobMatch.user_id == user.id, JobMatch.job_id == job.id)
    )
    assert match is not None
    assert match.score is not None
    assert match.ats_score is not None


# ---------------------------------------------------------------------------
# Endpoint tests (real DB + ASGI client + JWT auth)
# ---------------------------------------------------------------------------


async def test_list_matches_endpoint(client, db, setup_db):
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "list_match@example.com", "password": "Pass1234!"},
    )
    assert reg.status_code == 201
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "list_match@example.com", "password": "Pass1234!"},
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    user = await db.scalar(select(User).where(User.email == "list_match@example.com"))

    raw = RawJob(portal_id="naukri", external_id="ep-001", url="https://x.com/ep1",
                 title="EP Job", company="EP Corp", location="Remote")
    job, _ = await upsert_job(db, raw)

    match = JobMatch(
        user_id=user.id,
        job_id=job.id,
        score=0.90,
        ats_score=0.80,
        skill_gaps=[],
        status=MatchStatus.new,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(match)
    await db.commit()

    resp = await client.get("/api/v1/matches/", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["score"] == pytest.approx(0.90, abs=0.01)


async def test_get_job_match_endpoint_returns_stored(client, db, setup_db):
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "stored_match@example.com", "password": "Pass1234!"},
    )
    assert reg.status_code == 201
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "stored_match@example.com", "password": "Pass1234!"},
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    user = await db.scalar(select(User).where(User.email == "stored_match@example.com"))

    raw = RawJob(portal_id="linkedin", external_id="sm-001", url="https://x.com/sm1",
                 title="Stored Match Job", company="SM Co", location="Remote")
    job, _ = await upsert_job(db, raw)

    match = JobMatch(
        user_id=user.id,
        job_id=job.id,
        score=0.77,
        ats_score=0.60,
        skill_gaps=["Docker"],
        status=MatchStatus.new,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(match)
    await db.commit()

    resp = await client.get(f"/api/v1/jobs/{job.id}/match", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["score"] == pytest.approx(0.77, abs=0.01)
    assert "Docker" in data["skill_gaps"]


async def test_get_job_match_endpoint_pending(client, db, setup_db):
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "pending_match@example.com", "password": "Pass1234!"},
    )
    assert reg.status_code == 201
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "pending_match@example.com", "password": "Pass1234!"},
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Job with NO embedding → on-demand compute impossible → pending.
    raw = RawJob(portal_id="indeed", external_id="pend-001", url="https://x.com/p1",
                 title="Pending Job", company="Pend Co", location="Remote")
    job, _ = await upsert_job(db, raw)
    assert job.embedding is None
    await db.commit()

    resp = await client.get(f"/api/v1/jobs/{job.id}/match", headers=headers)
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "pending"
    assert data["score"] is None


async def test_get_job_match_endpoint_on_demand(client, db, setup_db):
    # Branch 3: no stored match, but both job and profile embeddings exist →
    # endpoint computes the match on demand, upserts, returns 200.
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "ondemand_match@example.com", "password": "Pass1234!"},
    )
    assert reg.status_code == 201
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "ondemand_match@example.com", "password": "Pass1234!"},
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    user = await db.scalar(select(User).where(User.email == "ondemand_match@example.com"))

    profile = Profile(
        user_id=user.id,
        current_role="Engineer",
        skills=["Python"],
        source=ProfileSource.manual,
        embedding=FAKE_EMBEDDING,
    )
    db.add(profile)

    raw = RawJob(portal_id="naukri", external_id="od-001", url="https://x.com/od1",
                 title="On Demand Job", company="OD Co", location="Remote",
                 description="Python needed", requirements={"skills": ["Python", "Kafka"]})
    job, _ = await upsert_job(db, raw)
    job.embedding = FAKE_EMBEDDING
    await db.commit()

    with patch("jobplatform.matching.service.AsyncOpenAI") as MockClient:
        _mock_openai(MockClient)
        resp = await client.get(f"/api/v1/jobs/{job.id}/match", headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    # Identical embeddings → similarity ~1.0.
    assert data["score"] == pytest.approx(1.0, abs=0.01)
    assert "Kafka" in data["skill_gaps"]

    # Match was persisted (upserted) by the on-demand branch.
    stored = await db.scalar(
        select(JobMatch).where(JobMatch.user_id == user.id, JobMatch.job_id == job.id)
    )
    assert stored is not None
