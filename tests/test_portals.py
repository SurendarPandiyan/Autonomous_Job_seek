import pytest

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
