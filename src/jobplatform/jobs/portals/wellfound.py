import structlog
import httpx

from jobplatform.jobs.portals.base import BasePortalAdapter, JobQuery, RawJob

logger = structlog.get_logger()

_SEARCH_URL = "https://wellfound.com/jobs"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
}


class WellFoundAdapter(BasePortalAdapter):
    portal_id = "wellfound"
    supports_auto_apply = False

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(headers=_HEADERS, timeout=30.0, follow_redirects=True)

    async def search_jobs(self, query: JobQuery) -> list[RawJob]:
        params = {"q": query.keywords, "location": query.location}
        try:
            resp = await self._client.get(_SEARCH_URL, params=params)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("wellfound.search_failed", error=str(exc))
            return []
        return self._parse_html(resp.text)

    def _parse_html(self, html: str) -> list[RawJob]:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        jobs = []
        for card in soup.select("div[data-test='StartupResult']"):
            title_el = card.select_one("a[data-test='startup-link'] span")
            company_el = card.select_one("span[data-test='startup-name']")
            link_el = card.select_one("a[data-test='startup-link']")
            if not title_el:
                continue
            href = link_el.get("href", "") if link_el else ""
            url = f"https://wellfound.com{href}" if href.startswith("/") else href
            jobs.append(RawJob(
                portal_id="wellfound",
                external_id=href.strip("/").split("/")[-1],
                url=url,
                title=title_el.get_text(strip=True),
                company=company_el.get_text(strip=True) if company_el else "",
                location=query.location,
            ))
        return jobs

    async def get_job_detail(self, url: str) -> RawJob:
        return RawJob(portal_id="wellfound", external_id="", url=url, title="", company="", location="")
