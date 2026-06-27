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
