from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger("job-scout")
TIMEOUT = 30


def make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers["User-Agent"] = "Mozilla/5.0 (job-scout-agent; personal job search)"
    return session


SESSION = make_session()


def html_to_text(raw: str | None) -> str:
    if not raw:
        return ""
    text = BeautifulSoup(html.unescape(raw), "html.parser").get_text("\n")
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def iso_date(value) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        if value > 1e12:  # milliseconds
            value /= 1000
        return datetime.fromtimestamp(value, timezone.utc).date().isoformat()
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


@dataclass
class Job:
    source: str
    company: str
    native_id: str
    title: str
    url: str
    location: str = ""
    posted_at: str | None = None
    description: str = ""
    semiconductor: bool = False
    early_hint: bool = False  # came from a curated new-grad list
    details_loader: Callable[["Job"], None] | None = field(default=None, repr=False)

    @property
    def id(self) -> str:
        return f"{self.source}:{slug(self.company)}:{self.native_id}"

    @property
    def dedupe_key(self) -> str:
        return f"{slug(self.company)}|{slug(self.title)}"

    def ensure_details(self) -> None:
        if self.details_loader is None:
            return
        loader, self.details_loader = self.details_loader, None
        try:
            loader(self)
        except Exception as exc:
            log.warning("Could not load details for %s: %s", self.url, exc)
