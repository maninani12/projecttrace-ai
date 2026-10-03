# Deployment preparation

No application has been deployed. Container and hosted-service configuration is supplied for review. The native environment used to build this source has no Docker, PostgreSQL or Redis installation; local validation uses SQLite and a separate local worker. GitHub Actions contains PostgreSQL/Redis integration, but no remote CI run has been started.

## Services

Use managed PostgreSQL with pgvector, a private Redis instance, an API process, an RQ worker, private shared upload storage, and scheduled retention maintenance. Frontend can be a static build behind a CDN/reverse proxy. Use one origin with `/api` routing so secure cookies work reliably; splitting onto unrelated frontend/backend domains requires an explicit cookie/CORS/CSRF design.

Copy `.env.example`, set a strong random SECRET_KEY and POSTGRES_PASSWORD, and configure HTTPS CORS_ORIGINS. Production validates PostgreSQL, RQ, a non-placeholder secret and HTTPS origins at startup. Set DATABASE_URL to `postgresql+psycopg://...`, REDIS_URL to private Redis, QUEUE_MODE=rq, VECTOR_STORE=pgvector, APP_ENV=production. Use credentials URL-encoded in DATABASE_URL. Compose interpolation of POSTGRES_PASSWORD assumes a URL-safe password. Never publish service ports beyond a trusted ingress.

Run migrations as a one-off release step: `python -m alembic upgrade head` from backend. The initial migration creates the vector extension; managed database permissions may require an administrator to provision it first. Start `python -m app.workers.runner` and `python -m app.workers.maintenance` separately from the API. `/health` checks liveness; `/ready` checks migrations/database and Redis connectivity, **not worker liveness**. Monitor worker heartbeat and job age separately.

## Containers

Docker Desktop is required on Windows. Native infrastructure: `docker compose up -d postgres redis`. Full local containers: `docker compose --profile full up --build`. The example maps frontend to `127.0.0.1:8080`; add `http://127.0.0.1:8080` to development CORS_ORIGINS. Development Compose is not an HTTPS production ingress. For production, terminate TLS externally, set HTTPS origins and protect volumes/backups. No automatic deployment is configured.

## AI configuration

Offline mode needs no key. For OpenAI Q&A, set LLM_PROVIDER=openai, LLM_API_KEY and an available LLM_MODEL. The default model is configurable; verify availability in your provider account. The adapter follows [official structured output guidance](https://developers.openai.com/api/docs/guides/structured-outputs). Context is trimmed/redacted and `store=False` is requested. Review your provider's data policy independently. The optional sentence-transformer model must produce 384 dimensions; install `backend/requirements-embeddings.txt` and select a trusted administrator-chosen model. Reanalyze snapshots when changing embeddings. Provider integration and semantic embeddings have not been live-tested in this environment.

## Performance and recovery

Each analysis is quota bounded and transactional. RQ times out after 600 seconds by default; maintenance marks stale PROCESSING jobs failed. Redis dispatch failure leaves a safe failed job, and retry creates a new snapshot. Keep Redis durable and private: RQ queue data is trusted internal application data. Upload originals expire independently of derived evidence. Regularly back up PostgreSQL; test restoration and account/project deletion. Flat FAISS and full-corpus BM25 are appropriate for measured small datasets, not a demonstrated high-traffic service. See validation and benchmark reports for actual observations.

Public GitHub metadata uses the REST API first. When its public quota is exhausted, a bounded `git ls-remote --symref` lookup resolves HEAD with credential helpers, local/global Git configuration and non-HTTPS protocols disabled. It uses a fresh empty temporary directory, does no clone/checkout and executes no repository hooks or files. [Git reference lookup documentation](https://git-scm.com/docs/git-ls-remote).
