import json
from datetime import datetime

from models import db


class Resume(db.Model):
    __tablename__ = "resumes"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=True)
    raw_text = db.Column(db.Text, nullable=False)
    cleaned_text = db.Column(db.Text, nullable=False)

    skills = db.Column(db.Text, default="[]")
    emails = db.Column(db.Text, default="[]")
    phones = db.Column(db.Text, default="[]")

    embedding = db.Column(db.Text, nullable=False)
    embedding_source = db.Column(db.String(50), default="local")  # "openai" or "local"

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_skills(self, v):
        self.skills = json.dumps(v)

    def get_skills(self):
        return json.loads(self.skills or "[]")

    def set_emails(self, v):
        self.emails = json.dumps(v)

    def get_emails(self):
        return json.loads(self.emails or "[]")

    def set_phones(self, v):
        self.phones = json.dumps(v)

    def get_phones(self):
        return json.loads(self.phones or "[]")

    def set_embedding(self, v):
        self.embedding = json.dumps(v)

    def get_embedding(self):
        return json.loads(self.embedding)

    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "skills": self.get_skills(),
            "emails": self.get_emails(),
            "phones": self.get_phones(),
            "embedding_source": self.embedding_source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "text_preview": self.cleaned_text[:300],
        }


class JobCache(db.Model):
    __tablename__ = "job_cache"

    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.String(255), unique=True, nullable=False)
    title = db.Column(db.String(500))
    company = db.Column(db.String(255))
    location = db.Column(db.String(255))
    url = db.Column(db.String(1000))
    tags = db.Column(db.Text, default="[]")
    description = db.Column(db.Text)
    embedding = db.Column(db.Text, nullable=False)
    embedding_source = db.Column(db.String(50), default="local")
    fetched_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_tags(self, v):
        self.tags = json.dumps(v)

    def get_tags(self):
        return json.loads(self.tags or "[]")

    def set_embedding(self, v):
        self.embedding = json.dumps(v)

    def get_embedding(self):
        return json.loads(self.embedding)

    def to_dict(self):
        return {
            "id": self.id,
            "external_id": self.external_id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "url": self.url,
            "tags": self.get_tags(),
        }
