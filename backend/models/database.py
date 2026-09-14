from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB
from models import db

DIMENSIONS = 1536


def now():
    return datetime.now(timezone.utc)


class Resume(db.Model):
    __tablename__ = "resumes"
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255))
    raw_text = db.Column(db.Text, nullable=False)
    cleaned_text = db.Column(db.Text, nullable=False)
    skills = db.Column(JSONB, nullable=False, default=list)
    emails = db.Column(JSONB, nullable=False, default=list)
    phones = db.Column(JSONB, nullable=False, default=list)
    profile = db.Column(JSONB)
    embedding = db.Column(Vector(DIMENSIONS), nullable=False)
    embedding_source = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=now, onupdate=now, nullable=False)

    def get_skills(self):
        return self.skills

    def get_embedding(self):
        return [float(value) for value in self.embedding]

    def to_dict(self, full=False):
        result = {
            "id": self.id, "filename": self.filename, "skills": self.skills,
            "emails": self.emails, "phones": self.phones,
            "embedding_source": self.embedding_source,
            "created_at": self.created_at.isoformat(), "updated_at": self.updated_at.isoformat(),
            "text_preview": self.cleaned_text[:300],
        }
        if full:
            result.update(text=self.raw_text, profile=self.profile)
        return result


class JobCache(db.Model):
    __tablename__ = "job_cache"
    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.String(1000), unique=True, nullable=False)
    title = db.Column(db.String(500), nullable=False)
    company = db.Column(db.String(255), nullable=False)
    location = db.Column(db.String(255), nullable=False)
    url = db.Column(db.String(2000), nullable=False)
    tags = db.Column(JSONB, nullable=False, default=list)
    description = db.Column(db.Text, nullable=False)
    remote = db.Column(db.Boolean, nullable=False, default=False)
    content_hash = db.Column(db.String(64), nullable=False)
    embedding = db.Column(Vector(DIMENSIONS), nullable=False)
    embedding_source = db.Column(db.String(100), nullable=False)
    fetched_at = db.Column(db.DateTime(timezone=True), default=now, nullable=False)

    def to_dict(self):
        return {key: getattr(self, key) for key in
                ("id", "external_id", "title", "company", "location", "url", "tags", "description", "remote")}


class EmbeddingCache(db.Model):
    __tablename__ = "embedding_cache"
    cache_key = db.Column(db.String(64), primary_key=True)
    embedding = db.Column(Vector(DIMENSIONS), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=now, nullable=False)


class Analysis(db.Model):
    __tablename__ = "analyses"
    id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False)
    cache_key = db.Column(db.String(64), unique=True, nullable=False)
    job_description = db.Column(db.Text, nullable=False)
    result = db.Column(JSONB, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=now, nullable=False)
