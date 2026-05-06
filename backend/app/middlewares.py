import time
from fastapi import FastAPI, Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse

from backend.app.services import check_rate_limit
from backend.config import get_rate_limit_config
from backend.app.auth import extract_identity


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

        try:
            allowed, headers = check_rate_limit(user_id, rate_limit_config) # atomic check
        except Exception:
            # fail open
            allowed, headers = True, {}

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit reached"},
                headers=headers
            )

        response = await call_next(request)
        response.headers.update(headers)
        return response