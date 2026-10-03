# ProjectTrace AI — verified build report

Date: 3 October 2026. Status: **locally tested pre-release**, with production release gates still open. No completion percentage is claimed.

## 1. What was built

An evidence-grounded project intelligence application at `C:\Users\sai krishna\OneDrive\Desktop\ProjectTrace-AI`. Windows Known Folder detection resolved the actual Desktop to OneDrive/Desktop; no existing related repository was found. One project was created there, with no numbered duplicate folders. The implementation safely imports source, preserves snapshot provenance, reviews code/README claims, supports cited questions, prepares viva practice and generates conservative documentation drafts.

The native demo is running at http://127.0.0.1:5173 while its local processes remain active. This is not a public deployment. No commit, push, uploaded-repository execution or automatic deployment occurred.

## 2. Architecture

React 19 + TypeScript + Vite 8 + Tailwind 4 calls a versioned FastAPI/Pydantic API. SQLAlchemy models and explicit Alembic migrations store users, sessions, projects, snapshots, evidence, claims, consistency findings, jobs, viva and document history. Separate worker processes perform static analysis; HTTP requests enqueue work and return job identifiers.

Production adapters are PostgreSQL/pgvector, Redis/RQ and a structured OpenAI Responses provider. The validated Windows path uses SQLite, FAISS, deterministic lexical hashing vectors, a separate SQL-backed local worker and offline answers. Optional Sentence Transformers is behind an embedding interface. The local adapter is suitable for demonstrations; production uses the mature RQ queue.

Analysis creates immutable snapshots and commits derived evidence plus the current-snapshot pointer atomically. Failure rolls back partial derived rows and preserves the preceding successful snapshot. A partial database index prevents two active analyses for one project. BM25, vector similarity and code/path signals retrieve bounded evidence; cached answers include snapshot and provider/model identity. External citations are restricted to retrieved evidence IDs. Citation validity does not establish semantic entailment, so provider results remain inferred.

See `docs/architecture.md` and the three decision records for boundaries and tradeoffs.

## 3. File and folder structure

```text
ProjectTrace-AI/
  frontend/
    src/app/                  application shell and import flow
    src/components/           accessible shared controls and evidence views
    src/features/             claims, evidence, ask, viva, documents
    src/services/             typed API client and memory-only CSRF
    e2e/                      desktop and mobile browser tests
  backend/
    app/api/                  versioned owner-scoped routes
    app/core/                 settings and database units of work
    app/parsers/              ZIP validation, source AST and metadata
    app/security/             auth, CSRF, redaction, limits and logs
    app/retrieval/             lexical/vector retrieval interfaces
    app/ai/                   provider abstraction and structured outputs
    app/services/             analysis, claims, audit and intelligence
    app/workers/              RQ/local worker and retention maintenance
    alembic/versions/         explicit initial and job-guard migrations
    tests/                    ownership, malicious input, grounding, failure tests
    requirements.lock        exact validated backend dependencies
  samples/                    safe React/FastAPI/mixed static fixtures and ZIP
  scripts/                    launcher, readiness, UI review and benchmark
  docs/                       architecture, deployment, reviews and evidence
  .github/workflows/ci.yml   checks plus PostgreSQL/Redis integration
  compose.yaml               infrastructure and full-container profiles
  .env.example               documented local defaults; no live credentials
  README.md, SECURITY.md, CONTRIBUTING.md
```

Local virtualenv, installed modules, databases, original uploads, caches and private configuration are intentionally excluded from the source archive.

## 4. Features implemented

- Registration, login/logout, expiring owner-scoped sessions, idempotent development/demo account seeding and loopback-only temporary demo.
- Project creation/switching; safe ZIP and public GitHub import; asynchronous stage labels, safe failure/retry and queued-job cancellation.
- Immutable history, SHA-256 ZIP snapshot identity, and GitHub default branch/commit provenance.
- Read-only file explorer with line numbers, evidence excerpts and snapshot-safe source links.
- Five-state claim ledger with explanations, recommendations, confidence disclaimers, project-wide counts, server search/filtering and pagination.
- README/code comparison with MATCH, contradiction, unsupported/inferred findings and stale claims after reanalysis.
- Grounded technology/configuration Q&A, explicit uncertainty for unsupported workflow questions, and optional schema-constrained OpenAI Q&A.
- Five viva perspectives with suggested answers, evidence, follow-up prompts and persisted revision markers.
- Cited Markdown report, Learning Block presentation content with 13 headings, resume, LinkedIn, README and viva-note drafts; unsupported purpose/contribution fields require author input.
- Static deployment indicators, potential-secret findings, history views, theme persistence, responsive navigation and confirmed project deletion.

The mixed fixture actually yields React, FastAPI, PostgreSQL and SQLAlchemy signals, with **5 verified, 2 unverified and 1 contradicted claim**. The README's MongoDB assertion contradicts PostgreSQL source configuration. JWT protection and production readiness are not presented as established facts. Claims refer to static source/configuration presence, not successful operation.

## Demo Login

On API startup, `APP_ENV=development` or `APP_ENV=demo` seeds this account after database migrations:

| Email | Password |
|---|---|
| `demo@projecttrace.ai` | `ProjectTrace@123` |

Open **http://127.0.0.1:5173** and use the **Sign in** form with these credentials. The account starts with an empty workspace; choose **Analyze project → Sample project** to add the evidence fixture. You can return to the same account and projects after signing out. **View demo** continues to create a separate temporary local workspace.

These are published local-demo credentials, not production secrets. The seed fixture stores only a password hash generated with the project's Argon2id hasher; normal application code contains no plaintext demo password. Startup is idempotent, including concurrent API starts, and never resets an existing account's password. No admin account is seeded because this version has no admin roles or functionality.

Seeding is skipped in production and test environments even if `SEED_DEMO_USER=true`; set `SEED_DEMO_USER=false` to disable it in development/demo. Use separate databases for local demonstrations and production. Run Alembic migrations before starting the API.

## 5. Security controls

Repositories are read as data; no target dependencies, hooks, commands, models or containers are executed. ZIPs are read without filesystem extraction. Traversal, absolute/Windows device and alternate-stream paths, symlinks, duplicate entries, encryption, nested archives and excessive compression/size/counts are rejected. Ignored files still consume archive safety quotas. Unsupported binaries and non-UTF-8 files are omitted.

Imports accept only a validated public `https://github.com/owner/repository` form and fixed GitHub download hosts, with no redirects. When the shared REST quota is exhausted, bounded `git ls-remote` resolves HEAD with configuration, credential helpers, interactive prompting, redirects and non-HTTPS protocols disabled. It does not clone or check out the repository.

Argon2id hashes passwords. Opaque HTTP-only SameSite cookies expire and revoke on logout; Secure is required for production. Session hashes use the configured secret. Mutations require CSRF, foreign origins are denied, and nested IDs are owner checked. Production rejects unsuitable database/queue/HTTPS/secret settings. Demo access is disabled in production and outside loopback.

Heuristic secret scanning runs before persistence and before provider calls; non-template `.env` content is fully redacted. Source/output is escaped in React and never evaluated. Untrusted snippets are isolated as context, providers receive no tools, schema/citation constraints bound results and output is re-redacted. Structured request logs omit source and credential values; safe error envelopes hide internal exceptions.

Original archives may contain unredacted credentials until private 24-hour retention cleanup. Derived evidence remains until project deletion. Encryption, backups, provider data policy, disclosure contact and exhaustive credential review remain operator responsibilities. This review is not an independent penetration test. See SECURITY.md for concrete release prerequisites.

## 6. Performance and traffic controls

Central defaults: 50 MB upload, 200 MB uncompressed archive, 10,000 entries, 2 MB per text file, 20,000 chunks, compression ratio 150 and 600-second RQ job timeout. Request bodies are capped both by declared length and streamed bytes. Default connection-IP limits per minute: login/registration/demo-session creation 10, imports 5, AI 10, general API 120. Redis provides atomic deployment limits and failure closes access; the native adapter uses process memory. Project count is bounded at 50 per owner. List endpoints use bounded pages; ledger evidence is fetched in batches rather than per-claim queries.

Measured observations in `performance-results.json` use one local worker, SQLite, offline Q&A and a seven-file fixture:

| Measurement | Actual result |
|---|---|
| Analysis wall time including polling | 533.03 ms |
| Archive parsing | 4.08 ms |
| Lexical embedding | 0.48 ms |
| 40 claim requests / 8 threads | 40 HTTP 200; median 91.02 ms; observed p95 120.99 ms |
| 12 sequential offline AI requests | 10 HTTP 200 and 2 intentional HTTP 429 |
| Offline AI latency including rejected requests | median 11.15 ms; observed p95 74.41 ms |
| Frontend production JS / CSS gzip | 84.10 KB / 7.72 KB |

These are small-fixture observations, not capacity guarantees, external-provider latency or production benchmarks. FAISS is flat and rebuilt per uncached query; BM25 loads the bounded corpus. Larger projects need persisted indexes, profiling and concurrency tests. Limits use connection IP, so production proxy handling needs explicit configuration.

## 7. Test results

| Validation | Verified result |
|---|---|
| Backend pytest | **73 passed**, 21.55 seconds |
| Backend statement coverage | **87.02%**, not full coverage |
| Backend Ruff lint/format | Passed |
| Alembic schema drift check | No new upgrade operations detected |
| Frontend Vitest | **5 passed**, 2 files |
| Frontend ESLint, strict TypeScript and Vite build | Passed |
| npm dependency audit | **0 reported vulnerabilities** at validation time |
| Playwright Edge seeded login, workflow and mobile | **3 passed**, 13.9 seconds |
| Clean native setup | New source copy, fresh virtualenv, lock installs, npm ci, empty SQLite migrations, API + separate worker, ZIP analysis, contradiction, cited answer and frontend build passed |
| Real public GitHub import | `octocat/Hello-World` completed; master, commit `7fd1a60b01f91b314f59955a4e4d4e80d8edf11d` |
| Live OpenAI / semantic model | Not exercised; structured provider failures/citation behavior tested with mocks |
| Docker / PostgreSQL / Redis / remote CI | Not exercised in this environment |

Tests also verify development/demo startup seeding, hashed credentials, login/logout, idempotent restart, concurrent starts, preservation of existing passwords, explicit opt-out, production/test exclusion before fixture/database access, and rate-budget separation for session checks. Tests cover IDOR across views, CSRF/logout, malformed archives and body limits, SSRF/URL restrictions, sensitive output redaction, dependency-vs-source grounding, README matches/contradictions, stale evidence, missing evidence, provider schema/auth/quota/timeout errors, rollback, bounded queries, active-job uniqueness, queued cancellation, deletion cascades and snapshot-scoped caching. The clean setup test used native source rather than preinstalled project dependencies. It proves the local adapter only.

The final browser pass followed a fix for an intermittent startup race: authentication originally exposed a project before demo import enqueue, so its first view could contain no job and never poll. Demo initialization now enqueues before opening the authenticated workspace. Other review fixes included keyboard-scroll regions, mobile overflow and project-wide ledger filtering.

One upstream Starlette test-client warning concerns future httpx/httpx2 compatibility. It did not fail tests, and the currently installed lock is preserved. Browser tooling emits a harmless NO_COLOR/FORCE_COLOR warning. These warnings are recorded rather than hidden.

Machine evidence is in `backend-test-results.xml`, `backend-coverage.json`, `clean-setup-results.json`, `performance-results.json`, `frontend-validation.json` and `ui-review-results.json`.

## 8. UI and UX validation

Real captured screenshots cover every product screen plus light overview and mobile overview/ledger/source. The review recorded **zero page errors**, **zero axe violations on 11 checked screen/theme combinations**, and **zero document overflow across 36 page/viewport checks** at 320, 390, 768 and 1024px. Internal table/source scrolling is intentional. Keyboard focus, Escape drawer dismissal, empty results, literal untrusted strings and source navigation were verified.

This is not a WCAG certification. Cross-browser/device, mobile screen-reader, all-light-screen and representative user studies remain outstanding. See `ui-review.md` for methodology, corrected issues and screenshot names.

## 9. Deployment status

The native development application runs locally. Dockerfiles, same-origin nginx/CSP, Compose, migrations, readiness endpoints, worker/maintenance commands and GitHub Actions are prepared. Docker, PostgreSQL and Redis were unavailable, so container and production-adapter integration are unverified. No remote CI run or public deployment was started; no commit or push occurred.

`/ready` verifies database/migrations and Redis when configured; it does not certify worker liveness. Before release: run the integration workflow, build containers, test worker recovery/retention, provision HTTPS and real secrets, protect Redis/shared storage, verify backups/restoration, configure monitoring/disclosure and exercise actual provider/semantic models. Native dev servers must stay local.

## 10. Known limitations

Technology/claim extraction is heuristic and Python AST coverage does not generalize to every language/framework. Broad application behavior, authorization, successful tests, deployment and claimed accuracy cannot be proven by static indicators. Valid citations do not guarantee claim entailment. Offline Q&A answers narrow source/configuration facts; document/viva generation uses evidence templates. Purpose/objectives/personal contribution must come from authors.

Hashing vectors are lexical, not semantic. Retrieval has no demonstrated large-corpus/high-traffic capacity. Local SQL worker is a single-process adapter. Original archives can retain secrets until cleanup. All device/theme/accessibility combinations are not verified. GitHub's rate and network behavior can change; only a real public sample and controlled failure cases were tested. The convenience launcher passed PowerShell syntax parsing; its full interactive start/stop flow was not independently exercised. Manual three-terminal setup was verified.

## 11. Items not implemented

- PDF, DOCX, PPTX, uploaded report/resume/presentation extraction and artifact-to-artifact comparisons beyond repository README/source.
- Native formatted PDF/DOCX/PPTX export; current downloads are cited Markdown content.
- Private GitHub OAuth, enterprise repository import and multi-user collaboration roles.
- General-purpose grounded workflow narration, semantic entailment verifier, multilingual source AST coverage and model-performance verification.
- Email verification, password reset, account-deletion UI, managed production backups, alerting and a configured disclosure contact.
- Persistent ANN retrieval indexes, a proved multi-instance deployment, large-load evaluation, live model integration tests and completed production rollout.

The source provides interfaces and deployment preparation for several of these; this does not make them completed features. The brief's production-grade target remains a release objective rather than a certified current status.

## 12. Exact commands to run locally

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

Checks from `backend`: `..\.venv\Scripts\python.exe -m ruff check .`, `..\.venv\Scripts\python.exe -m ruff format --check .`, `..\.venv\Scripts\python.exe -m pytest --cov=app`, and `..\.venv\Scripts\python.exe -m alembic check`. Checks from `frontend`: `npm.cmd test`, `npm.cmd run lint`, `npm.cmd run build`, `npm.cmd audit`, and `npm.cmd run test:e2e` with services running.

From the root, `node scripts/ui-review.cjs` reproduces screenshots/audits. ` .\.venv\Scripts\python.exe scripts\performance_probe.py` creates a local demo and a public GitHub validation project, sends bounded benchmark requests and overwrites the benchmark report. Run validation tools sequentially so intentional rate limits do not interfere. Docker commands are documented in `docs/deployment.md`, and remain unverified here.

## 13. Demo workflow

1. Open http://127.0.0.1:5173 and choose **View demo**. Wait for actual worker stages.
2. Review the detected React/FastAPI/PostgreSQL stack and real eight-claim summary.
3. Open **Claim Ledger → Contradicted** and inspect “The project uses MongoDB as its database.”
4. Compare the README statement with cited `backend/database.py` PostgreSQL configuration; open its exact source lines.
5. In **Ask Project**, choose “Which database does this project use?” The answer cites configuration and does not claim runtime success.
6. In **Viva**, choose **Adversarial Examiner**, start practice and reveal the discrepancy answer. Mark a question for revision.
7. In **Documentation**, generate a report or 13-part presentation draft and download Markdown. Missing objectives/contribution are explicitly marked for author input.
8. Use **Analyze project** for `samples/mixed-demo.zip` or a public GitHub URL. Reanalysis preserves historical snapshots. Review deployment indicators as static observations.

## 14. Next highest-value improvements

1. Close release gates: production integration/container builds, live provider and semantic model tests, retention/recovery/backup restoration and monitoring.
2. Evaluate claim entailment and behavior extraction on varied repositories; add false-positive/false-negative fixtures and separate author assertions from implemented behavior.
3. Add document parsers and artifact-version comparisons, then actual PDF/DOCX/PPTX rendering/export with layout validation.
4. Profile large corpora and persist vector/BM25 indexes; add database ANN indexes and measure multi-user queues before making scale claims.
5. Complete account recovery/lifecycle, disclosure configuration, cross-browser/device accessibility and user testing.

No automatic follow-up, deployment, commit or push has been scheduled.
