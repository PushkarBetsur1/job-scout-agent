from .base import SESSION, TIMEOUT, Job, html_to_text, iso_date


def collect(company: dict, settings: dict):
    r = SESSION.get(
        f"https://boards-api.greenhouse.io/v1/boards/{company['token']}/jobs",
        params={"content": "true"},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    for j in r.json().get("jobs", []):
        yield Job(
            source="greenhouse",
            company=company["name"],
            native_id=str(j["id"]),
            title=j.get("title", ""),
            url=j.get("absolute_url", ""),
            location=(j.get("location") or {}).get("name", ""),
            posted_at=iso_date(j.get("first_published") or j.get("updated_at")),
            description=html_to_text(j.get("content")),
            semiconductor=company.get("semiconductor", False),
        )
