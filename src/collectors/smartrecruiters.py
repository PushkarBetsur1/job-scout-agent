from .base import SESSION, TIMEOUT, Job, html_to_text, iso_date

API = "https://api.smartrecruiters.com/v1/companies/{co}/postings"
SKIP_LEVELS = {"mid_senior_level", "director", "executive"}


def posting_text(co: str, posting_id: str) -> str:
    r = SESSION.get(f"{API.format(co=co)}/{posting_id}", timeout=TIMEOUT)
    r.raise_for_status()
    sections = (r.json().get("jobAd") or {}).get("sections") or {}
    keys = ("jobDescription", "qualifications", "additionalInformation")
    return "\n\n".join(html_to_text(sections[k].get("text")) for k in keys if sections.get(k))


def _location(loc: dict) -> str:
    parts = [loc.get("city"), loc.get("region"), (loc.get("country") or "").upper()]
    text = ", ".join(p for p in parts if p)
    return f"{text} (Remote)" if loc.get("remote") else text


def collect(company: dict, settings: dict):
    co = company["token"]
    max_postings = company.get("max_postings", 1000)
    offset = 0
    while offset < max_postings:
        params = {"limit": 100, "offset": offset}
        if company.get("country", "us"):
            params["country"] = company.get("country", "us")
        r = SESSION.get(API.format(co=co), params=params, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        content = data.get("content") or []
        for p in content:
            if (p.get("experienceLevel") or {}).get("id") in SKIP_LEVELS:
                continue
            yield Job(
                source="smartrecruiters",
                company=company["name"],
                native_id=str(p["id"]),
                title=p.get("name", ""),
                url=f"https://jobs.smartrecruiters.com/{co}/{p['id']}",
                location=_location(p.get("location") or {}),
                posted_at=iso_date(p.get("releasedDate")),
                semiconductor=company.get("semiconductor", False),
                details_loader=lambda job, pid=str(p["id"]): setattr(job, "description", posting_text(co, pid)),
            )
        offset += len(content)
        if not content or offset >= data.get("totalFound", 0):
            break
