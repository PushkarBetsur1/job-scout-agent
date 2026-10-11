import html
import os

from .collectors.base import make_session

TELEGRAM_URL = "https://api.telegram.org/bot{token}/sendMessage"
MAX_LEN = 3900  # Telegram limit is 4096
SESSION = make_session()


def _e(value) -> str:
    return html.escape(str(value or ""), quote=True)


def _short(value: str, n: int = 90) -> str:
    value = value or ""
    return value if len(value) <= n else value[: n - 1] + "…"


def send(text: str) -> None:
    token, chat_id = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print(f"---- Telegram not configured; message below ----\n{text}\n")
        return
    r = SESSION.post(
        TELEGRAM_URL.format(token=token),
        json={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
        timeout=30,
    )
    r.raise_for_status()


def _tag(job: dict) -> str:
    return " · CompE-degree match" if job.get("match_path") == "degree" else ""


def send_instant(job: dict) -> None:
    lines = [
        "<b>Top match</b>",
        f"<b>{_e(job['title'])}</b>",
        f"{job['score']}% fit{_tag(job)}",
        f"{_e(job['company'])} · {_e(_short(job['location']))}",
    ]
    if job["reasons"]:
        lines += ["", "<b>Why it matches:</b>", *[f"• {_e(r)}" for r in job["reasons"]]]
    if job["missing_skills"]:
        lines += ["", f"<b>Missing:</b> {_e(', '.join(job['missing_skills']))}"]
    lines += ["", f'<a href="{_e(job["url"])}">Apply</a>']
    send("\n".join(lines))


def send_digest(jobs: list[dict], label: str) -> None:
    if not jobs:
        send(f"<b>{_e(label)}</b>\nNo new matches above the digest threshold since the last digest.")
        return
    message = f"<b>{_e(label)}</b> — {len(jobs)} match{'es' if len(jobs) != 1 else ''}\n"
    for i, job in enumerate(jobs, 1):
        block = (
            f"\n{i}. <b>{_e(job['title'])}</b> ({job['score']}%{_tag(job)})\n"
            f"{_e(job['company'])} · {_e(_short(job['location'], 60))}\n"
            + (f"<i>{_e(job['reasons'][0])}</i>\n" if job["reasons"] else "")
            + f'<a href="{_e(job["url"])}">Apply</a>\n'
        )
        if len(message) + len(block) > MAX_LEN:
            send(message)
            message = ""
        message += block
    if message:
        send(message)
