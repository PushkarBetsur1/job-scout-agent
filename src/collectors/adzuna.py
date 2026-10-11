"""Optional: requires free API credentials (developer.adzuna.com)."""
import os

from .base import SESSION, TIMEOUT, Job, iso_date, log

DEFAULT_QUERIES = ["new grad hardware engineer", "entry level embedded engineer", "new grad firmware engineer",
                   "entry level electrical engineer", "new grad computer engineer", "entry level FPGA engineer"]


def collect(company: dict, settings: dict):
    app_id, app_key = os.environ.get("ADZUNA_APP_ID"), os.environ.get("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        log.info("Adzuna skipped (ADZUNA_APP_ID/ADZUNA_APP_KEY not set)")
        return
    for query in company.get("queries", DEFAULT_QUERIES):
        for page in range(1, company.get("max_pages", 2) + 1):
            r = SESSION.get(
                f"https://api.adzuna.com/v1/api/jobs/{company.get('country', 'us')}/search/{page}",
                params={"app_id": app_id, "app_key": app_key, "what": query, "results_per_page": 50,
                        "max_days_old": settings["max_age_days"], "sort_by": "date"},
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            results = r.json().get("results") or []
            for j in results:
                yield Job(
                    source="adzuna",
                    company=(j.get("company") or {}).get("display_name", ""),
                    native_id=str(j["id"]),
                    title=j.get("title", ""),
                    url=j.get("redirect_url", ""),
                    location=(j.get("location") or {}).get("display_name", ""),
                    posted_at=iso_date(j.get("created")),
                    description=j.get("description", ""),
                )
            if len(results) < 50:
                break
