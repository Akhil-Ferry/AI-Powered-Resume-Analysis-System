"""
Embedding service with automatic provider switching.

- If OPENAI_API_KEY is set in .env  -> uses OpenAI's text-embedding-3-small
  (higher quality, small per-call cost).
- If no key is set                  -> automatically falls back to a free,
  100% local sentence-transformers model (all-MiniLM-L6-v2). No API key,
  no cost, runs on CPU.

Every function returns `(vector, source)` where source is "openai" or "local",
so callers can store which provider produced an embedding (needed because the
two providers produce vectors of different dimensionality and can't be mixed
in a single cosine-similarity comparison).
"""

import threading

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity as sk_cosine_similarity

from config import Config

_local_model = None
_local_lock = threading.Lock()
_openai_client = None


def _get_local_model():
    global _local_model
    if _local_model is None:
        with _local_lock:
            if _local_model is None:
                from sentence_transformers import SentenceTransformer

                _local_model = SentenceTransformer(Config.LOCAL_EMBEDDING_MODEL)
    return _local_model


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI

        _openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)
    return _openai_client


def current_source() -> str:
    return "openai" if Config.USE_OPENAI else "local"


def embed_text(text: str):
    """Returns (vector: list[float], source: str)."""
    if not text or not text.strip():
        text = " "

    if Config.USE_OPENAI:
        client = _get_openai_client()
        response = client.embeddings.create(model=Config.OPENAI_EMBEDDING_MODEL, input=text)
        return response.data[0].embedding, "openai"

    model = _get_local_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist(), "local"


def embed_texts(texts):
    """Batch embed. Returns (list[vector], source)."""
    texts = [t if t and t.strip() else " " for t in texts]

    if Config.USE_OPENAI:
        client = _get_openai_client()
        response = client.embeddings.create(model=Config.OPENAI_EMBEDDING_MODEL, input=texts)
        vectors = [d.embedding for d in sorted(response.data, key=lambda d: d.index)]
        return vectors, "openai"

    model = _get_local_model()
    vectors = model.encode(texts, normalize_embeddings=True, batch_size=32)
    return [v.tolist() for v in vectors], "local"


def cosine_similarity(vec_a, vec_b) -> float:
    a = np.array(vec_a).reshape(1, -1)
    b = np.array(vec_b).reshape(1, -1)
    if a.shape[1] != b.shape[1]:
        raise ValueError(
            f"Embedding dimension mismatch ({a.shape[1]} vs {b.shape[1]}). "
            "This happens if one embedding was generated with OpenAI and the "
            "other with the local model - re-embed both with the same provider."
        )
    return float(sk_cosine_similarity(a, b)[0][0])


def rank_by_similarity(query_vector, candidates: list):
    """candidates: list of dicts each with an 'embedding' key. Adds a 'score' key
    (0-100 scale) and returns sorted, most similar first."""
    if not candidates:
        return []

    query = np.array(query_vector).reshape(1, -1)
    matrix = np.array([c["embedding"] for c in candidates])
    scores = sk_cosine_similarity(query, matrix)[0]

    for candidate, score in zip(candidates, scores):
        # Cosine similarity can technically be negative. A match percentage is
        # clearer (and safer for the UI) when expressed on a 0-100 scale.
        candidate["score"] = round(max(0.0, float(score)) * 100, 2)

    return sorted(candidates, key=lambda c: c["score"], reverse=True)
