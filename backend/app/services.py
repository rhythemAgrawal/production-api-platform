from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database import redis_client
from backend.app.models import User
from backend.config import settings, RATE_LIMIT_RULES


# Registered once. redis-py sends the script's hash and only uploads the
# script body when Redis does not have it cached.
token_bucket = redis_client.register_script(
    Path(settings.token_bucket_script_path).read_text()
)

def get_user_from_db(user_id, db: Session):
    get_user_query = select(User).where(User.id == user_id)
    user = db.execute(get_user_query).scalars().all()

    return user[0] if user else None

def check_rate_limit(user_id, path, rate_limit_config):
    # Paths with their own rule get their own bucket, since a different
    # capacity cannot share a token count. Everything else shares "default".
    scope = path if path in RATE_LIMIT_RULES else "default"
    user_key = f"rate_limit:{scope}:{user_id}"

    allowed, tokens, retry_after = token_bucket(
        keys=[user_key],
        args=[rate_limit_config.capacity, rate_limit_config.refill_rate,
              rate_limit_config.requested, rate_limit_config.ttl])
    headers = {"X-RateLimit-Remaining": str(tokens)}

    if not allowed:
        headers["Retry-After"] = str(retry_after)

    return bool(allowed), headers
