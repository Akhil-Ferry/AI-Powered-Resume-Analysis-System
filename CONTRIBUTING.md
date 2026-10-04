# Development

Follow the Docker setup instructions in [README.md](README.md). Keep real API keys,
database passwords, resumes and database files out of commits. Copy the provided
`.env.example` files locally; never replace their placeholders with credentials.

Install the locked backend dependencies with `uv sync --locked` in `backend/`
and frontend dependencies with `npm ci` in `frontend/`.

Before committing:

```powershell
cd backend
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
cd ../frontend
npm run lint
npm run build
cd ..
git diff --check
git status --short
```

Backend tests create and delete a uniquely named temporary PostgreSQL database.
Use a PostgreSQL/pgvector test server and provide its administrator connection
through `TEST_POSTGRES_ADMIN_URL`. Set `DATABASE_URL` to the same test server
when using that override. OpenAI calls are mocked in CI; no real API key is
required. Never run tests with production administrator credentials.

Add schema changes as new numbered SQL files in `backend/migrations/`; do not
modify an already-applied migration. Keep both dependency lockfiles committed.
Include tests for behavior changes and update the README when setup or API
behavior changes.

The optional `backend/scripts/live_smoke.py` check uses real OpenAI requests and
requires API credits. Do not include real resumes in test fixtures or reports.
