from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer
import jwt
from pathlib import Path
import time

from backend.app.database import get_db
from backend.app.models import User
from backend.config import settings
from backend.app.database import get_redis


security = HTTPBearer()

def get_user_from_db(user_id, db: Session = Depends(get_db)):
    get_user_query = select(User).where(User.id == user_id)
    user = db.execute(get_user_query).scalars().all()

    return user[0] if user else None

def check_rate_limit(credentials = Depends(security), redis_cache = Depends(get_redis)):
    token = credentials.credentials
    public_key = Path(settings.jwt_public_key_path).read_text()

    try:
        payload = jwt.decode(token, public_key, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub", "anonymous")
    except:
        user_id = "anonymous"
    
    lua_script = Path(settings.token_bucket_script_path).read_text()
    script = redis_cache.register_script(lua_script)
    user_key = "rate_limit:" + str(user_id)
    allowed, tokens, retry_after = script(keys=[user_key], args=[100, 1, time.perf_counter(), 2, 60])
    headers = {
        "X-RateLimit-Remaining": tokens,
        "Retry-After": retry_after
    }

    return bool(allowed), headers