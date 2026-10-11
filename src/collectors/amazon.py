from datetime import datetime

from .base import SESSION, TIMEOUT, Job, html_to_text

URL = "https://www.amazon.jobs/en/search.json"
DEFAULT_QUERIES = ["early career", "university", "hardware", "embedded", "firmware", "silicon", "FPGA", "ASIC"]


def _posted(text: str | None) -> str | None:
    try:
        return datetime.strptime(" ".join((text or "").split()), "%B %d, %Y").date().isoformat()
    except ValueError:
        return None


def collect(company: dict, settings: dict):
    seen: set[str] = set()
    for query in company.get("queries", DEFAULT_QUERIES):
        for page in range(company.get("max_pages", 1)):
            params = {
                "base_query": query,
                "result_limit": 100,
                "offset": page * 100,
                "sort": "recent",
                "normalized_country_code[]": company.get("country", "USA"),
            }
            r = SESSION.get(URL, params=params, timeout=TIMEOUT)
            r.raise_for_status()
            jobs = r.json().get("jobs") or []
            for j in jobs:
                job_id = str(j.get("id_icims") or j.get("id"))
                if job_id in seen:
                    continue
                seen.add(job_id)
                sections = ("description", "basic_qualifications", "preferred_qualifications")
                yield Job(
                    source="amazon",
                    company=company.get("name", "Amazon"),
                    native_id=job_id,
                    title=j.get("title", ""),
                    url=f"https://www.amazon.jobs{j.get('job_path', '')}",
                    location=j.get("normalized_location") or j.get("location", ""),
                    posted_at=_posted(j.get("posted_date")),
                    description="\n\n".join(html_to_text(j[k]) for k in sections if j.get(k)),
                    semiconductor=company.get("semiconductor", False),
                )
            if len(jobs) < 100:
                break
