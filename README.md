# AI-Powered Resume Analysis System

**Python | Flask | PostgreSQL | OpenAI API | NLP | Vector Embeddings**

A resume builder and analysis application with a React interface. PostgreSQL is required; OpenAI generates all embeddings and recommendations. There is no SQLite database fallback or local AI mode.

## Features

- Build a resume from structured profile fields, preview it, save/edit it, download TXT, or use the browser's Print / Save PDF.
- Upload PDF, DOCX or TXT, or paste existing resume text.
- Normalize Unicode and whitespace; extract contact information and technical skill phrases with canonical aliases.
- Compare resumes against job descriptions with OpenAI embeddings and contextual, keyword-targeted feedback.
- Save resumes, general reviews and job-match history in PostgreSQL.
- Search live Arbeitnow job listings, batch-embed new/changed job content, and rank it in PostgreSQL.
- Search previously saved jobs semantically, with location and remote filters.
- Reuse persistent embedding and analysis caches, pooled database connections, a shared OpenAI client and a short-lived job-feed cache.
- Use versioned, transactional database migrations, JSON errors, input limits, and request latency headers.

Match scores are cosine similarity percentages, **not** hiring probabilities or ATS scores. Keyword extraction uses a maintained technical vocabulary; it is not a general-purpose entity-recognition model.

## Docker setup

Install Docker Desktop, then set an OpenAI key in your shell:

```powershell
$env:OPENAI_API_KEY="your-own-key"
docker compose up --build
```

Open **http://localhost:5174**. The API is available at **http://localhost:5000**.
The database, backend, and frontend run as separate containers. PostgreSQL data is
persisted in the `postgres_data` Docker volume. Stop the stack with
`docker compose down`; add `-v` only when you intentionally want to delete the
database volume.

For a hosted PostgreSQL instance, replace the `DATABASE_URL` value in
`docker-compose.yml` and keep pgvector enabled. Do not commit API keys or
production database credentials.

## Database and environment details

| Setting | Project value |
|---|---|
| Database host | `db` inside Docker |
| Port | `5432` inside Docker |
| Database | `resume_analyzer` |
| Application user | `resume_app` (not a superuser) |
| Password | Generated locally; included in `backend/.env`'s `DATABASE_URL` |
| Vector extension | pgvector, version 0.8+ |
| Embedding model | `text-embedding-3-small`, 1536 dimensions |
| Recommendation model | `gpt-4o-mini` |
| Frontend API URL | `frontend/.env`: `VITE_API_BASE_URL=http://localhost:5000` |

`backend/.env`, `frontend/.env` and `.local/` are excluded from Git. Docker Compose
credentials are development defaults; use secrets or environment variables in
production.

For a hosted database, provision PostgreSQL with pgvector 0.8+, enable the extension as its administrator, and set:

```dotenv
DATABASE_URL=postgresql://USER:URL_ENCODED_PASSWORD@HOST:5432/DATABASE?sslmode=require
```

Use the SSL settings required by your provider. The application user needs permission to create its own schema tables and indexes. Enable the extension once:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

The backend image runs `python manage.py upgrade` before starting the API, so
migrations are applied automatically after PostgreSQL is healthy.

## Embedding model options

The default is OpenAI `text-embedding-3-small` with 1536 dimensions. OpenAI
usage is paid, although the model is relatively inexpensive. The application
also uses `gpt-4o-mini` for written recommendations, which is a separate
chat-model cost.

Free or local alternatives are possible, but they are not drop-in replacements
in the current build: the schema fixes vectors at `vector(1536)` and the
embedding service calls the OpenAI API. Models such as
`sentence-transformers/all-MiniLM-L6-v2` (384 dimensions) or
`BAAI/bge-small-en-v1.5` (384 dimensions) can run locally with Ollama or
Sentence Transformers, but require an embedding-provider adapter and a database
migration/re-embedding of existing records. A local model also does not replace
the OpenAI chat recommendations. If you need a completely free setup, use a
local embedding model plus a local chat model such as Ollama, accepting the
additional integration and hardware requirements.

## Architecture

```mermaid
flowchart LR
    UI[React resume builder] --> API[Flask REST API / Waitress]
    API --> NLP[Text normalization and skill extraction]
    NLP --> Emb[OpenAI embeddings]
    API --> Review[OpenAI contextual recommendations]
    Emb --> PG[(PostgreSQL + pgvector)]
    API --> PG
    Feed[Arbeitnow live job feed] --> API
    PG --> Rank[Cosine-distance search]
    Rank --> UI
```

The schema contains:

- `resumes`: resume text, optional structured profile, JSONB metadata and `vector(1536)`.
- `job_cache`: job content, content fingerprint, model identity and vectors, with an HNSW cosine index.
- `embedding_cache`: normalized-content/model fingerprints and reusable vectors.
- `analyses`: resume-linked recommendations and job descriptions; repeated requests reuse the result.
- `schema_migrations`: applied SQL migration versions.

Migration scripts live in `backend/migrations`; `python manage.py upgrade` applies each once under a PostgreSQL advisory lock. Startup does not silently create or mutate tables. Add new numbered migration files for future schema changes.

Long embedding inputs are split into chunks of at most 8,000 tokens, embedded in batches of at most 16 chunks and combined by token-weighted, normalized averaging. Model identity is stored alongside vectors, and mismatched models return HTTP 409 until the resume is re-saved. The database fixes dimensionality at 1536. Changing embedding model requires re-saving resumes and refreshing job embeddings; changing dimensionality requires a migration.

The HNSW index supports approximate nearest-neighbor search over stored jobs. A small filtered result set may be faster with a sequential scan; PostgreSQL chooses its plan. Approximate results trade recall for speed.

The app sends resume/job text to OpenAI for AI operations. Missing or failed OpenAI access returns a clear error; heuristic feedback is never passed off as OpenAI output. Health reports whether a key is configured, not whether billing/model access has been verified.

## REST API

All errors are JSON: `{"error":"message"}`. IDs and pagination must be positive integers.
Text inputs are limited to 40,000 characters; file requests default to 5 MB.

| Method | Endpoint | Input / purpose |
|---|---|---|
| GET | `/api/health` | PostgreSQL/pgvector readiness and OpenAI configuration |
| GET | `/api/resumes?page=1&limit=20` | Paginated saved resumes |
| POST | `/api/resume/upload` | Multipart `file` or JSON `{"text":"..."}` |
| POST | `/api/resume/build` | `{"profile":{"name":"...","experience":"...",...}}` |
| GET / PUT / DELETE | `/api/resume/<id>` | Read, edit (`text` or `profile`), delete |
| GET | `/api/resume/<id>/download` | Plain-text download |
| GET | `/api/resume/<id>/feedback` | Cached OpenAI general review |
| GET | `/api/resume/<id>/analyses` | Latest 30 saved reviews |
| POST | `/api/analyze` | `{"resume_id":1,"job_description":"...","job_tags":[]}` |
| GET | `/api/jobs` | Live feed; `search, location, remote_only, page, limit` |
| POST | `/api/match-jobs` | `{"resume_id":1,"search":"","location":"","remote_only":false,"top_n":10}` |
| POST | `/api/jobs/search` | `{"query":"Python backend","top_n":10}` or `{"resume_id":1}`; optional location/remote filters |

Builder profile fields are strings: `name, headline, email, phone, location, summary, skills, experience, projects, education`. Name and at least one of experience/projects/education are required.

Live matching fetches up to 50 filtered jobs from one job-feed page and saves them. Saved search only searches jobs already ingested; it is not a search of the entire external job board.

Responses include `X-Response-Time-Ms`. Analysis/review responses expose `cached`.

## Verification

Database integration tests use a **fresh temporary PostgreSQL database** and mocked OpenAI responses. They cover persistence, vector ranking, changed-job refresh, analysis cache invalidation, batching/chunking, JSON validation, builder/edit/delete, provider mismatch, error handling and migrations. They never clear the application's database.

```powershell
cd backend
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
cd ../frontend
npm run lint
npm run build
```

For a real OpenAI check, after saving a valid key with model access and API billing:

```powershell
cd backend
.venv\Scripts\python.exe scripts/live_smoke.py
```

This sends synthetic resume/job text, checks real embeddings and recommendations, measures first/repeated analysis latency, and removes its temporary resume/review records. It uses billable OpenAI API calls. Its single local latency sample is not a throughput benchmark. No percentage latency improvement or production scale is claimed without measurement.

## Scope and operational limits

This is a complete local, single-user workflow. Servers bind to loopback by default.
Authentication, per-user authorization, public hosting, distributed rate limiting and a background ingestion queue are not implemented. Add them before turning this into a public multi-user service. Waitress provides threaded request serving; pooling/caching/indexing are implemented, but sustained load has not been benchmarked.

Scanned image-only PDFs require OCR, which is not included. Job-feed availability and job locations depend on Arbeitnow. Existing local backups are excluded from version control.

## Repository checks and publishing

GitHub Actions runs frontend lint/build and backend tests against an isolated PostgreSQL + pgvector service. OpenAI is mocked; CI needs no API credentials. See [CONTRIBUTING.md](CONTRIBUTING.md).

To publish to a new empty GitHub repository after reviewing the changes:

```bash
git add .
git diff --cached --stat
git commit -m "Prepare resume analysis platform"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
git push -u origin main
```

Create the GitHub repository without an initial README or other files when using these commands. Removing a Git remote does not remove local commit history. Environment files, databases, dependencies and logs remain local. Review `git status` before committing; do not force-add ignored files.

## Primary implementation references

- [OpenAI embeddings](https://developers.openai.com/api/docs/guides/embeddings)
- [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [pgvector and HNSW indexing](https://github.com/pgvector/pgvector)
- [pgvector SQLAlchemy integration](https://github.com/pgvector/pgvector-python)
