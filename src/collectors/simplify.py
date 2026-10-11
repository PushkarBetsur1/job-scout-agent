from .base import SESSION, TIMEOUT, Job, iso_date
from .details import load_from_url

LISTINGS_URL = "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/.github/scripts/listings.json"


def collect(company: dict, settings: dict):
    r = SESSION.get(company.get("url", LISTINGS_URL), timeout=TIMEOUT)
    r.raise_for_status()
    categories = set(company.get("categories") or [])
    for j in r.json():
        if not j.get("active") or not j.get("is_visible", True):
            continue
        if categories and j.get("category") not in categories:
            continue
        yield Job(
            source="simplify",
            company=j.get("company_name", ""),
            native_id=j["id"],
            title=j.get("title", ""),
            url=j.get("url", ""),
            location="; ".join(j.get("locations") or []),
            posted_at=iso_date(j.get("date_posted")),
            early_hint=True,
            details_loader=load_from_url,
        )
