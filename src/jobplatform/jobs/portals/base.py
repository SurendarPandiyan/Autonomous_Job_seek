from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class JobQuery:
    keywords: str
    location: str
    max_results: int = 50
    experience_years_min: int | None = None
    experience_years_max: int | None = None
    salary_min: int | None = None


@dataclass
class RawJob:
    portal_id: str
    external_id: str
    url: str
    title: str
    company: str
    location: str
    description: str | None = None
    requirements: dict | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    employment_type: str | None = None
    posted_at: datetime | None = None
    raw_data: dict | None = None


class BasePortalAdapter(ABC):
    portal_id: str
    supports_auto_apply: bool = False

    @abstractmethod
    async def search_jobs(self, query: JobQuery) -> list[RawJob]:
        """Search and return raw job listings."""

    @abstractmethod
    async def get_job_detail(self, url: str) -> RawJob:
        """Fetch full job detail for a given URL."""
