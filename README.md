# ProjectTrace AI

**Understand it. Verify it. Document it. Defend it.**

Evidence-grounded project intelligence for students and early-career developers. Source, README and project explanations often disagree; ProjectTrace preserves exact source provenance, checks technical statements, and helps prepare documentation and viva answers from what is actually present.

This is a pre-release implementation with a verified native demo path. It is not declared production ready. See `docs/validation-report.md` for actual test results and remaining release gates.

## What is available

- ZIP and public GitHub import with queued static analysis and immutable snapshots.
- React/FastAPI/PostgreSQL and other technology signals, separated from dependency-only inference.
- A five-state claim ledger: verified, inferred, unverified, contradicted and stale.
- Code ↔ README consistency review with recommendations and source locations.
- Hybrid evidence retrieval, narrow offline Q&A and an optional OpenAI structured-output adapter.
- Five viva perspectives with answers, citations and revision markers.
- Cited Markdown report, 13-part Learning Block presentation content, resume/LinkedIn guidance, README suggestions and viva notes.
- Static deployment indicators, redaction, owner-scoped sessions, migrations, security tests and CI.
- Responsive light/dark React interface with claim inspectors and line-numbered source evidence.

**Evidence policy:** source presence/configuration is not proof of successful runtime behavior. README claims do not establish technologies. Documents label missing purpose, objectives and personal contributions for author input. No uploaded code is executed. Binary artifacts and document/PPTX/PDF imports are not supported in v1.

## Architecture and folders

React + TypeScript + Vite + Tailwind → FastAPI + Pydantic → SQLAlchemy/Alembic → PostgreSQL/pgvector + Redis/RQ worker. The native local demo substitutes SQLite, FAISS, lexical hashing vectors and a separate durable local worker. Optional Sentence Transformers provides semantic embeddings; it is not required for the offline demo.

```
frontend/        feature views, application shell, Vitest and Playwright
backend/app/     api, core, parsers, security, retrieval, ai, services, workers
backend/alembic/ explicit database migrations
backend/tests/   API, ownership, security, provider and evidence fixtures
samples/         React, FastAPI and mixed static data fixtures + demo ZIP
scripts/         local launcher, readiness and performance tools
docs/            architecture, decisions, deployment and validation
.github/         test/build/integration workflows; no deployment
```

Read `docs/architecture.md`, `SECURITY.md`, `CONTRIBUTING.md` and `docs/deployment.md`. RQ was chosen for a small Python worker architecture; pgvector keeps deployment data in PostgreSQL; FAISS makes native setup practical. See `docs/decisions/`.

## Windows native demo setup

Requirements: Python 3.11 or 3.12, Node 24, npm, Git for the public-import quota fallback, and Microsoft Edge for local Playwright tests. Docker is optional for the native demo. Python 3.14 is not the validated version. Use these commands one at a time from the project root. Adjust the path if you place the repository elsewhere.

### PowerShell

```powershell
Set-Location -LiteralPath 'C:\Users\sai krishna\OneDrive\Desktop\ProjectTrace-AI'
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock
Copy-Item -LiteralPath .env.example -Destination .env
Set-Location backend
..\.venv\Scripts\python.exe -m alembic upgrade head
Set-Location ..\frontend
npm.cmd ci
Set-Location ..
```

Skip the copy command if `.env` already contains your configuration. The default `.env.example` config is SQLite + separate local worker + offline provider. Paths are resolved from the current directory; run backend processes from `backend` as below. No API key is necessary for the demo.

### CMD

```bat
cd /d "C:\Users\sai krishna\OneDrive\Desktop\ProjectTrace-AI"
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend\requirements.lock
copy .env.example .env
cd backend
..\.venv\Scripts\python.exe -m alembic upgrade head
cd ..\frontend
npm ci
cd ..
```

### Start three terminals

In terminal 1, from backend:

```powershell
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

In terminal 2, from backend:

```powershell
..\.venv\Scripts\python.exe -m app.workers.runner
```

In terminal 3, from frontend:

```powershell
npm.cmd run dev
```

CMD uses the same Python commands; replace `npm.cmd run dev` with `npm run dev` if preferred. Open **http://127.0.0.1:5173**. Health is at http://127.0.0.1:8000/ready and development OpenAPI at http://127.0.0.1:8000/docs. Do not expose the native development server publicly.

PowerShell convenience launcher: `powershell -ExecutionPolicy Bypass -File .\scripts\start-local.ps1`. It starts API/worker hidden, runs Vite in the terminal, and stops the processes it created when the frontend exits. Do not run it while another copy of the services uses these ports.

## Demo workflow

1. Open the app and choose **View demo**. A private local session and sample project are created.
2. Wait for the separate worker to finish analysis. Overview shows React, FastAPI, PostgreSQL and real claim counts.
3. Open Claim Ledger → Contradicted → “The project uses MongoDB as its database.”
4. Inspect the README statement and `backend/database.py` PostgreSQL configuration.
5. Ask “Which database does this project use?” and open the cited source.
6. Start Adversarial Examiner viva; reveal the discrepancy answer and mark it for revision.
7. Generate a Markdown draft. Recommendations are separate from verified facts.
8. For your own repository, use Analyze project → ZIP or public GitHub. Register an account if you need to return after the demo session expires.

## Demo Login

On API startup, `APP_ENV=development` or `APP_ENV=demo` seeds this account after database migrations:

| Email | Password |
|---|---|
| `demo@projecttrace.ai` | `ProjectTrace@123` |

Open **http://127.0.0.1:5173** and use the **Sign in** form with these credentials. The account starts with an empty workspace; choose **Analyze project → Sample project** to add the evidence fixture. You can return to the same account and projects after signing out. **View demo** continues to create a separate temporary local workspace.

These are published local-demo credentials, not production secrets. The seed fixture stores only a password hash generated with the project's Argon2id hasher; normal application code contains no plaintext demo password. Startup is idempotent, including concurrent API starts, and never resets an existing account's password. No admin account is seeded because this version has no admin roles or functionality.

Seeding is skipped in production and test environments even if `SEED_DEMO_USER=true`; set `SEED_DEMO_USER=false` to disable it in development/demo. Use separate databases for local demonstrations and production. Run Alembic migrations before starting the API.

## Configuration

| Variable | Purpose / default |
|---|---|
| APP_ENV | development, demo, test, production |
| SEED_DEMO_USER | Seed the published account in development/demo only; default true |
| DATABASE_URL | SQLite local; PostgreSQL + psycopg for deployment |
| REDIS_URL / QUEUE_MODE | Redis/RQ for deployment; local separate worker for demo |
| SECRET_KEY | HMAC session-token hash key; random 32+ characters required in production |
| CORS_ORIGINS | Explicit allowed browser origins; no wildcard |
| LLM_PROVIDER / LLM_API_KEY / LLM_MODEL | offline or openai; provider key required when enabled |
| EMBEDDING_MODEL | hashing-v1 baseline or administrator-chosen 384-dimensional Sentence Transformers |
| VECTOR_STORE | faiss or pgvector |
| MAX_UPLOAD_MB / MAX_EXTRACTED_MB | ZIP 50 MB / decompressed 200 MB |
| MAX_FILE_COUNT / MAX_TEXT_FILE_MB | 10,000 entries / 2 MB per text file |
| MAX_CHUNKS | 20,000 bounded evidence chunks |
| UPLOAD_RETENTION_HOURS / STORAGE_DIR | 24 hours / private .storage directory |
| SESSION_HOURS | 24 hours |

Defaults are centralized in `backend/app/core/config.py`. Production fails clearly on missing PostgreSQL/RQ/HTTPS origins or weak session configuration. API/import/AI/auth rate limits default to 120/5/10/10 requests per minute per connection IP and can be set by their corresponding configuration names.

Original archives remain private and can contain unredacted secrets until retention cleanup. Derived redacted evidence remains until project deletion. Deleting requires the exact project name and is blocked during active analysis. External AI receives only trimmed retrieved context; see SECURITY.md.

## Checks

From backend:

```powershell
..\.venv\Scripts\python.exe -m ruff check .
..\.venv\Scripts\python.exe -m ruff format --check .
..\.venv\Scripts\python.exe -m pytest --cov=app --cov-report=term
..\.venv\Scripts\python.exe -m alembic check
```

From frontend:

```powershell
npm.cmd run lint
npm.cmd test
npm.cmd run build
npm.cmd audit
npm.cmd run test:e2e
```

Run API, worker and frontend before Playwright. Local tests use installed Edge. Linux CI installs Chromium and sets CI=true. Backend tests create isolated SQLite databases through Alembic; they never execute fixture source. GitHub Actions separately exercises the browser flow against PostgreSQL/Redis/pgvector, but a configured workflow is not proof of a remote passing run.

## Deployment and limitations

Container files and Compose are prepared, with non-root backend, health checks, same-origin nginx routing and static frontend CSP. They have not been built here because Docker is unavailable. See deployment notes for PostgreSQL/Redis setup and release gates. No public deployment, automatic commit or push is configured.

Known limitations: heuristic detection can miss or overinterpret unfamiliar syntax; claims are not a formal proof; offline Q&A cannot explain arbitrary workflows; generated documents/viva use evidence templates; hashing vectors are lexical; flat retrieval is bounded but not load-tested at large scale; registration has no email verification/password reset; provider live tests and semantic embedding tests require configured dependencies/credentials. PPT/report/resume import, PDF/DOCX/PPTX output and private GitHub OAuth remain unimplemented.

Roadmap: expand grounded behavior extraction and claim entailment tests; verify production dependencies in CI; add sentence-transformer evaluation and persistent retrieval indexes; add document import adapters and version-aware artifact comparisons. No completion percentage or high-scale claim is made.

## Screenshots

Real captured screens and layout findings are recorded in `docs/ui-review.md` and `docs/screenshots/`. These show fixture-derived data, not invented product metrics.
