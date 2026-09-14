"""Exercise real OpenAI + PostgreSQL with synthetic content, then remove test records."""
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app
from models import db
from models.database import EmbeddingCache
from sqlalchemy import delete
from services.embedding_service import current_source, fingerprint

RESUME = "Alex Example\nBackend Engineer\nBuilt Python Flask REST APIs with PostgreSQL. Reduced response latency by 20% through SQL query optimization. Skills: Python, Flask, PostgreSQL, Docker."
JOB = "Backend engineer building Python Flask REST APIs with PostgreSQL, Docker and semantic search."
client = app.test_client()
resume_id = None
try:
    response = client.post("/api/resume/upload", json={"text": RESUME})
    if response.status_code != 201:
        raise RuntimeError(f"Upload failed: {response.status_code} {response.json}")
    resume_id = response.json["resume"]["id"]
    payload = {"resume_id": resume_id, "job_description": JOB}
    start = time.perf_counter()
    response = client.post("/api/analyze", json=payload)
    uncached_ms = round((time.perf_counter() - start) * 1000, 1)
    if response.status_code != 200:
        raise RuntimeError(f"Analysis failed: {response.status_code} {response.json}")
    assert response.json["suggestions_source"] == "openai"
    start = time.perf_counter()
    cached = client.post("/api/analyze", json=payload)
    cached_ms = round((time.perf_counter() - start) * 1000, 1)
    assert cached.status_code == 200 and cached.json["cached"]
    print(f"PASS: real OpenAI embedding + recommendations, PostgreSQL persistence, analysis cache.")
    print(f"Observed analysis latency: first={uncached_ms} ms, cached={cached_ms} ms. Single local sample, not a load benchmark.")
finally:
    if resume_id is not None:
        client.delete(f"/api/resume/{resume_id}")
    with app.app_context():
        keys = [fingerprint(current_source(), value) for value in (RESUME, JOB)]
        db.session.execute(delete(EmbeddingCache).where(EmbeddingCache.cache_key.in_(keys)))
        db.session.commit()
