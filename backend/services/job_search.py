from datetime import datetime, timezone
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from models import db
from models.database import JobCache
from services.embedding_service import current_source, embed_texts, fingerprint


def sync_jobs(jobs):
    # One cache query and one batched embedding operation; refresh changed descriptions.
    jobs = list({job["external_id"]: job for job in jobs}.values())
    if not jobs:
        return []
    existing = {row.external_id: row for row in db.session.scalars(
        select(JobCache).where(JobCache.external_id.in_([job["external_id"] for job in jobs]))
    )}
    pending = []
    for job in jobs:
        content = job["title"] + "\n" + job["description"] + "\n" + ", ".join(job["tags"])
        digest = fingerprint(content)
        row = existing.get(job["external_id"])
        if row is None or row.content_hash != digest or row.embedding_source != current_source():
            pending.append((job, content, digest))
        else:
            # Keep metadata fresh even when the semantic content is unchanged.
            for key in ("company", "location", "url", "remote"):
                setattr(row, key, job[key])
            row.fetched_at = datetime.now(timezone.utc)
    vectors, source = embed_texts([item[1] for item in pending])
    for (job, _, digest), vector in zip(pending, vectors):
        values = {**job, "content_hash": digest, "embedding": vector, "embedding_source": source,
                  "fetched_at": datetime.now(timezone.utc)}
        statement = insert(JobCache).values(**values)
        db.session.execute(statement.on_conflict_do_update(
            index_elements=["external_id"],
            set_={key: getattr(statement.excluded, key) for key in values if key != "external_id"}))
    db.session.commit()
    return [job["external_id"] for job in jobs]


def search_jobs(vector, top_n=10, external_ids=None, location="", remote_only=False):
    distance = JobCache.embedding.cosine_distance(vector)
    query = select(JobCache, distance.label("distance")).where(JobCache.embedding_source == current_source())
    if external_ids is not None:
        query = query.where(JobCache.external_id.in_(external_ids))
    if location:
        query = query.where(JobCache.location.icontains(location, autoescape=True))
    if remote_only:
        query = query.where(JobCache.remote.is_(True))
    # pgvector 0.8+: continue scanning when metadata filters discard HNSW candidates.
    db.session.execute(text("SET LOCAL hnsw.iterative_scan = 'strict_order'"))
    rows = db.session.execute(query.order_by(distance).limit(top_n)).all()
    return [{**job.to_dict(), "match_score": round(max(0.0, min(1.0, 1 - float(d))) * 100, 2)}
            for job, d in rows]
