from .base import SESSION, TIMEOUT, Job, html_to_text, iso_date


def collect(company: dict, settings: dict):
    r = SESSION.get(f"https://api.ashbyhq.com/posting-api/job-board/{company['token']}", timeout=TIMEOUT)
    r.raise_for_status()
    for j in r.json().get("jobs", []):
        if j.get("isListed") is False:
            continue
        locations = [j.get("location")] + [s.get("location") for s in j.get("secondaryLocations") or []]
        yield Job(
            source="ashby",
            company=company["name"],
            native_id=j["id"],
            title=j.get("title", ""),
            url=j.get("jobUrl", ""),
            location="; ".join(loc for loc in locations if loc),
            posted_at=iso_date(j.get("publishedAt")),
            description=j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml")),
            semiconductor=company.get("semiconductor", False),
        )
