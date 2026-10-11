"""Fetches a job description from a posting URL, using ATS APIs when the URL is recognized."""
import re
from functools import lru_cache

from bs4 import BeautifulSoup

from .base import SESSION, TIMEOUT, Job, html_to_text
from .smartrecruiters import posting_text

WORKDAY = re.compile(
    r"https://(?P<tenant>[\w-]+)\.(?P<wd>wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?(?P<site>[^/?#]+)(?P<path>/job/[^?#]+)"
)
GREENHOUSE = re.compile(r"https://(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/(?P<token>[^/?#]+)/jobs/(?P<id>\d+)")
LEVER = re.compile(r"https://jobs\.lever\.co/(?P<co>[^/?#]+)/(?P<id>[0-9a-f-]{36})")
ASHBY = re.compile(r"https://jobs\.ashbyhq\.com/(?P<co>[^/?#]+)/(?P<id>[0-9a-f-]{36})")
SMARTRECRUITERS = re.compile(r"https://(?:jobs|careers)\.smartrecruiters\.com/(?P<co>[^/?#]+)/(?P<id>\d+)")
MAX_CHARS = 20000


@lru_cache(maxsize=128)
def _ashby_board(co: str) -> tuple:
    r = SESSION.get(f"https://api.ashbyhq.com/posting-api/job-board/{co}", timeout=TIMEOUT)
    r.raise_for_status()
    return tuple(r.json().get("jobs") or [])


def _from_api(url: str) -> str | None:
    if m := WORKDAY.match(url):
        api = f"https://{m['tenant']}.{m['wd']}.myworkdayjobs.com/wday/cxs/{m['tenant']}/{m['site']}{m['path']}"
        r = SESSION.get(api, timeout=TIMEOUT)
        r.raise_for_status()
        return html_to_text((r.json().get("jobPostingInfo") or {}).get("jobDescription"))
    if m := GREENHOUSE.match(url):
        r = SESSION.get(f"https://boards-api.greenhouse.io/v1/boards/{m['token']}/jobs/{m['id']}", timeout=TIMEOUT)
        r.raise_for_status()
        return html_to_text(r.json().get("content"))
    if m := LEVER.match(url):
        r = SESSION.get(f"https://api.lever.co/v0/postings/{m['co']}/{m['id']}", timeout=TIMEOUT)
        r.raise_for_status()
        j = r.json()
        lists = [f"{s.get('text', '')}\n{html_to_text(s.get('content'))}" for s in j.get("lists") or []]
        return "\n\n".join([j.get("descriptionPlain") or "", *lists])
    if m := ASHBY.match(url):
        job = next((j for j in _ashby_board(m["co"]) if j.get("id") == m["id"]), {})
        return job.get("descriptionPlain") or html_to_text(job.get("descriptionHtml"))
    if m := SMARTRECRUITERS.match(url):
        return posting_text(m["co"], m["id"])
    return None


def fetch_description(url: str) -> str:
    if not url.startswith("https://"):
        return ""
    text = _from_api(url)
    if text is not None:
        return text[:MAX_CHARS]
    r = SESSION.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    if r.url != url and (text := _from_api(r.url)) is not None:
        return text[:MAX_CHARS]
    if "html" not in r.headers.get("content-type", ""):
        return ""
    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "svg"]):
        tag.decompose()
    text = re.sub(r"\n\s*\n+", "\n\n", soup.get_text("\n")).strip()
    return text[:MAX_CHARS]


def load_from_url(job: Job) -> None:
    job.description = fetch_description(job.url)
