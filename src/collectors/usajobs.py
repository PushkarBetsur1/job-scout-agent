"""Optional: federal jobs open to recent graduates. Requires a free key from developer.usajobs.gov."""
import os

from .base import SESSION, TIMEOUT, Job, iso_date, log

DEFAULT_QUERIES = ["electrical engineer", "computer engineer", "electronics engineer", "embedded"]


def collect(company: dict, settings: dict):
    key, email = os.environ.get("USAJOBS_API_KEY"), os.environ.get("USAJOBS_EMAIL")
    if not key or not email:
        log.info("USAJOBS skipped (USAJOBS_API_KEY/USAJOBS_EMAIL not set)")
        return
    headers = {"Host": "data.usajobs.gov", "User-Agent": email, "Authorization-Key": key}
    for query in company.get("queries", DEFAULT_QUERIES):
        r = SESSION.get(
            "https://data.usajobs.gov/api/search",
            params={"Keyword": query, "HiringPath": company.get("hiring_path", "graduates"),
                    "ResultsPerPage": 250, "DatePosted": settings["max_age_days"]},
            headers=headers,
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        for item in (r.json().get("SearchResult") or {}).get("SearchResultItems") or []:
            d = item.get("MatchedObjectDescriptor") or {}
            details = (d.get("UserArea") or {}).get("Details") or {}
            yield Job(
                source="usajobs",
                company=d.get("OrganizationName", "US Government"),
                native_id=str(d.get("PositionID") or item.get("MatchedObjectId")),
                title=d.get("PositionTitle", ""),
                url=d.get("PositionURI", ""),
                location=d.get("PositionLocationDisplay", ""),
                posted_at=iso_date(d.get("PublicationStartDate")),
                description="\n\n".join(filter(None, [details.get("JobSummary"), d.get("QualificationSummary")])),
                early_hint=True,
            )
