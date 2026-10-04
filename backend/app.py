import os
import time

from flask import Flask, Response, g, jsonify, request
from flask_cors import CORS
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename

from config import Config
from models import db
from models.database import Analysis, Resume
from services.analyzer import PROMPT_VERSION, compute_match, general_resume_feedback
from services.builder import build_resume
from services.embedding_service import current_source, embed_text, fingerprint
from services.errors import ServiceError
from services.job_fetcher import fetch_jobs
from services.job_search import search_jobs, sync_jobs
from services.resume_parser import allowed_file, clean_text, extract_emails, extract_phones, extract_skills, parse_resume


def create_app(overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)
    url = app.config["SQLALCHEMY_DATABASE_URI"]
    if not url.startswith(("postgresql://", "postgresql+psycopg2://")):
        raise RuntimeError("PostgreSQL is required. Set DATABASE_URL or start the Docker Compose database.")
    if app.config["OPENAI_EMBEDDING_MODEL"] not in ("text-embedding-3-small", "text-embedding-3-large"):
        raise RuntimeError("Use text-embedding-3-small or text-embedding-3-large (1536 dimensions).")
    db.init_app(app)
    CORS(app, origins=app.config["CORS_ORIGINS"], expose_headers=["X-Response-Time-Ms"])

    @app.before_request
    def validate_body():
        g.started = time.perf_counter()
        if request.method in ("POST", "PUT") and request.is_json:
            if not isinstance(request.get_json(silent=True), dict):
                raise ValueError("Request JSON must be an object.")

    @app.after_request
    def timing(response):
        response.headers["X-Response-Time-Ms"] = str(round((time.perf_counter() - g.started) * 1000, 2))
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(ValueError)
    def invalid(exc):
        db.session.rollback()
        return jsonify(error=str(exc)), 400

    @app.errorhandler(ServiceError)
    def service_error(exc):
        db.session.rollback()
        app.logger.warning("External operation failed: %s", type(exc.__cause__).__name__)
        return jsonify(error=str(exc)), exc.status

    @app.errorhandler(SQLAlchemyError)
    def database_error(exc):
        db.session.rollback()
        app.logger.error("Database operation failed: %s", type(exc).__name__)
        return jsonify(error="PostgreSQL is unavailable or the schema is not current. Start the database and run python manage.py upgrade."), 503

    @app.errorhandler(HTTPException)
    def http_error(exc):
        return jsonify(error=exc.description), exc.code

    register_routes(app)
    return app


def body():
    if not request.is_json:
        raise ValueError("Send a JSON object with Content-Type: application/json.")
    return request.get_json()


def string(value, name, required=False, maximum=40000):
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError(f"{name} must be text, at most {maximum} characters.")
    if required and not value.strip():
        raise ValueError(f"{name} is required.")
    return value.strip()


def integer(value, name, maximum=1000000000):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a positive integer.")
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"{name} must be a positive integer.") from None
    if str(parsed) != str(value) or not 1 <= parsed <= maximum:
        raise ValueError(f"{name} must be between 1 and {maximum}.")
    return parsed


def boolean(value, name):
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be true or false.")
    return value


def resume_by_id(value):
    return db.get_or_404(Resume, integer(value, "resume_id"))


def save_resume(raw, filename=None, profile=None, resume=None):
    raw = string(raw, "Resume text", required=True)
    cleaned = clean_text(raw)
    vector, source = embed_text(cleaned)
    resume = resume or Resume()
    resume.filename, resume.raw_text, resume.cleaned_text = filename, raw, cleaned
    resume.skills, resume.emails, resume.phones = extract_skills(cleaned), extract_emails(cleaned), extract_phones(cleaned)
    resume.profile, resume.embedding, resume.embedding_source = profile, vector, source
    db.session.add(resume)
    db.session.commit()
    return resume


def require_current(resume):
    if resume.embedding_source != current_source():
        raise ServiceError("Embedding model changed. Edit and save this resume to refresh its embedding.", 409)


def register_routes(app):
    @app.get("/api/health")
    def health():
        version = db.session.execute(text("SELECT extversion FROM pg_extension WHERE extname='vector'")).scalar()
        migrated = db.session.execute(text("SELECT to_regclass('public.schema_migrations')")).scalar()
        if not version or not migrated:
            raise ServiceError("Database schema needs setup. Run python manage.py upgrade.", 503)
        key_present = bool(app.config["OPENAI_API_KEY"])
        return jsonify(status="ok" if key_present else "needs_configuration", database="postgresql",
                       pgvector=version, embedding_provider="openai", embedding_model=app.config["OPENAI_EMBEDDING_MODEL"],
                       openai_enabled=key_present, openai_key_configured=key_present,
                       message="Ready. OpenAI credentials are verified when an AI operation runs." if key_present else "Add OPENAI_API_KEY to backend/.env and restart.")

    @app.get("/api/resumes")
    def resumes():
        page = integer(request.args.get("page", "1"), "page")
        limit = integer(request.args.get("limit", "20"), "limit", 100)
        result = db.paginate(select(Resume).order_by(Resume.created_at.desc(), Resume.id.desc()),
                             page=page, per_page=limit, error_out=False)
        return jsonify(resumes=[r.to_dict() for r in result.items], total=result.total, page=page, pages=result.pages)

    @app.post("/api/resume/upload")
    def upload():
        if "file" in request.files:
            file = request.files["file"]
            filename = secure_filename(file.filename or "")
            if not allowed_file(filename, app.config["ALLOWED_EXTENSIONS"]):
                raise ValueError("Unsupported file type. Use PDF, DOCX or TXT.")
            try:
                parsed = parse_resume(file.read(), filename)
            except Exception:
                raise ValueError("Could not read this file. Use a text-based PDF, DOCX or UTF-8 TXT file.") from None
            raw = parsed["raw_text"]
        else:
            raw, filename = body().get("text", ""), None
        resume = save_resume(raw, filename)
        return jsonify(resume=resume.to_dict(full=True)), 201

    @app.post("/api/resume/build")
    def build():
        raw, profile = build_resume(body().get("profile"))
        resume = save_resume(raw, profile=profile)
        return jsonify(resume=resume.to_dict(full=True)), 201

    @app.get("/api/resume/<int:resume_id>")
    def get_resume(resume_id):
        return jsonify(resume_by_id(resume_id).to_dict(full=True))

    @app.put("/api/resume/<int:resume_id>")
    def update_resume(resume_id):
        resume, data = resume_by_id(resume_id), body()
        if "profile" in data:
            raw, profile = build_resume(data["profile"])
        else:
            raw, profile = data.get("text", ""), None
        return jsonify(resume=save_resume(raw, resume.filename, profile, resume).to_dict(full=True))

    @app.delete("/api/resume/<int:resume_id>")
    def delete_resume(resume_id):
        db.session.delete(resume_by_id(resume_id))
        db.session.commit()
        return jsonify(message="Deleted.")

    @app.get("/api/resume/<int:resume_id>/download")
    def download(resume_id):
        resume = resume_by_id(resume_id)
        return Response(resume.raw_text, mimetype="text/plain",
                        headers={"Content-Disposition": f'attachment; filename="resume-{resume.id}.txt"'})

    @app.get("/api/resume/<int:resume_id>/feedback")
    def feedback(resume_id):
        resume = resume_by_id(resume_id)
        key = fingerprint("feedback", PROMPT_VERSION, resume.id, resume.cleaned_text, app.config["OPENAI_CHAT_MODEL"])
        cached = db.session.scalar(select(Analysis).where(Analysis.cache_key == key))
        if cached:
            return jsonify(resume_id=resume.id, feedback=cached.result["suggestions"], source="openai", cached=True)
        suggestions = general_resume_feedback(resume.cleaned_text, resume.skills)
        db.session.execute(insert(Analysis).values(resume_id=resume.id, cache_key=key, job_description="",
                           result={"suggestions": suggestions, "suggestions_source": "openai"}).on_conflict_do_nothing())
        db.session.commit()
        return jsonify(resume_id=resume.id, feedback=suggestions, source="openai", cached=False)

    @app.get("/api/resume/<int:resume_id>/analyses")
    def history(resume_id):
        resume_by_id(resume_id)
        rows = db.session.scalars(select(Analysis).where(Analysis.resume_id == resume_id)
                                  .order_by(Analysis.created_at.desc()).limit(30))
        return jsonify(analyses=[{"id": r.id, "job_description": r.job_description,
                                  "created_at": r.created_at.isoformat(), **r.result} for r in rows])

    @app.post("/api/analyze")
    def analyze():
        data = body()
        resume = resume_by_id(data.get("resume_id"))
        description = string(data.get("job_description", ""), "job_description", required=True)
        tags = data.get("job_tags", [])
        if not isinstance(tags, list) or len(tags) > 100 or not all(isinstance(t, str) and len(t) <= 100 for t in tags):
            raise ValueError("job_tags must be a list of up to 100 short strings.")
        require_current(resume)
        key = fingerprint("analysis", PROMPT_VERSION, resume.id, resume.cleaned_text, current_source(),
                          description, sorted(set(tags)), app.config["OPENAI_CHAT_MODEL"])
        cached = db.session.scalar(select(Analysis).where(Analysis.cache_key == key))
        if cached:
            return jsonify(resume_id=resume.id, analysis_id=cached.id, cached=True, **cached.result)
        result = compute_match(resume.cleaned_text, resume.skills, resume.get_embedding(),
                               resume.embedding_source, description, tags)
        db.session.execute(insert(Analysis).values(resume_id=resume.id, cache_key=key,
                           job_description=description, result=result).on_conflict_do_nothing())
        db.session.commit()
        saved = db.session.scalar(select(Analysis).where(Analysis.cache_key == key))
        return jsonify(resume_id=resume.id, analysis_id=saved.id, cached=False, **result)

    @app.get("/api/jobs")
    def jobs():
        remote = request.args.get("remote_only", "false")
        if remote not in ("true", "false"):
            raise ValueError("remote_only must be true or false.")
        result = fetch_jobs(search=string(request.args.get("search", ""), "search", maximum=200),
                            location=string(request.args.get("location", ""), "location", maximum=200),
                            remote_only=remote == "true", page=integer(request.args.get("page", "1"), "page", 1000),
                            limit=integer(request.args.get("limit", "25"), "limit", 100))
        if result["error"]:
            raise ServiceError(result["error"])
        return jsonify(count=len(result["jobs"]), jobs=result["jobs"])

    @app.post("/api/match-jobs")
    def match_jobs():
        data = body()
        resume = resume_by_id(data.get("resume_id"))
        require_current(resume)
        top_n = integer(data.get("top_n", 10), "top_n", 25)
        result = fetch_jobs(search=string(data.get("search", ""), "search", maximum=200),
                            location=string(data.get("location", ""), "location", maximum=200),
                            remote_only=boolean(data.get("remote_only", False), "remote_only"), limit=50)
        if result["error"]:
            raise ServiceError(result["error"])
        ids = sync_jobs(result["jobs"])
        matches = search_jobs(resume.get_embedding(), top_n=top_n, external_ids=ids) if ids else []
        add_matched_skills(matches, resume.skills)
        return jsonify(resume_id=resume.id, count=len(matches), matches=matches, search_engine="pgvector")

    @app.post("/api/jobs/search")
    def semantic_search():
        data = body()
        if data.get("resume_id") is not None:
            resume = resume_by_id(data["resume_id"])
            require_current(resume)
            vector, skills = resume.get_embedding(), resume.skills
        else:
            query = string(data.get("query", ""), "query", required=True)
            vector, _ = embed_text(query)
            skills = extract_skills(query)
        matches = search_jobs(vector, integer(data.get("top_n", 10), "top_n", 25),
                              location=string(data.get("location", ""), "location", maximum=200),
                              remote_only=boolean(data.get("remote_only", False), "remote_only"))
        add_matched_skills(matches, skills)
        db.session.commit()
        return jsonify(count=len(matches), matches=matches, search_engine="pgvector")


def add_matched_skills(matches, skills):
    for job in matches:
        job["matched_skills"] = sorted(set(skills) & (set(extract_skills(job["description"])) |
                                                    {t.lower() for t in job["tags"]}))


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=app.config["DEBUG"])
