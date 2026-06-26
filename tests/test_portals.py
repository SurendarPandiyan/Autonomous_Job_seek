from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from jobplatform.jobs.portals.base import BasePortalAdapter, JobQuery, RawJob
from jobplatform.jobs.portals.registry import PortalRegistry


class FakeAdapter(BasePortalAdapter):
    portal_id = "fake"
    supports_auto_apply = False

    async def search_jobs(self, query: JobQuery) -> list[RawJob]:
        return [
            RawJob(
                portal_id="fake",
                external_id="1",
                url="https://fake.com/job/1",
                title="Python Dev",
                company="Acme",
                location="Remote",
                description="Python role",
            )
        ]

    async def get_job_detail(self, url: str) -> RawJob:
        return RawJob(
            portal_id="fake",
            external_id="1",
            url=url,
            title="Python Dev",
            company="Acme",
            location="Remote",
            description="Python role",
        )


def test_registry_register_and_get():
    registry = PortalRegistry()
    adapter = FakeAdapter()
    registry.register(adapter)
    assert registry.get("fake") is adapter
    assert adapter in registry.all()


def test_registry_get_unknown_raises():
    registry = PortalRegistry()
    with pytest.raises(KeyError):
        registry.get("nonexistent")


async def test_adapter_search_jobs():
    adapter = FakeAdapter()
    query = JobQuery(keywords="Python", location="Remote")
    results = await adapter.search_jobs(query)
    assert len(results) == 1
    assert results[0].title == "Python Dev"
    assert results[0].portal_id == "fake"


from jobplatform.jobs.portals.naukri import NaukriAdapter
from jobplatform.jobs.portals.linkedin import LinkedInAdapter
from jobplatform.jobs.portals.indeed import IndeedAdapter
from jobplatform.jobs.portals.wellfound import WellFoundAdapter
from jobplatform.jobs.portals.registry import portal_registry


def test_all_adapters_registered():
    """Importing portals package registers all 4 adapters."""
    import jobplatform.jobs.portals  # noqa: F401
    assert portal_registry.get("naukri") is not None
    assert portal_registry.get("linkedin") is not None
    assert portal_registry.get("indeed") is not None
    assert portal_registry.get("wellfound") is not None


async def test_naukri_adapter_parses_response():
    fake_response = {
        "jobDetails": [
            {
                "jobId": "nk-001",
                "title": "Python Backend Engineer",
                "companyName": "TechCorp",
                "placeholders": [{"label": "location", "title": "Bengaluru"}],
                "jdURL": "/job-listings/python-backend-engineer-techcorp-bengaluru-1-to-3-years-nk-001",
                "jobDescription": "We need Python skills.",
                "salaryDetail": {"minimumSalary": 800000, "maximumSalary": 1500000},
            }
        ]
    }
    adapter = NaukriAdapter()
    with patch.object(adapter._client, "get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = fake_response
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp
        results = await adapter.search_jobs(JobQuery(keywords="Python", location="Bengaluru"))
    assert len(results) == 1
    assert results[0].title == "Python Backend Engineer"
    assert results[0].company == "TechCorp"
    assert results[0].portal_id == "naukri"
    assert results[0].salary_min == 800000


async def test_adapter_http_error_returns_empty():
    """HTTP error during scrape returns empty list, does not raise."""
    adapter = NaukriAdapter()
    with patch.object(adapter._client, "get", new_callable=AsyncMock, side_effect=httpx.HTTPError("timeout")):
        results = await adapter.search_jobs(JobQuery(keywords="Python", location="Bengaluru"))
    assert results == []
