"""Parses job tables from GitHub new-grad list READMEs (speedyapply, jobright, zapply, ...)."""
import hashlib
import re
from datetime import date, datetime, timedelta

from bs4 import BeautifulSoup

from .base import SESSION, TIMEOUT, Job
from .details import load_from_url

LINK = re.compile(r'href="(https?://[^"]+)"|\]\((https?://[^)\s]+)\)')
MD_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
AGE = re.compile(r"(\d+)\s*(mo|m|h|d|w)", re.I)
COLUMNS = {
    "company": ("company",),
    "title": ("role", "position", "title"),
    "location": ("location",),
    "date": ("age", "posted", "date"),
}


def _text(cell: str) -> str:
    cell = MD_LINK.sub(r"\1", cell)
    text = BeautifulSoup(cell, "html.parser").get_text(" ")
    return " ".join(text.replace("*", "").split())


def _date(text: str) -> str | None:
    t = text.strip().lower()
    today = date.today()
    if m := AGE.fullmatch(t):
        n, unit = int(m[1]), m[2]
        days = {"m": 0, "h": 0, "d": n, "w": 7 * n, "mo": 30 * n}[unit]
        return (today - timedelta(days=days)).isoformat()
    try:
        d = datetime.strptime(f"{text.strip()} {today.year}", "%b %d %Y").date()
    except ValueError:
        return None
    return (d.replace(year=d.year - 1) if d > today else d).isoformat()


def _header_map(cells: list[str]) -> dict[str, int]:
    mapping = {}
    for i, cell in enumerate(cells):
        name = _text(cell).lower()
        for key, words in COLUMNS.items():
            if key not in mapping and any(w in name for w in words):
                mapping[key] = i
    return mapping


def collect(company: dict, settings: dict):
    r = SESSION.get(company["url"], timeout=TIMEOUT)
    r.raise_for_status()
    lines = r.text.splitlines()
    header: dict[str, int] | None = None
    last_company = ""
    for i, line in enumerate(lines):
        if not line.startswith("|"):
            header = None
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if i + 1 < len(lines) and re.match(r"^\|\s*:?-{3,}", lines[i + 1]):
            header = _header_map(cells)
            continue
        if header is None or "title" not in header or re.match(r"^:?-{3,}", cells[0]):
            continue
        links = [a or b for a, b in LINK.findall(line)]
        if not links or len(cells) <= max(header.values()):
            continue
        name = _text(cells[header["company"]]) if "company" in header else company["name"]
        if name in ("↳", ""):
            name = last_company
        last_company = name
        url = links[-1]
        yield Job(
            source="readme",
            company=name,
            native_id=hashlib.sha1(url.encode()).hexdigest()[:16],
            title=_text(cells[header["title"]]),
            url=url,
            location=_text(cells[header["location"]]) if "location" in header else "",
            posted_at=_date(_text(cells[header["date"]])) if "date" in header else None,
            early_hint=True,
            details_loader=load_from_url,
        )
