import re
from datetime import date, timedelta

from .base import SESSION, TIMEOUT, Job, html_to_text

PAGE_SIZE = 20  # Workday's maximum


def _posted(text: str | None) -> str | None:
    t = (text or "").lower()
    today = date.today()
    if "today" in t:
        return today.isoformat()
    if "yesterday" in t:
        return (today - timedelta(days=1)).isoformat()
    m = re.search(r"(\d+)\+?\s*days", t)
    return (today - timedelta(days=int(m.group(1)))).isoformat() if m else None


def _load_details(job: Job, url: str) -> None:
    r = SESSION.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    info = r.json().get("jobPostingInfo", {})
    job.description = html_to_text(info.get("jobDescription"))
    locations = [info.get("location")] + (info.get("additionalLocations") or [])
    job.location = "; ".join(loc for loc in locations if loc) or job.location


def collect(company: dict, settings: dict):
    host, tenant, site = company["host"], company["tenant"], company["site"]
    base = f"https://{host}.myworkdayjobs.com"
    api = f"{base}/wday/cxs/{tenant}/{site}"
    terms = company.get("search_terms") or settings["workday_search_terms"]
    max_pages = settings.get("workday_max_pages", 2)
    seen: set[str] = set()

    for term in terms:
        total = 0
        for page in range(max_pages):
            r = SESSION.post(
                f"{api}/jobs",
                json={"appliedFacets": {}, "limit": PAGE_SIZE, "offset": page * PAGE_SIZE, "searchText": term},
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            if page == 0:
                total = data.get("total", 0)  # only reported on the first page
            postings = data.get("jobPostings") or []
            for p in postings:
                path = p.get("externalPath")
                if not path or path in seen:
                    continue
                seen.add(path)
                yield Job(
                    source="workday",
                    company=company["name"],
                    native_id=(p.get("bulletFields") or [path])[0],
                    title=p.get("title", ""),
                    url=f"{base}/{site}{path}",
                    location=p.get("locationsText", ""),
                    posted_at=_posted(p.get("postedOn")),
                    semiconductor=company.get("semiconductor", False),
                    details_loader=lambda job, u=f"{api}{path}": _load_details(job, u),
                )
            if len(postings) < PAGE_SIZE or (page + 1) * PAGE_SIZE >= total:
                break
