import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from jobplatform.jobs.portals.base import RawJob, JobQuery


async def test_scrape_portal_task_creates_jobs(db):
    """Scrape task calls adapter, upserts jobs, returns summary."""
    fake_jobs = [
        RawJob(
            portal_id="naukri",
            external_id=f"t-{i}",
            url=f"https://naukri.com/t-{i}",
            title=f"Engineer {i}",
            company="Corp",
            location="Bengaluru",
        )
        for i in range(3)
    ]

    with patch("jobplatform.jobs.tasks.portal_registry") as mock_registry, \
         patch("jobplatform.jobs.tasks.AsyncSessionLocal") as mock_session_cls, \
         patch("jobplatform.jobs.tasks.publish_log"):

        mock_adapter = AsyncMock()
        mock_adapter.search_jobs = AsyncMock(return_value=fake_jobs)
        mock_registry.get.return_value = mock_adapter

        # Use real db session
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=db)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        from jobplatform.jobs.tasks import _scrape_portal_async
        result = await _scrape_portal_async("naukri", "Engineer", "Bengaluru", 10, "test-task-id")

    assert result["portal_id"] == "naukri"
    assert result["total"] == 3
    assert result["created"] == 3
    assert result["errors"] == 0


async def test_scrape_portal_task_deduplicates(db):
    """Running scrape twice with same jobs doesn't double-create."""
    raw = RawJob(
        portal_id="naukri",
        external_id="dup-1",
        url="https://naukri.com/dup-1",
        title="Dup Engineer",
        company="DupCo",
        location="Mumbai",
    )

    with patch("jobplatform.jobs.tasks.portal_registry") as mock_registry, \
         patch("jobplatform.jobs.tasks.AsyncSessionLocal") as mock_session_cls, \
         patch("jobplatform.jobs.tasks.publish_log"):

        mock_adapter = AsyncMock()
        mock_adapter.search_jobs = AsyncMock(return_value=[raw])
        mock_registry.get.return_value = mock_adapter
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=db)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        from jobplatform.jobs.tasks import _scrape_portal_async

        r1 = await _scrape_portal_async("naukri", "Dup", "Mumbai", 5, "t1")
        r2 = await _scrape_portal_async("naukri", "Dup", "Mumbai", 5, "t2")

    assert r1["created"] == 1
    assert r2["created"] == 0
