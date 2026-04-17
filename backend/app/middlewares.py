import time
from fastapi import FastAPI, Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse

from backend.app.services import check_rate_limit


class RateLimitingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        allowed, headers = check_rate_limit()

        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Rate limit reached",
                headers=headers
            )

        response = await call_next(request)
        return response