"""Manage a private PostgreSQL cluster. Never changes the system service."""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

import psycopg2
from psycopg2 import sql
from dotenv import dotenv_values, set_key

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"
DATA = LOCAL / "postgres"
CREDS = LOCAL / "database.json"
PG_BIN = Path(os.getenv("PG_BIN", r"C:\Program Files\PostgreSQL\18\bin"))


def run(*args, check=True):
    return subprocess.run([str(PG_BIN / args[0]), *map(str, args[1:])], check=check,
                          creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["setup", "start", "stop", "status"])
    action = parser.parse_args().action
    LOCAL.mkdir(exist_ok=True)
    if action == "setup":
        if not CREDS.exists():
            CREDS.write_text(json.dumps({"admin_password": secrets.token_hex(24),
                                        "app_password": secrets.token_hex(24), "port": 5433}))
        settings = json.loads(CREDS.read_text())
        if not (DATA / "PG_VERSION").exists():
            pwfile = LOCAL / "initdb-password"
            pwfile.write_text(settings["admin_password"])
            try:
                run("initdb.exe", "-D", DATA, "-U", "resume_admin", "--pwfile", pwfile,
                    "--auth=scram-sha-256", "--encoding=UTF8", "--locale=C")
            finally:
                pwfile.unlink(missing_ok=True)
            with (DATA / "postgresql.conf").open("a") as config:
                config.write(f"\nlisten_addresses = '127.0.0.1'\nport = {settings['port']}\n")
    if action in {"setup", "start"}:
        if run("pg_ctl.exe", "-D", DATA, "status", check=False).returncode != 0:
            run("pg_ctl.exe", "-D", DATA, "-l", LOCAL / "postgres.log", "-w", "start")
    elif action == "stop":
        run("pg_ctl.exe", "-D", DATA, "-m", "fast", "-w", "stop")
    else:
        run("pg_ctl.exe", "-D", DATA, "status")
    if action != "setup":
        return
    conn = psycopg2.connect(host="127.0.0.1", port=settings["port"], user="resume_admin",
                            password=settings["admin_password"], dbname="postgres")
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = 'resume_app'")
        if not cur.fetchone():
            cur.execute(sql.SQL("CREATE ROLE resume_app LOGIN PASSWORD {}").format(sql.Literal(settings["app_password"])))
        cur.execute("SELECT 1 FROM pg_database WHERE datname = 'resume_analyzer'")
        if not cur.fetchone():
            cur.execute("CREATE DATABASE resume_analyzer OWNER resume_app")
    conn.close()
    conn = psycopg2.connect(host="127.0.0.1", port=settings["port"], user="resume_admin",
                            password=settings["admin_password"], dbname="resume_analyzer")
    with conn, conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
    conn.close()
    env = ROOT / "backend" / ".env"
    if not env.exists():
        env.write_text((env.parent / ".env.example").read_text())
    values = dotenv_values(env)
    url = f"postgresql://resume_app:{settings['app_password']}@127.0.0.1:{settings['port']}/resume_analyzer"
    if not values.get("DATABASE_URL") or "@127.0.0.1:5433/resume_analyzer" in values["DATABASE_URL"]:
        set_key(str(env), "DATABASE_URL", url)
    if not values.get("FLASK_SECRET_KEY") or values.get("FLASK_SECRET_KEY") == "change-this-secret-key":
        set_key(str(env), "FLASK_SECRET_KEY", secrets.token_hex(32))
    print("PostgreSQL + pgvector ready on 127.0.0.1:5433. Credentials saved locally; OpenAI key preserved.")


if __name__ == "__main__":
    try:
        main()
    except (psycopg2.Error, subprocess.CalledProcessError, OSError) as exc:
        print(f"Database setup failed ({type(exc).__name__}). Check .local/postgres.log and PG_BIN.", file=sys.stderr)
        sys.exit(1)
