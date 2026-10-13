import argparse
import logging
import os
import re
import time as time_module
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
import yaml

from . import filters, notifier
from .collectors import COLLECTORS
from .database import Database
from .resume_matcher import PROVIDERS, load_resume, score_job

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger("job-scout")


def _is_instant_alert_company(company: str, settings: dict) -> bool:
    normalize = lambda value: re.sub(r"[^a-z0-9]", "", value.lower())
    target = normalize(company)
    return target in {normalize(name) for name in settings.get("instant_alert_companies", [])}


def _collect_one(company: dict, settings: dict) -> list:
    collect = COLLECTORS.get(company.get("ats"))
    if collect is None:
        log.warning("Unknown ats %r for %s", company.get("ats"), company.get("name"))
        return []
    try:
        jobs = list(collect(company, settings))
    except Exception as exc:
        log.warning("%s (%s) failed: %s", company["name"], company["ats"], exc)
        return []
    log.info("%-32s %5d postings", company["name"], len(jobs))
    return jobs


def collect_all(cfg: dict):
    settings = cfg["settings"]
    with ThreadPoolExecutor(settings.get("collector_workers", 8)) as pool:
        for jobs in pool.map(lambda c: _collect_one(c, settings), cfg["companies"]):
            yield from jobs


def scan(cfg: dict, db: Database) -> None:
    s = cfg["settings"]
    cutoff = (date.today() - timedelta(days=s["max_age_days"])).isoformat()
    counts = {"pending": 0, "filtered": 0, "duplicate": 0}
    candidates, seen_ids, seen_keys = [], set(), set()
    for job in collect_all(cfg):
        if (job.posted_at and job.posted_at < cutoff) or job.id in seen_ids or db.has_job(job.id):
            continue
        seen_ids.add(job.id)
        if job.dedupe_key in seen_keys or db.has_dedupe_key(job.dedupe_key):
            db.add_job(job, "duplicate")
            counts["duplicate"] += 1
            continue
        seen_keys.add(job.dedupe_key)
        candidates.append(job)

    # evaluate() may fetch job descriptions over the network
    with ThreadPoolExecutor(s.get("detail_workers", 12)) as pool:
        results = list(pool.map(filters.evaluate, candidates))
    for job, (ok, reason, path) in zip(candidates, results):
        status = "pending" if ok else "filtered"
        db.add_job(job, status, reason, path)
        counts[status] += 1
    db.prune()
    db.commit()
    log.info("New postings: %s", counts)
    score_pending(cfg, db)


def score_pending(cfg: dict, db: Database) -> None:
    s = cfg["settings"]
    jobs = db.pending(s["max_llm_jobs_per_run"])
    if not jobs:
        return
    provider = os.environ.get("LLM_PROVIDER") or s["llm_provider"]
    base_url, key_env = PROVIDERS[provider]
    api_key = os.environ.get(key_env)
    if not api_key:
        log.error("%s is not set; %d jobs left pending", key_env, len(jobs))
        return

    resume = load_resume(ROOT / s["resume_path"])
    model = os.environ.get("LLM_MODEL") or s["llm_model"]
    pause = s.get("llm_min_seconds_between_calls", 0)
    priority_instant: list[str] = []
    instant: list[str] = []
    for i, job in enumerate(jobs):
        if i and pause:
            time_module.sleep(pause)
        try:
            result = score_job(job, resume, s["preferences"], model, base_url, api_key)
        except requests.HTTPError as exc:
            code = exc.response.status_code if exc.response is not None else None
            if code in (401, 403):
                log.error("%s rejected the API key: %s", provider, exc)
                break
            if code == 429:
                log.warning("%s rate limit reached; remaining jobs will be scored next run", provider)
                break
            log.warning("Scoring failed for %s: %s", job["url"], exc)
            db.record_score_failure(job["id"])
            continue
        except Exception as exc:
            log.warning("Scoring failed for %s: %s", job["url"], exc)
            db.record_score_failure(job["id"])
            continue

        db.save_score(job["id"], result)
        log.info("%3d  %s — %s", result["score"], job["company"], job["title"])
        digest_min = s["degree_match_threshold"] if job["match_path"] == "degree" else s["digest_threshold"]
        if result["eligible"] and _is_instant_alert_company(job["company"], s):
            priority_instant.append(job["id"])
        elif result["score"] >= s["instant_threshold"]:
            instant.append(job["id"])
        elif result["score"] >= digest_min:
            db.queue_for_digest([job["id"]])
        db.commit()

    cap = s["max_instant_alerts_per_run"]
    for job_id in priority_instant + instant[:cap]:
        try:
            job = db.get(job_id)
            job["priority_alert"] = job_id in priority_instant
            notifier.send_instant(job)
            db.mark_alerted(job_id)
        except Exception as exc:
            log.warning("Instant alert failed, moving to digest: %s", exc)
            db.queue_for_digest([job_id])
    db.queue_for_digest(instant[cap:])
    db.commit()


def digest(cfg: dict, db: Database, force: bool = False) -> None:
    s = cfg["settings"]
    tz = ZoneInfo(s["timezone"])
    now = datetime.now(tz)
    slots = [
        datetime.combine(now.date() - timedelta(days=d), time(hour), tzinfo=tz)
        for d in (0, 1)
        for hour in s["digest_hours"]
    ]
    slot = max(x for x in slots if x <= now)
    last = db.get_meta("last_digest_slot")
    if not force and last and datetime.fromisoformat(last) >= slot:
        log.info("Digest for %s already sent", slot)
        return

    jobs = db.digest_queue()
    notifier.send_digest(jobs, f"Job digest · {slot:%b %d, %-I %p %Z}")
    db.mark_digested([j["id"] for j in jobs])
    db.set_meta("last_digest_slot", slot.isoformat())
    db.commit()
    log.info("Digest sent with %d jobs", len(jobs))


def main() -> None:
    parser = argparse.ArgumentParser(description="New-grad hardware/embedded job scout")
    parser.add_argument("command", choices=["scan", "digest", "test-notify"])
    parser.add_argument("--config", default=str(ROOT / "config" / "companies.yaml"))
    parser.add_argument("--db", default=os.environ.get("JOB_DB_PATH", str(ROOT / "data" / "jobs.db")))
    parser.add_argument("--force", action="store_true", help="send the digest even if this slot was already sent")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    if args.command == "test-notify":
        notifier.send("<b>Job Scout</b> is connected. You'll get alerts here.")
        return

    db = Database(Path(args.db))
    if args.command == "scan":
        scan(cfg, db)
    else:
        digest(cfg, db, force=args.force)


if __name__ == "__main__":
    main()
