from datetime import date, timedelta

from .base import SESSION, TIMEOUT, Job, html_to_text, iso_date

SEARCH_URL = "https://{host}/api/pcsx/search"
DETAIL_URL = "https://{host}/api/pcsx/position_details"


def _load_details(job: Job, host: str, domain: str) -> None:
    r = SESSION.get(
        DETAIL_URL.format(host=host),
        params={"position_id": job.native_id, "domain": domain, "hl": "en"},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    job.description = html_to_text((r.json().get("data") or {}).get("jobDescription"))


def collect(company: dict, settings: dict):
    host, domain = company["host"], company["domain"]
    cutoff = (date.today() - timedelta(days=settings["max_age_days"])).isoformat()
    page_size = 10
    max_pages = company.get("max_pages", 25)

    for page in range(max_pages):
        r = SESSION.get(
            SEARCH_URL.format(host=host),
            params={
                "domain": domain,
                "query": "",
                "location": "",
                "start": page * page_size,
                "sort_by": "timestamp",
            },
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json().get("data") or {}
        positions = data.get("positions") or []
        if not positions:
            break

        reached_cutoff = False
        for position in positions:
            posted_at = iso_date(position.get("postedTs"))
            if posted_at and posted_at < cutoff:
                reached_cutoff = True
                continue
            location = position.get("standardizedLocations") or position.get("locations") or []
            yield Job(
                source="eightfold",
                company=company["name"],
                native_id=str(position["id"]),
                title=position.get("name", ""),
                url=f"https://{host}{position.get('positionUrl', '')}",
                location="; ".join(location),
                posted_at=posted_at,
                semiconductor=company.get("semiconductor", False),
                details_loader=lambda job, h=host, d=domain: _load_details(job, h, d),
            )

        if reached_cutoff or (page + 1) * page_size >= data.get("count", 0):
            break