from .base import SESSION, TIMEOUT, Job, html_to_text, iso_date


def collect(company: dict, settings: dict):
    r = SESSION.get(f"https://api.lever.co/v0/postings/{company['token']}", params={"mode": "json"}, timeout=TIMEOUT)
    r.raise_for_status()
    for j in r.json():
        sections = [f"{s.get('text', '')}\n{html_to_text(s.get('content'))}" for s in j.get("lists") or []]
        description = "\n\n".join([j.get("descriptionPlain") or "", *sections, j.get("additionalPlain") or ""])
        yield Job(
            source="lever",
            company=company["name"],
            native_id=j["id"],
            title=j.get("text", ""),
            url=j.get("hostedUrl", ""),
            location=(j.get("categories") or {}).get("location", ""),
            posted_at=iso_date(j.get("createdAt")),
            description=description.strip(),
            semiconductor=company.get("semiconductor", False),
        )
