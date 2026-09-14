import io

import pytest
from sqlalchemy import text

from models import db
from services.embedding_service import embed_text, embed_texts
from services.errors import ServiceError
from services.job_search import search_jobs, sync_jobs
from services.resume_parser import clean_text, extract_skills

RESUME = "Alex Example\nalex@example.com\nBuilt Python Flask REST APIs and PostgreSQL search. Improved response times by 20%."
PROFILE = {"name": "Alex Example", "headline": "Backend developer", "skills": "Python, Flask, PostgreSQL",
           "experience": "Built Python APIs using Flask.", "education": "BSc Computer Science"}


def upload(client):
    response = client.post("/api/resume/upload", json={"text": RESUME})
    assert response.status_code == 201, response.json
    return response.json["resume"]["id"]


def job(id, description):
    return {"external_id": id, "title": "Developer", "company": "Example", "location": "Remote",
            "url": "https://example.com/jobs", "tags": [], "description": description, "remote": True}


def test_database_stack_and_index(client):
    result = client.get("/api/health")
    assert result.status_code == 200
    assert result.json["database"] == "postgresql"
    assert result.json["pgvector"]
    assert db.session.execute(text("SELECT indexdef FROM pg_indexes WHERE indexname='job_embedding_hnsw'")).scalar().endswith("USING hnsw (embedding vector_cosine_ops)")
    assert "X-Response-Time-Ms" in result.headers


def test_sqlite_rejected():
    from app import create_app
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})


def test_resume_lifecycle_and_builder(client, ai):
    response = client.post("/api/resume/build", json={"profile": PROFILE})
    assert response.status_code == 201
    resume = response.json["resume"]
    assert resume["profile"]["name"] == PROFILE["name"]
    assert resume["embedding_source"] == "openai:text-embedding-3-small:1536"
    id = resume["id"]
    assert client.get("/api/resumes").json["total"] == 1
    assert "EXPERIENCE" in client.get(f"/api/resume/{id}/download").text
    updated = client.put(f"/api/resume/{id}", json={"text": RESUME})
    assert updated.status_code == 200
    assert updated.json["resume"]["profile"] is None
    assert client.get(f"/api/resume/{id}").json["emails"] == ["alex@example.com"]
    assert client.delete(f"/api/resume/{id}").status_code == 200
    assert client.get(f"/api/resume/{id}").status_code == 404


@pytest.mark.parametrize("payload", [[], "text", None, {"text": 17}, {"text": ""}, {"text": "x" * 40001}])
def test_invalid_uploads_are_json_errors(client, payload):
    result = client.post("/api/resume/upload", json=payload)
    assert result.status_code == 400
    assert "error" in result.json


def test_file_parsing(client, ai):
    response = client.post("/api/resume/upload", data={"file": (io.BytesIO(RESUME.encode()), "resume.txt")})
    assert response.status_code == 201
    assert client.post("/api/resume/upload", data={"file": (io.BytesIO(b"bad"), "resume.pdf")}).status_code == 400
    assert client.post("/api/resume/upload", data={"file": (io.BytesIO(b"bad"), "resume.exe")}).status_code == 400


def test_analysis_cache_and_history(client, ai):
    id = upload(client)
    payload = {"resume_id": id, "job_description": "Python Flask PostgreSQL developer with Docker", "job_tags": ["python"]}
    result = client.post("/api/analyze", json=payload)
    assert result.status_code == 200, result.json
    assert result.json["suggestions_source"] == "openai"
    assert result.json["match_score"] == 100
    assert "docker" in result.json["missing_skills"]
    calls = (ai.embedding_calls, ai.chat_calls)
    repeated = client.post("/api/analyze", json=payload)
    assert repeated.json["cached"]
    assert (ai.embedding_calls, ai.chat_calls) == calls
    assert len(client.get(f"/api/resume/{id}/analyses").json["analyses"]) == 1
    client.put(f"/api/resume/{id}", json={"text": RESUME + " Docker"})
    changed = client.post("/api/analyze", json=payload)
    assert not changed.json["cached"]
    assert "docker" in changed.json["matched_skills"]
    client.delete(f"/api/resume/{id}")
    assert db.session.execute(text("SELECT count(*) FROM analyses")).scalar() == 0


def test_model_change_prevents_mixing(client, app, ai):
    id = upload(client)
    app.config["OPENAI_EMBEDDING_MODEL"] = "text-embedding-3-large"
    result = client.post("/api/analyze", json={"resume_id": id, "job_description": "Python"})
    assert result.status_code == 409


def test_failed_ai_does_not_claim_success(client, ai, monkeypatch):
    import services.analyzer as analyzer
    id = upload(client)
    def fail(_):
        raise ServiceError("OpenAI review unavailable.")
    monkeypatch.setattr(analyzer, "feedback_for", fail)
    response = client.get(f"/api/resume/{id}/feedback")
    assert response.status_code == 502
    assert "source" not in response.json
    assert db.session.execute(text("SELECT count(*) FROM analyses")).scalar() == 0


def test_missing_key_has_no_local_fallback(client, app):
    app.config["OPENAI_API_KEY"] = ""
    assert client.get("/api/health").json["status"] == "needs_configuration"
    from services.embedding_service import get_client
    with pytest.raises(ServiceError, match="OPENAI_API_KEY"):
        get_client()


def test_feedback_is_cached(client, ai):
    id = upload(client)
    assert client.get(f"/api/resume/{id}/feedback").status_code == 200
    calls = ai.chat_calls
    assert client.get(f"/api/resume/{id}/feedback").json["cached"]
    assert ai.chat_calls == calls


def test_vector_ranking_and_changed_job_refresh(app, ai):
    sync_jobs([job("python", "Python Flask"), job("design", "Graphic design")])
    vector, _ = embed_text("Python developer")
    rows = search_jobs(vector)
    assert rows[0]["external_id"] == "python"
    assert rows[0]["match_score"] == 100
    assert rows[1]["match_score"] == 0
    calls = ai.embedding_calls
    sync_jobs([job("python", "Python Flask"), job("design", "Graphic design")])
    assert ai.embedding_calls == calls
    sync_jobs([job("design", "Python backend")])
    assert ai.embedding_calls == calls + 1
    assert all(row["match_score"] == 100 for row in search_jobs(vector))


def test_live_jobs_and_saved_semantic_search(client, ai, monkeypatch):
    import app as application
    monkeypatch.setattr(application, "fetch_jobs", lambda **kwargs: {"error": None, "jobs": [job("py", "Python Flask"), job("ui", "Graphic design")]})
    id = upload(client)
    response = client.post("/api/match-jobs", json={"resume_id": id})
    assert response.status_code == 200
    assert response.json["search_engine"] == "pgvector"
    assert response.json["matches"][0]["external_id"] == "py"
    result = client.post("/api/jobs/search", json={"query": "Graphic design", "remote_only": True})
    assert result.json["matches"][0]["external_id"] == "ui"
    assert client.post("/api/jobs/search", json={"query": "Python", "location": "%"}).json["count"] == 0


def test_batch_dedup_and_long_text(app, ai):
    vectors, _ = embed_texts(["Python", "Python", "x" * 17000])
    db.session.commit()
    assert len(vectors) == 3
    assert vectors[0] == vectors[1]
    assert sum(len(batch) for batch in ai.batches) == 4
    assert all(len(tokens) <= 8000 for batch in ai.batches for tokens in batch)
    calls = ai.embedding_calls
    embed_texts(["Python", "x" * 17000])
    assert ai.embedding_calls == calls


@pytest.mark.parametrize("payload", [
    {"resume_id": True}, {"resume_id": 1.5}, {"resume_id": 1, "top_n": "bad"},
    {"resume_id": 1, "remote_only": "false"},
])
def test_matching_validation(client, ai, payload):
    upload(client)
    assert client.post("/api/match-jobs", json=payload).status_code == 400


def test_nlp_normalization():
    assert clean_text("\uff30\uff59\uff54\uff48\uff4f\uff4e\r\n\x00Flask") == "Python\nFlask"
    assert "java" not in extract_skills("JavaScript")
    assert extract_skills("Postgres PostgreSQL nodejs NLP") == ["nlp", "node.js", "postgresql"]


def test_migration_is_idempotent(database_url):
    from manage import upgrade
    upgrade(database_url)
    upgrade(database_url)
