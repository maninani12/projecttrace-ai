from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.routes import router
from app.core.config import settings
from app.core.db import engine
from app.security.demo_seed import seed_demo_user
from app.security.middleware import BodyLimitMiddleware, SecurityMiddleware, setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_demo_user()
    yield


setup_logging()
app = FastAPI(
    title="ProjectTrace AI",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings().app_env != "production" else None,
    redoc_url=None,
)
app.add_middleware(BodyLimitMiddleware)
app.add_middleware(SecurityMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings().origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse(
        {
            "error": {
                "code": f"http_{exc.status_code}",
                "message": exc.detail,
                "request_id": getattr(request.state, "request_id", None),
            }
        },
        status_code=exc.status_code,
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    fields = [".".join(str(x) for x in e["loc"]) for e in exc.errors()]
    return JSONResponse(
        {
            "error": {
                "code": "invalid_input",
                "message": "Check the supplied values.",
                "fields": fields,
                "request_id": getattr(request.state, "request_id", None),
            }
        },
        status_code=422,
    )


@app.get("/health")
def health(request: Request):
    return {
        "status": "ok",
        "version": "0.1.0",
        "demo_available": settings().app_env != "production"
        and request.client.host in {"127.0.0.1", "::1", "testclient"},
    }


@app.get("/ready")
def ready():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            conn.execute(text("SELECT version_num FROM alembic_version"))
        if settings().queue_mode == "rq":
            from redis import Redis

            Redis.from_url(settings().redis_url, socket_connect_timeout=2, socket_timeout=2).ping()
        return {
            "status": "ready",
            "queue": settings().queue_mode,
            "provider": settings().llm_provider,
        }
    except Exception:
        return JSONResponse(
            {
                "status": "unavailable",
                "message": "Database migrations or queue connection unavailable.",
            },
            status_code=503,
        )


app.include_router(router)
