import re

import requests

from config import Config

REQUEST_TIMEOUT = 10


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = re.sub(r"&nbsp;|&amp;|&#39;|&quot;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fetch_jobs(search: str = "", location: str = "", remote_only: bool = False, page: int = 1, limit: int = 25):
    try:
        response = requests.get(Config.JOB_API_URL, params={"page": page}, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        return {"error": f"Could not reach job listings API: {exc}", "jobs": []}

    raw_jobs = payload.get("data", [])
    jobs = []

    search_lower = search.lower().strip()
    location_lower = location.lower().strip()

    for job in raw_jobs:
        title = job.get("title", "")
        description = _strip_html(job.get("description", ""))
        tags = job.get("tags", []) or []
        job_location = job.get("location", "") or ""
        is_remote = job.get("remote", False)

        if remote_only and not is_remote:
            continue

        if location_lower and location_lower not in job_location.lower() and not (
            is_remote and location_lower in ("remote", "anywhere")
        ):
            continue

        if search_lower:
            haystack = " ".join([title, description, " ".join(tags)]).lower()
            if search_lower not in haystack:
                continue

        jobs.append({
            "external_id": job.get("slug") or job.get("url") or title,
            "title": title,
            "company": job.get("company_name", "Unknown"),
            "location": "Remote" if is_remote else (job_location or "Not specified"),
            "url": job.get("url", ""),
            "tags": tags,
            "description": description[:4000],
        })

        if len(jobs) >= limit:
            break

    return {"error": None, "jobs": jobs}
