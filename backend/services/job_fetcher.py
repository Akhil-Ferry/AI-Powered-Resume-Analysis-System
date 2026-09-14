import html
import re
import threading
import time
from urllib.parse import urlparse

import requests
from flask import current_app

_cache = {}
_lock = threading.Lock()


def _strip_html(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()


def fetch_jobs(search="", location="", remote_only=False, page=1, limit=25):
    url = current_app.config["JOB_API_URL"]
    key = (url, page)
    try:
        with _lock:
            cached = _cache.get(key)
        if cached and cached[0] > time.monotonic():
            payload = cached[1]
        else:
            response = requests.get(url, params={"page": page}, timeout=15)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
                raise ValueError("Invalid job feed")
            with _lock:
                if len(_cache) >= 32:
                    _cache.clear()
                _cache[key] = (time.monotonic() + current_app.config["JOB_CACHE_SECONDS"], payload)
    except (requests.RequestException, ValueError):
        return {"error": "Could not load live jobs. Try again, or search previously saved jobs.", "jobs": []}
    jobs = []
    for item in payload["data"]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "")[:500]
        description = _strip_html(str(item.get("description") or ""))[:12000]
        tags = [t[:100] for t in item.get("tags", []) if isinstance(t, str)] if isinstance(item.get("tags"), list) else []
        place = str(item.get("location") or "")[:255]
        remote = bool(item.get("remote", False))
        if remote_only and not remote:
            continue
        if location.strip().lower() not in place.lower() and not (remote and location.strip().lower() in ("remote", "anywhere")):
            continue
        if search.strip().lower() not in " ".join([title, description, *tags]).lower():
            continue
        link = str(item.get("url") or "")[:2000]
        if urlparse(link).scheme not in ("https", "http"):
            link = ""
        external_id = str(item.get("slug") or link or title)[:1000]
        if not title or not external_id:
            continue
        jobs.append({"external_id": external_id, "title": title,
                     "company": str(item.get("company_name") or "Unknown")[:255],
                     "location": "Remote" if remote else (place or "Not specified"),
                     "url": link, "tags": tags, "description": description, "remote": remote})
        if len(jobs) >= limit:
            break
    return {"error": None, "jobs": jobs}
