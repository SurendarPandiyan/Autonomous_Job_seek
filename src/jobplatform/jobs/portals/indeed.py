import structlog
import httpx

from jobplatform.jobs.portals.base import BasePortalAdapter, JobQuery, RawJob

logger = structlog.get_logger()

_SEARCH_URL = "https://indeed.com/jobs"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept-Language": "en-IN,en;q=0.9",
}


class IndeedAdapter(BasePortalAdapter):
    portal_id = "indeed"
    supports_auto_apply = False

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(headers=_HEADERS, timeout=30.0, follow_redirects=True)

    async def search_jobs(self, query: JobQuery) -> list[RawJob]:
        params = {"q": query.keywords, "l": query.location, "limit": min(query.max_results, 15)}
        try:
            resp = await self._client.get(_SEARCH_URL, params=params)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("indeed.search_failed", error=str(exc))
            return []
        return self._parse_html(resp.text)

    def _parse_html(self, html: str) -> list[RawJob]:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        jobs = []
        for card in soup.select("div.job_seen_beacon"):
            title_el = card.select_one("h2.jobTitle span")
            company_el = card.select_one("[data-testid='company-name']")
            location_el = card.select_one("[data-testid='text-location']")
            link_el = card.select_one("h2.jobTitle a")
            if not title_el:
                continue
            href = link_el.get("href", "") if link_el else ""
            url = f"https://indeed.com{href}" if href.startswith("/") else href
            jobs.append(RawJob(
                portal_id="indeed",
                external_id=href.split("jk=")[-1].split("&")[0] if "jk=" in href else href,
                url=url,
                title=title_el.get_text(strip=True),
                company=company_el.get_text(strip=True) if company_el else "",
                location=location_el.get_text(strip=True) if location_el else "",
            ))
        return jobs

    async def get_job_detail(self, url: str) -> RawJob:
        return RawJob(portal_id="indeed", external_id="", url=url, title="", company="", location="")
