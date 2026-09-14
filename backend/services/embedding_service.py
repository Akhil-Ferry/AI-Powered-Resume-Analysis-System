"""OpenAI embeddings with token-aware chunking, batching and a PostgreSQL cache."""
from functools import lru_cache
import hashlib
import json
import numpy as np
import tiktoken
from flask import current_app
from openai import OpenAI, OpenAIError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from models import db
from models.database import EmbeddingCache
from services.errors import ServiceError, openai_service_error
from services.resume_parser import clean_text


def fingerprint(*parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def current_source():
    return f"openai:{current_app.config['OPENAI_EMBEDDING_MODEL']}:1536"


@lru_cache(maxsize=4)
def _client(key, timeout):
    return OpenAI(api_key=key, timeout=timeout, max_retries=1)


def get_client():
    key = current_app.config["OPENAI_API_KEY"]
    if not key:
        raise ServiceError("Set OPENAI_API_KEY in backend/.env and restart the backend.", 503)
    return _client(key, current_app.config["OPENAI_TIMEOUT"])


@lru_cache(maxsize=1)
def tokenizer():
    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception as exc:
        raise ServiceError("Could not load the text tokenizer. Check the network connection and retry.") from exc


def embed_text(text):
    vectors, source = embed_texts([text])
    return vectors[0], source


def embed_texts(texts):
    source = current_source()
    if not texts:
        return [], source
    normalized = [clean_text(t) for t in texts]
    if any(not t for t in normalized):
        raise ValueError("Cannot embed empty text.")
    keys = [fingerprint(source, t) for t in normalized]
    cached = db.session.scalars(select(EmbeddingCache).where(EmbeddingCache.cache_key.in_(keys))).all()
    vectors = {row.cache_key: [float(value) for value in row.embedding] for row in cached}
    missing = dict((key, value) for key, value in zip(keys, normalized) if key not in vectors)
    client = get_client() if missing else None
    chunks, owners, weights = [], [], []
    for key, value in missing.items():
        tokens = tokenizer().encode(value, disallowed_special=())
        for start in range(0, len(tokens), 8000):
            chunk = tokens[start:start + 8000]
            chunks.append(chunk)
            owners.append(key)
            weights.append(len(chunk))
    sums, totals = {}, {}
    try:
        for start in range(0, len(chunks), 16):
            batch = chunks[start:start + 16]
            response = client.embeddings.create(
                model=current_app.config["OPENAI_EMBEDDING_MODEL"],
                input=batch, dimensions=1536,
            )
            data = sorted(response.data, key=lambda item: item.index)
            if len(data) != len(batch) or [v.index for v in data] != list(range(len(batch))):
                raise ServiceError("OpenAI returned an incomplete embedding batch.")
            for offset, item in enumerate(data):
                index = start + offset
                vec = np.asarray(item.embedding, dtype=float)
                if vec.shape != (1536,) or not np.isfinite(vec).all() or np.linalg.norm(vec) == 0:
                    raise ServiceError("OpenAI returned an invalid embedding.")
                key = owners[index]
                sums[key] = sums.get(key, np.zeros(1536)) + vec * weights[index]
                totals[key] = totals.get(key, 0) + weights[index]
    except OpenAIError as exc:
        raise openai_service_error(exc) from exc
    for key in missing:
        vector = sums[key] / totals[key]
        norm = np.linalg.norm(vector)
        if norm == 0:
            raise ServiceError("OpenAI returned a zero embedding.")
        vectors[key] = (vector / norm).tolist()
        db.session.execute(insert(EmbeddingCache).values(cache_key=key, embedding=vectors[key]).on_conflict_do_nothing())
    return [vectors[key] for key in keys], source


def cosine_similarity(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if a.shape != b.shape:
        raise ValueError("Embedding dimensions differ. Re-save the resume to refresh its embedding.")
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.clip(np.dot(a, b) / denom, -1, 1)) if denom else 0.0
