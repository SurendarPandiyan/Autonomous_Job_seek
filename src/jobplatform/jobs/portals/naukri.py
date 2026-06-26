import structlog
import httpx

from jobplatform.jobs.portals.base import BasePortalAdapter, JobQuery, RawJob

logger = structlog.get_logger()

_NAUKRI_SEARCH_URL = "https://www.naukri.com/jobapi/v3/search"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
    "Appid": "109",
    "Systemid": "109",
}


class NaukriAdapter(BasePortalAdapter):
    portal_id = "naukri"
    supports_auto_apply = False

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(headers=_HEADERS, timeout=30.0)

    async def search_jobs(self, query: JobQuery) -> list[RawJob]:
        params = {
            "noOfResults": min(query.max_results, 20),
            "urlType": "search_by_keyword",
            "searchType": "adv",
            "keyword": query.keywords,
            "location": query.location,
            "experience": query.experience_years_min or 0,
        }
        try:
            resp = await self._client.get(_NAUKRI_SEARCH_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("naukri.search_failed", error=str(exc))
            return []
        return [self._parse(item) for item in data.get("jobDetails", [])]

    def _parse(self, item: dict) -> RawJob:
        location = next(
            (p["title"] for p in item.get("placeholders", []) if p.get("label") == "location"),
            "",
        )
        salary = item.get("salaryDetail", {}) or {}
        return RawJob(
            portal_id="naukri",
            external_id=str(item.get("jobId", "")),
            url=f"https://www.naukri.com{item.get('jdURL', '')}",
            title=item.get("title", ""),
            company=item.get("companyName", ""),
            location=location,
            description=item.get("jobDescription"),
            salary_min=salary.get("minimumSalary"),
            salary_max=salary.get("maximumSalary"),
            raw_data=item,
        )

    async def get_job_detail(self, url: str) -> RawJob:
        try:
            resp = await self._client.get(url)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("naukri.detail_failed", url=url, error=str(exc))
            raise
        return RawJob(portal_id="naukri", external_id="", url=url, title="", company="", location="")
