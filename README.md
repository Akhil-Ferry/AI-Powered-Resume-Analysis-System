# AI-Powered Resume Analysis System

Full-stack app: **Flask + uv** backend, **React (Vite)** frontend.
Semantic resume-to-job matching using vector embeddings, live job listings, and
AI-generated improvement suggestions.

Works **immediately with no API key** (free local embeddings + rule-based
suggestions). Drop your `OPENAI_API_KEY` into `backend/.env` and it
automatically upgrades to OpenAI embeddings (`text-embedding-3-small`) and
GPT-powered suggestions (`gpt-4o-mini`) — no code changes needed.

---

## 1. Prerequisites

- **Python 3.10+** and **[uv](https://docs.astral.sh/uv/getting-started/installation/)** installed
  (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **Node.js 18+** and npm

---

## 2. Backend setup (Flask + uv)

```bash
cd backend
cp .env.example .env
uv sync
```

`uv sync` creates a `.venv` and installs everything from `pyproject.toml` /
`uv.lock` (Flask, SQLAlchemy, the OpenAI SDK, sentence-transformers, etc).

### Add your OpenAI API key (optional but recommended)
Open `backend/.env` and set:
```
OPENAI_API_KEY=sk-...your-key...
```
That's it — restart the backend and it automatically uses OpenAI for both
embeddings and suggestion generation. Leave it blank to keep running 100% free
on the local model.

### Database (optional)
By default the app uses a local SQLite file — **zero setup required**. To use
PostgreSQL instead, set in `backend/.env`:
```
DATABASE_URL=postgresql://username:password@localhost:5432/resume_analyzer
```

### Run the backend
```bash
uv run python app.py
```
API is now live at **http://localhost:5000**. Check `http://localhost:5000/api/health`
— it reports whether OpenAI mode is active.

---

## 3. Frontend setup (React + Vite)

In a second terminal:
```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```
App is now live at **http://localhost:5173**.

`frontend/.env` controls which backend URL the UI talks to
(`VITE_API_BASE_URL=http://localhost:5000` by default).

---

## 4. Run both at once (optional convenience script)

From the project root, after having done the one-time `uv sync` / `npm install` above:
```bash
./run.sh
```
This starts the backend on :5000 and frontend on :5173 together, and stops
both with Ctrl+C.

---

### Windows shortcut

On Windows PowerShell, after the one-time setup, start both servers with:

```powershell
.\run.ps1
```

If your execution policy blocks local scripts, use:

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

## 5. Using the app

1. **Add a resume** — drag & drop a PDF/DOCX/TXT file, or paste text.
2. **Analyze against a job description** — paste any job posting and get a
   semantic match score (0–100%), matched/missing skills, and improvement
   suggestions.
3. **Find & rank live job listings** — searches real, current openings
   (via the free Arbeitnow job board API) and ranks them by semantic
   similarity to your resume.

---

## Project structure

```
resume_project/
├── run.sh                       # start backend + frontend together
├── backend/
│   ├── pyproject.toml           # uv-managed dependencies
│   ├── uv.lock
│   ├── .env.example             # <-- add OPENAI_API_KEY here
│   ├── app.py                   # Flask REST API
│   ├── config.py
│   ├── models/                  # SQLAlchemy models (Resume, JobCache)
│   └── services/
│       ├── embedding_service.py # OpenAI <-> local model auto-switch
│       ├── resume_parser.py     # PDF/DOCX/TXT parsing, skill/email/phone extraction
│       ├── job_fetcher.py       # free live job board integration
│       └── analyzer.py          # match scoring + GPT/heuristic suggestions
└── frontend/
    ├── .env.example             # <-- backend API URL
    └── src/
        ├── api.js               # typed fetch client for the backend
        ├── App.jsx
        └── components/
            ├── StatusBar.jsx        # shows active embedding provider
            ├── ResumeUploader.jsx
            ├── JobAnalyzer.jsx
            ├── JobMatcher.jsx
            ├── ScoreRing.jsx
            └── BadgeList.jsx
```

## REST API reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Health check; reports active embedding provider |
| POST | `/api/resume/upload` | Upload a resume file (`multipart/form-data`, field `file`) or JSON `{"text": "..."}` |
| GET | `/api/resume/<id>` | Get parsed resume data |
| DELETE | `/api/resume/<id>` | Delete a resume |
| GET | `/api/resume/<id>/feedback` | General resume-quality feedback |
| GET | `/api/jobs?search=&location=&remote_only=&page=&limit=` | Live job listings |
| POST | `/api/analyze` | `{resume_id, job_description, job_tags?}` → match score + suggestions |
| POST | `/api/match-jobs` | `{resume_id, search?, location?, remote_only?, top_n?}` → ranked live job matches |

## Notes

- **Switching providers mid-project**: embeddings from OpenAI (1536-dim) and
  the local model (384-dim) can't be compared directly. If you add an API key
  after already uploading resumes, just re-upload the resume (or re-run
  `/api/resume/upload`) so it gets re-embedded with the new provider — the
  API returns a clear `409` error if there's a mismatch, telling you to do this.
- **Job listings source**: uses [Arbeitnow's public API](https://www.arbeitnow.com/api/job-board-api)
  — free, no key required. Swap it for another provider in
  `backend/services/job_fetcher.py` if you prefer (e.g. Remotive, RemoteOK).
- **Production considerations**: add auth/rate-limiting, move uploaded files
  to object storage, and set `FLASK_DEBUG=False` + a real `FLASK_SECRET_KEY`.

# AI-Powered-Resume-Analysis-System
