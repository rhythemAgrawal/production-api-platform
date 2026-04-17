import time
from fastapi import FastAPI, Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse

from backend.app.services import check_rate_limit


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """
    Todo:
    1) Design per-user + per-tier limits (JWT roles)
    2) Add dynamic config via Redis/DB
    3) Custom exception classes
    4) Maybe there is a better structure for this?
    5) Use Redis time to prevent server clock difference issues
    """
    async def dispatch(self, request: Request, call_next):
        allowed, headers = check_rate_limit(request)

        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Rate limit reached",
                headers=headers
            )

        response = await call_next(request)
        return response