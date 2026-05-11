import uuid
import time
from fastapi import FastAPI, Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
import structlog

from backend.app.services import check_rate_limit
from backend.config import get_rate_limit_config
from backend.app.auth import extract_identity
from backend.app.observability.instruments import (
    rate_limit_check_duration,
    rate_limit_decisions
)


logger = structlog.get_logger()

class RateLimitingMiddleware(BaseHTTPMiddleware):
    """
    Todo:
    1) Design per-user + per-tier limits (JWT roles)
    2) Add dynamic config via Redis/DB
    3) Custom exception classes
    4) Maybe there is a better structure for this?
    5) Use Redis time to prevent server clock difference issues
    6) Add lua script loader
    """
    async def dispatch(self, request: Request, call_next):
        user_id = extract_identity(request)
        rate_limit_config = get_rate_limit_config(request.url.path)

        t0 = time.perf_counter()
        try:
            allowed, headers = check_rate_limit(user_id, rate_limit_config) # atomic check
        except Exception:
            # fail open
            allowed, headers = True, {}
        finally:
            rate_limit_check_duration.record(time.perf_counter()-t0)
        
        rate_limit_decisions.add(
            1,
            {
                "outcome": "allowed" if allowed else "rejected",
                "path": request.url.path
            }
        )

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit reached"},
                headers=headers
            )

        response = await call_next(request)
        response.headers.update(headers)
        return response

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            path=request.url.path,
            method=request.method
        )

        start_time = time.time()

        try:
            response = await call_next(request)
        except Exception:
            logger.exception("Unhandled exception")
            raise

        duration = (time.time() - start_time) * 1000
        logger.info(
            "request_completed",
            status_code=response.status_code,
            duration_in_ms=duration
        )

        response.headers["X-Request-ID"] = request_id
        return response


def register_middlewares(app: FastAPI):
    app.add_middleware(RateLimitingMiddleware)
    app.add_middleware(LoggingMiddleware)
