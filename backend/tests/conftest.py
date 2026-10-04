import json
import os
from pathlib import Path
from types import SimpleNamespace
import uuid

import psycopg2
from psycopg2 import sql
import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app import create_app
from config import Config
from manage import upgrade
from models import db


@pytest.fixture(scope="session")
def database_url():
    # Every test run owns a fresh database; the application's database is never cleared.
    path = Path(__file__).resolve().parents[2] / ".local" / "database.json"
    admin_url = os.getenv("TEST_POSTGRES_ADMIN_URL")
    if admin_url:
        parsed = make_url(admin_url)
        options = dict(host=parsed.host, port=parsed.port or 5432, user=parsed.username,
                       password=parsed.password, **dict(parsed.query))
        app_url = make_url(Config.SQLALCHEMY_DATABASE_URI)
        if (app_url.host, app_url.port or 5432) != (parsed.host, parsed.port or 5432):
            pytest.fail("DATABASE_URL and TEST_POSTGRES_ADMIN_URL must refer to the same test server.")
    else:
        if not path.exists():
            pytest.fail("Start the Docker Compose database or configure TEST_POSTGRES_ADMIN_URL.")
        credentials = json.loads(path.read_text())
        options = dict(host="127.0.0.1", port=credentials["port"], user="resume_admin",
                       password=credentials["admin_password"])
        app_url = make_url(Config.SQLALCHEMY_DATABASE_URI).set(
            host="127.0.0.1", port=credentials["port"],
            username="resume_app", password=credentials["app_password"])
    name = "resume_test_" + uuid.uuid4().hex[:12]
    admin = psycopg2.connect(dbname="postgres", **options)
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(name), sql.Identifier(app_url.username)))
    try:
        connection = psycopg2.connect(dbname=name, **options)
        with connection, connection.cursor() as cur:
            cur.execute("CREATE EXTENSION vector")
        connection.close()
        url = app_url.set(database=name)
        url = url.render_as_string(hide_password=False)
        upgrade(url)
        yield url
    finally:
        with admin.cursor() as cur:
            cur.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        admin.close()


@pytest.fixture
def app(database_url):
    application = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": database_url,
                              "OPENAI_API_KEY": "test-placeholder", "OPENAI_CHAT_MODEL": "gpt-4o-mini"})
    with application.app_context():
        db.session.execute(text("TRUNCATE analyses, resumes, job_cache, embedding_cache RESTART IDENTITY CASCADE"))
        db.session.commit()
        yield application
        db.session.remove()
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def ai(monkeypatch):
    import services.embedding_service as embeddings
    import services.analyzer as analyzer

    class FakeAI:
        def __init__(self):
            self.embedding_calls = 0
            self.chat_calls = 0
            self.batches = []
            self.embeddings = SimpleNamespace(create=self.embed)
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.review))

        def embed(self, input, **kwargs):
            self.embedding_calls += 1
            self.batches.append(input)
            data = []
            for index, tokens in enumerate(input):
                content = "".join(chr(t) for t in tokens).lower()
                vector = [0.0] * 1536
                vector[0 if "python" in content else 1] = 1.0
                data.append(SimpleNamespace(index=index, embedding=vector))
            return SimpleNamespace(data=data)

        def review(self, **kwargs):
            self.chat_calls += 1
            self.last_prompt = kwargs
            return SimpleNamespace(choices=[SimpleNamespace(
                finish_reason="stop", message=SimpleNamespace(refusal=None,
                content=json.dumps({"suggestions": ["Explain the Flask API work.", "Add real impact metrics if available."]})))])

    fake = FakeAI()
    monkeypatch.setattr(embeddings, "get_client", lambda: fake)
    monkeypatch.setattr(analyzer, "get_client", lambda: fake)
    monkeypatch.setattr(embeddings, "tokenizer", lambda: SimpleNamespace(encode=lambda value, **kwargs: [ord(c) for c in value]))
    return fake
