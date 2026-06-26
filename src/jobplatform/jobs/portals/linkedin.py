import structlog
import httpx

from jobplatform.jobs.portals.base import BasePortalAdapter, JobQuery, RawJob

logger = structlog.get_logger()

_SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
}


class LinkedInAdapter(BasePortalAdapter):
    portal_id = "linkedin"
    supports_auto_apply = False

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(headers=_HEADERS, timeout=30.0)

    async def search_jobs(self, query: JobQuery) -> list[RawJob]:
        params = {
            "keywords": query.keywords,
            "location": query.location,
            "start": 0,
            "count": min(query.max_results, 25),
        }
        try:
            resp = await self._client.get(_SEARCH_URL, params=params)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("linkedin.search_failed", error=str(exc))
            return []
        return self._parse_html(resp.text, query)

    def _parse_html(self, html: str, query: JobQuery) -> list[RawJob]:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        jobs = []
        for card in soup.select("li"):
            title_el = card.select_one(".base-search-card__title")
            company_el = card.select_one(".base-search-card__subtitle")
            location_el = card.select_one(".job-search-card__location")
            link_el = card.select_one("a.base-card__full-link")
            if not title_el or not link_el:
                continue
            url = link_el.get("href", "")
            external_id = url.split("?")[0].rstrip("/").split("-")[-1] if url else ""
            jobs.append(RawJob(
                portal_id="linkedin",
                external_id=external_id,
                url=url,
                title=title_el.get_text(strip=True),
                company=company_el.get_text(strip=True) if company_el else "",
                location=location_el.get_text(strip=True) if location_el else query.location,
            ))
        return jobs

    async def get_job_detail(self, url: str) -> RawJob:
        return RawJob(portal_id="linkedin", external_id="", url=url, title="", company="", location="")
