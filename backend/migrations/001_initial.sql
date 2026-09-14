CREATE TABLE resumes (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255),
    raw_text TEXT NOT NULL,
    cleaned_text TEXT NOT NULL,
    skills JSONB NOT NULL DEFAULT '[]',
    emails JSONB NOT NULL DEFAULT '[]',
    phones JSONB NOT NULL DEFAULT '[]',
    profile JSONB,
    embedding vector(1536) NOT NULL,
    embedding_source VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE job_cache (
    id SERIAL PRIMARY KEY,
    external_id VARCHAR(1000) UNIQUE NOT NULL,
    title VARCHAR(500) NOT NULL,
    company VARCHAR(255) NOT NULL,
    location VARCHAR(255) NOT NULL,
    url VARCHAR(2000) NOT NULL,
    tags JSONB NOT NULL DEFAULT '[]',
    description TEXT NOT NULL,
    remote BOOLEAN NOT NULL DEFAULT false,
    content_hash VARCHAR(64) NOT NULL,
    embedding vector(1536) NOT NULL,
    embedding_source VARCHAR(100) NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX job_embedding_hnsw ON job_cache USING hnsw (embedding vector_cosine_ops);
CREATE INDEX job_source_idx ON job_cache (embedding_source);
CREATE INDEX job_fetched_idx ON job_cache (fetched_at);
CREATE TABLE embedding_cache (
    cache_key VARCHAR(64) PRIMARY KEY,
    embedding vector(1536) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE analyses (
    id SERIAL PRIMARY KEY,
    resume_id INTEGER NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
    cache_key VARCHAR(64) UNIQUE NOT NULL,
    job_description TEXT NOT NULL,
    result JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX analyses_resume_idx ON analyses (resume_id, created_at DESC);
CREATE INDEX resumes_created_idx ON resumes (created_at DESC);
