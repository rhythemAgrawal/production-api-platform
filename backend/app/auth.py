from functools import lru_cache
from pathlib import Path
import time
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from backend.config import settings
from backend.app.services import get_user_from_db
from backend.app.database import get_db
from backend.app.models import User

security = HTTPBearer()

@lru_cache
def get_private_key() -> str:
    return Path(settings.jwt_private_key_path).read_text()

@lru_cache
def get_public_key() -> str:
    return Path(settings.jwt_public_key_path).read_text()

def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "iat": int(time.time()),
        "exp": int(time.time()) + settings.jwt_access_token_expires_seconds
    }

    return jwt.encode(payload, get_private_key(), algorithm=settings.jwt_algorithm)

def get_current_user(credentials = Depends(security), db : Session = Depends(get_db)) -> User:
    token = credentials.credentials

    try:
        payload = jwt.decode(token, get_public_key(), algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub")

        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        # "sub" is a string in the token; users.id is an integer in Postgres.
        user = get_user_from_db(int(user_id), db)

        if not user:
            raise HTTPException(status_code=401, detail="User not found")
    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return user

def extract_identity(request):
    auth = request.headers.get("Authorization")
    token = None

    if auth and auth.startswith("Bearer "):
        token = auth.removeprefix("Bearer ").strip()

    if not token:
        return "anonymous"

    try:
        payload = jwt.decode(token, get_public_key(), algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub", "anonymous")
    except jwt.InvalidTokenError:
        user_id = "anonymous"

    return user_id
