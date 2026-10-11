"""Career sites built on iCIMS Jibe (e.g. careers.amd.com) expose /api/jobs."""
from .base import SESSION, TIMEOUT, Job, html_to_text, iso_date

PAGE_SIZE = 100


def collect(company: dict, settings: dict):
    base = company["base_url"].rstrip("/")
    countries = set(company.get("countries") or [])
    seen: set[str] = set()
    for keyword in company.get("search_terms") or settings["workday_search_terms"]:
        for page in range(1, company.get("max_pages", 2) + 1):
            r = SESSION.get(
                f"{base}/api/jobs",
                params={"keywords": keyword, "page": page, "limit": PAGE_SIZE, "sortBy": "posted_date", "descending": "true"},
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            items = r.json().get("jobs") or []
            for item in items:
                d = item.get("data") or {}
                req_id = str(d.get("req_id") or d.get("slug"))
                if req_id in seen or (countries and d.get("country_code") not in countries):
                    continue
                seen.add(req_id)
                parts = (d.get("description"), d.get("responsibilities"), d.get("qualifications"))
                yield Job(
                    source="jibe",
                    company=company["name"],
                    native_id=req_id,
                    title=d.get("title", ""),
                    url=f"{base}/careers-home/jobs/{req_id}",
                    location=d.get("full_location") or d.get("location_name", ""),
                    posted_at=iso_date((d.get("posted_date") or "").replace("+0000", "+00:00")),
                    description="\n\n".join(html_to_text(p) for p in parts if p),
                    semiconductor=company.get("semiconductor", False),
                )
            if len(items) < PAGE_SIZE:
                break
