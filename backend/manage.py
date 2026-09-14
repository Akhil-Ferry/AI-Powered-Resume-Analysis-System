"""Versioned, transactional PostgreSQL migrations: python manage.py upgrade."""
import argparse
from pathlib import Path
from sqlalchemy import create_engine, text
from config import Config


def upgrade(url=None):
    url = url or Config.SQLALCHEMY_DATABASE_URI
    if not url.startswith(("postgresql://", "postgresql+psycopg2://")):
        raise RuntimeError("Set DATABASE_URL to a PostgreSQL connection string in backend/.env.")
    engine = create_engine(url, connect_args={"connect_timeout": 5})
    try:
        with engine.begin() as conn:
            conn.execute(text("SELECT pg_advisory_xact_lock(78139422)"))
            if not conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")).scalar():
                raise RuntimeError("Enable pgvector as a database administrator: CREATE EXTENSION vector;")
            conn.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"))
            for path in sorted((Path(__file__).parent / "migrations").glob("*.sql")):
                if conn.execute(text("SELECT 1 FROM schema_migrations WHERE version = :v"), {"v": path.name}).scalar():
                    continue
                conn.exec_driver_sql(path.read_text(encoding="utf-8"))
                conn.execute(text("INSERT INTO schema_migrations(version) VALUES (:v)"), {"v": path.name})
                print(f"Applied {path.name}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["upgrade"])
    parser.parse_args()
    upgrade()
    print("PostgreSQL schema is current.")
