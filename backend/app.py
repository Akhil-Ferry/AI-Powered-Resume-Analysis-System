import os

from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename

from config import Config
from models import db
from models.database import Resume, JobCache
from services.resume_parser import parse_resume, allowed_file, clean_text, extract_emails, extract_phones, extract_skills
from services.embedding_service import embed_text, embed_texts, rank_by_similarity, current_source
from services.job_fetcher import fetch_jobs
from services.analyzer import compute_match, general_resume_feedback


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app, origins=Config.CORS_ORIGINS if Config.CORS_ORIGINS != ["*"] else "*")

    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    db.init_app(app)

    with app.app_context():
        db.create_all()

    register_routes(app)
    return app


def register_routes(app):

    @app.route("/api/health")
    def health():
        return jsonify({
            "status": "ok",
            "embedding_provider": current_source(),
            "openai_enabled": Config.USE_OPENAI,
        })

    # ------------------------------------------------------------------
    # Resume upload / parsing
    # ------------------------------------------------------------------
    @app.route("/api/resume/upload", methods=["POST"])
    def upload_resume():
        if "file" in request.files and request.files["file"].filename:
            file = request.files["file"]
            filename = secure_filename(file.filename)

            if not allowed_file(filename, Config.ALLOWED_EXTENSIONS):
                return jsonify({"error": "Unsupported file type. Use pdf, docx, or txt."}), 400

            file_bytes = file.read()
            try:
                parsed = parse_resume(file_bytes, filename)
            except Exception as exc:  # noqa: BLE001
                return jsonify({"error": f"Failed to parse file: {exc}"}), 400

        elif request.is_json and request.json.get("text"):
            filename = None
            text = request.json["text"]
            cleaned = clean_text(text)
            parsed = {
                "raw_text": text,
                "cleaned_text": cleaned,
                "emails": extract_emails(cleaned),
                "phones": extract_phones(cleaned),
                "skills": extract_skills(cleaned),
            }
        else:
            return jsonify({"error": "Provide a resume file (multipart 'file') or JSON {'text': ...}"}), 400

        if not parsed["cleaned_text"].strip():
            return jsonify({"error": "Could not extract any text from the resume."}), 400

        try:
            embedding, source = embed_text(parsed["cleaned_text"])
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": f"Failed to generate embedding: {exc}"}), 502

        resume = Resume(filename=filename, raw_text=parsed["raw_text"], cleaned_text=parsed["cleaned_text"])
        resume.set_skills(parsed["skills"])
        resume.set_emails(parsed["emails"])
        resume.set_phones(parsed["phones"])
        resume.set_embedding(embedding)
        resume.embedding_source = source

        db.session.add(resume)
        db.session.commit()

        return jsonify({
            "message": "Resume uploaded and parsed successfully.",
            "resume": resume.to_dict(),
        }), 201

    @app.route("/api/resume/<int:resume_id>", methods=["GET"])
    def get_resume(resume_id):
        resume = Resume.query.get_or_404(resume_id)
        return jsonify(resume.to_dict())

    @app.route("/api/resume/<int:resume_id>", methods=["DELETE"])
    def delete_resume(resume_id):
        resume = Resume.query.get_or_404(resume_id)
        db.session.delete(resume)
        db.session.commit()
        return jsonify({"message": "Deleted."})

    @app.route("/api/resume/<int:resume_id>/feedback", methods=["GET"])
    def resume_feedback(resume_id):
        resume = Resume.query.get_or_404(resume_id)
        feedback = general_resume_feedback(resume.cleaned_text, resume.get_skills())
        return jsonify({"resume_id": resume.id, "feedback": feedback, "source": "openai" if Config.USE_OPENAI else "heuristic"})

    # ------------------------------------------------------------------
    # Job listings (free API, live data)
    # ------------------------------------------------------------------
    @app.route("/api/jobs", methods=["GET"])
    def list_jobs():
        search = request.args.get("search", "")
        location = request.args.get("location", "")
        remote_only = request.args.get("remote_only", "false").lower() == "true"
        try:
            page = max(1, int(request.args.get("page", 1)))
            limit = min(100, max(1, int(request.args.get("limit", 25))))
        except ValueError:
            return jsonify({"error": "page and limit must be valid integers."}), 400

        result = fetch_jobs(search=search, location=location, remote_only=remote_only, page=page, limit=limit)
        if result["error"]:
            return jsonify({"error": result["error"], "jobs": []}), 502

        return jsonify({"count": len(result["jobs"]), "jobs": result["jobs"]})

    # ------------------------------------------------------------------
    # Analysis: resume vs a single job description
    # ------------------------------------------------------------------
    @app.route("/api/analyze", methods=["POST"])
    def analyze():
        body = request.get_json(force=True, silent=True) or {}
        resume_id = body.get("resume_id")
        job_description = body.get("job_description", "")
        job_tags = body.get("job_tags", [])

        if not resume_id:
            return jsonify({"error": "resume_id is required"}), 400
        if not job_description or not job_description.strip():
            return jsonify({"error": "job_description is required"}), 400

        resume = Resume.query.get(resume_id)
        if not resume:
            return jsonify({"error": f"No resume found with id {resume_id}"}), 404

        try:
            result = compute_match(
                resume_text=resume.cleaned_text,
                resume_skills=resume.get_skills(),
                resume_embedding=resume.get_embedding(),
                resume_embedding_source=resume.embedding_source,
                job_description=job_description,
                job_tags=job_tags,
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 409
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": f"Analysis failed: {exc}"}), 502

        return jsonify({"resume_id": resume.id, **result})

    # ------------------------------------------------------------------
    # Match resume against live job listings, ranked by semantic similarity
    # ------------------------------------------------------------------
    @app.route("/api/match-jobs", methods=["POST"])
    def match_jobs():
        body = request.get_json(force=True, silent=True) or {}
        resume_id = body.get("resume_id")
        search = body.get("search", "")
        location = body.get("location", "")
        remote_only = bool(body.get("remote_only", False))
        try:
            top_n = min(25, max(1, int(body.get("top_n", 10))))
        except (TypeError, ValueError):
            return jsonify({"error": "top_n must be a valid integer."}), 400

        if not resume_id:
            return jsonify({"error": "resume_id is required"}), 400

        resume = Resume.query.get(resume_id)
        if not resume:
            return jsonify({"error": f"No resume found with id {resume_id}"}), 404

        active_source = current_source()
        if resume.embedding_source != active_source:
            return jsonify({
                "error": (
                    f"Resume was embedded with '{resume.embedding_source}' but the app is "
                    f"currently using '{active_source}'. Re-upload the resume to refresh its embedding."
                )
            }), 409

        job_result = fetch_jobs(search=search, location=location, remote_only=remote_only, limit=50)
        if job_result["error"]:
            return jsonify({"error": job_result["error"], "matches": []}), 502

        jobs = job_result["jobs"]
        if not jobs:
            return jsonify({"matches": [], "message": "No jobs found for the given filters."})

        candidates = []
        try:
            # Reuse stored vectors whenever possible, then embed the remaining
            # descriptions as one batch. This makes live job ranking much faster
            # than issuing one embedding request per listing.
            uncached_jobs = []
            for job in jobs:
                cached = JobCache.query.filter_by(external_id=job["external_id"]).first()
                if cached and cached.embedding_source == active_source:
                    embedding = cached.get_embedding()
                    candidates.append({**job, "embedding": embedding})
                else:
                    uncached_jobs.append((job, cached))

            if uncached_jobs:
                vectors, source = embed_texts([
                    job["description"] or job["title"] for job, _ in uncached_jobs
                ])
                for (job, cached), embedding in zip(uncached_jobs, vectors):
                    if cached:
                        cached.title = job["title"]
                        cached.company = job["company"]
                        cached.location = job["location"]
                        cached.url = job["url"]
                        cached.description = job["description"]
                        cached.set_tags(job["tags"])
                        cached.set_embedding(embedding)
                        cached.embedding_source = source
                    else:
                        cached = JobCache(
                            external_id=job["external_id"],
                            title=job["title"],
                            company=job["company"],
                            location=job["location"],
                            url=job["url"],
                            description=job["description"],
                        )
                        cached.set_tags(job["tags"])
                        cached.set_embedding(embedding)
                        cached.embedding_source = source
                        db.session.add(cached)
                    candidates.append({**job, "embedding": embedding})
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": f"Failed to generate job embeddings: {exc}"}), 502

        db.session.commit()

        ranked = rank_by_similarity(resume.get_embedding(), candidates)[:top_n]

        resume_skill_set = {s.lower() for s in resume.get_skills()}
        matches = []
        for job in ranked:
            job_tags_lower = {t.lower() for t in job.get("tags", [])}
            matched_skills = sorted(resume_skill_set & job_tags_lower)
            matches.append({
                "title": job["title"],
                "company": job["company"],
                "location": job["location"],
                "url": job["url"],
                "tags": job["tags"],
                "match_score": job["score"],
                "matched_skills": matched_skills,
            })

        return jsonify({"resume_id": resume.id, "count": len(matches), "matches": matches})


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=Config.DEBUG)
