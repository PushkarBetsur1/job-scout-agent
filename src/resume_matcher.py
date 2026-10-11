import json
import os
import re
from pathlib import Path

from pypdf import PdfReader

from .collectors.base import make_session

# provider -> (OpenAI-compatible base URL, env var holding the API key)
PROVIDERS = {
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY"),
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY"),
}
WEIGHTS = {
    "skills": 0.30,
    "experience_relevance": 0.25,
    "role_alignment": 0.20,
    "eligibility": 0.15,
    "location": 0.10,
}
SESSION = make_session()

SYSTEM_PROMPT = """You are a meticulous technical recruiter for hardware, embedded systems, computer engineering and semiconductor roles.
Evaluate how well the candidate fits the job. Be strict and calibrated: a subscore of 90+ means an excellent, concrete match; 80-89 strong; 60-79 plausible; below 60 weak.

Return ONLY a JSON object with exactly these keys:
{
  "eligible": boolean,
  "eligibility_note": string,
  "subscores": {
    "skills": 0-100,               // overlap of required/preferred technical skills with the resume
    "experience_relevance": 0-100, // relevance of the candidate's internships and projects to the day-to-day work
    "role_alignment": 0-100,       // match with the candidate's target areas in PREFERENCES
    "eligibility": 0-100,          // new-grad / 0-2 years fit, degree level, graduation timing
    "location": 0-100              // match with location preferences
  },
  "reasons": [up to 4 short phrases citing concrete resume evidence],
  "missing_skills": [up to 3 short phrases]
}

Set "eligible" to false if the role requires 3+ years of full-time industry experience, requires a degree the candidate will not have (e.g. PhD-only), is an internship/co-op, is located only outside the candidate's preferred locations, or otherwise clearly excludes a new graduate."""


def load_resume(path: Path) -> str:
    if text := os.environ.get("RESUME_TEXT", "").strip():
        return text
    text = "\n".join((page.extract_text() or "") for page in PdfReader(str(path)).pages).strip()
    if not text:
        raise ValueError(f"No text could be extracted from {path}")
    return text


def _parse_json(content: str) -> dict:
    match = re.search(r"\{.*\}", content or "", re.S)
    if not match:
        raise ValueError(f"No JSON object in model response: {content[:200]!r}")
    return json.loads(match.group(0))


def score_job(job, resume: str, preferences: str, model: str, base_url: str, api_key: str) -> dict:
    description = (job["description"] or "").strip()[:8000] or "(not available — judge from title, company and location)"
    user_prompt = (
        f"PREFERENCES:\n{preferences}\n\nRESUME:\n{resume}\n\n"
        f"JOB:\nTitle: {job['title']}\nCompany: {job['company']}\nLocation: {job['location']}\n"
        f"Description:\n{description}"
    )
    r = SESSION.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        },
        timeout=120,
    )
    r.raise_for_status()
    data = _parse_json(r.json()["choices"][0]["message"]["content"])

    subscores = data.get("subscores") or {}
    score = round(sum(float(subscores.get(k, 0)) * w for k, w in WEIGHTS.items()))
    eligible = bool(data.get("eligible", True))
    if not eligible:
        score = min(score, 50)
    return {
        "score": max(0, min(100, score)),
        "eligible": eligible,
        "eligibility_note": str(data.get("eligibility_note", "")),
        "reasons": [str(x) for x in (data.get("reasons") or [])][:4],
        "missing_skills": [str(x) for x in (data.get("missing_skills") or [])][:3],
    }
