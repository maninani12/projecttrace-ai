import json
import logging
import threading
import time
import uuid
from collections import deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings

log = logging.getLogger("projecttrace.api")


class JsonLogFormatter(logging.Formatter):
    def format(self, record):
        fields = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        for field in (
            "request_id",
            "endpoint",
            "latency_ms",
            "status",
            "job_id",
            "snapshot_id",
            "error_type",
        ):
            if hasattr(record, field):
                fields[field] = getattr(record, field)
        return json.dumps(fields)


def setup_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    logger = logging.getLogger("projecttrace")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False


class BodyTooLarge(Exception):
    pass


class BodyLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        limit = (
            (settings().max_upload_mb + 1) * 1024**2
            if scope["path"].endswith("/upload")
            else 64 * 1024
        )
        headers = dict(scope["headers"])
        try:
            declared = int(headers.get(b"content-length", b"0"))
        except ValueError:
            declared = limit + 1
        if declared < 0 or declared > limit:
            return await JSONResponse(
                {
                    "error": {
                        "code": "body_too_large",
                        "message": "Request body exceeds the allowed limit.",
                    }
                },
                status_code=413,
            )(scope, receive, send)
        consumed = 0

        async def bounded_receive():
            nonlocal consumed
            message = await receive()
            consumed += len(message.get("body", b""))
            if consumed > limit:
                raise BodyTooLarge()
            return message

        try:
            await self.app(scope, bounded_receive, send)
        except BodyTooLarge:
            await JSONResponse(
                {
                    "error": {
                        "code": "body_too_large",
                        "message": "Request body exceeds the allowed limit.",
                    }
                },
                status_code=413,
            )(scope, receive, send)


class RateLimiter:
    def __init__(self):
        self.buckets = {}
        self.lock = threading.Lock()

    def allow(self, key, limit):
        if settings().app_env == "production":
            from redis import Redis

            client = Redis.from_url(
                settings().redis_url, socket_connect_timeout=2, socket_timeout=2
            )
            script = "local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],60) end; return n"
            return int(client.eval(script, 1, "pt:rate:" + key)) <= limit
        clock = time.monotonic()
        with self.lock:
            if len(self.buckets) > 5000:
                self.buckets = {k: q for k, q in self.buckets.items() if q and q[-1] > clock - 60}
            queue = self.buckets.setdefault(key, deque())
            while queue and queue[0] <= clock - 60:
                queue.popleft()
            if len(queue) >= limit:
                return False
            queue.append(clock)
            return True


limiter = RateLimiter()


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        config = settings()
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.perf_counter()
        origin = request.headers.get("origin")
        if (
            request.method not in {"GET", "HEAD", "OPTIONS"}
            and origin
            and origin not in config.origins
        ):
            response = JSONResponse(
                {
                    "error": {
                        "code": "origin_denied",
                        "message": "Request origin is not allowed.",
                        "request_id": request_id,
                    }
                },
                status_code=403,
            )
        else:
            path = request.url.path
            category, limit = "api", config.api_rate_per_minute
            if request.method == "POST" and path.rstrip("/") in {
                "/api/v1/auth/login",
                "/api/v1/auth/register",
                "/api/v1/auth/demo",
            }:
                category, limit = "auth", config.auth_rate_per_minute
            elif path.endswith(("/ask", "/viva", "/documents")) and request.method == "POST":
                category, limit = "ai", config.ai_rate_per_minute
            elif (
                path.endswith(("/upload", "/github", "/demo", "/analyze"))
                and request.method == "POST"
            ):
                category, limit = "import", config.import_rate_per_minute
            client = request.client.host if request.client else "unknown"
            try:
                allowed = limiter.allow(category + ":" + client, limit)
                if not allowed:
                    response = JSONResponse(
                        {
                            "error": {
                                "code": "rate_limited",
                                "message": "Too many requests. Try again in 60 seconds.",
                                "request_id": request_id,
                            }
                        },
                        status_code=429,
                        headers={"Retry-After": "60"},
                    )
                else:
                    response = await call_next(request)
            except BodyTooLarge:
                response = JSONResponse(
                    {
                        "error": {
                            "code": "body_too_large",
                            "message": "Request body exceeds the allowed limit.",
                            "request_id": request_id,
                        }
                    },
                    status_code=413,
                )
            except Exception:
                response = JSONResponse(
                    {
                        "error": {
                            "code": "service_unavailable",
                            "message": "The service could not complete this request. Try again shortly.",
                            "request_id": request_id,
                        }
                    },
                    status_code=503,
                )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        if config.app_env == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        log.info(
            "request_completed",
            extra={
                "request_id": request_id,
                "endpoint": request.url.path,
                "latency_ms": round((time.perf_counter() - start) * 1000, 2),
                "status": response.status_code,
            },
        )
        return response
