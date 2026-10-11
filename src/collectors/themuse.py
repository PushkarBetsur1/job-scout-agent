from .base import SESSION, TIMEOUT, Job, html_to_text, iso_date

URL = "https://www.themuse.com/api/public/jobs"


def collect(company: dict, settings: dict):
    for category in company.get("categories", ["Science and Engineering", "Software Engineering"]):
        for page in range(company.get("max_pages", 5)):
            r = SESSION.get(
                URL,
                params={"category": category, "level": company.get("levels", ["Entry Level"]), "page": page, "descending": "true"},
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            for j in data.get("results") or []:
                yield Job(
                    source="themuse",
                    company=(j.get("company") or {}).get("name", ""),
                    native_id=str(j["id"]),
                    title=j.get("name", ""),
                    url=(j.get("refs") or {}).get("landing_page", ""),
                    location="; ".join(loc.get("name", "") for loc in j.get("locations") or []),
                    posted_at=iso_date(j.get("publication_date")),
                    description=html_to_text(j.get("contents")),
                )
            if page + 1 >= data.get("page_count", 0):
                break
