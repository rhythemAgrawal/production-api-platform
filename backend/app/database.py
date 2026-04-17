from collections.abc import Generator
from redis import Redis
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, echo=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_redis() -> Generator[Redis, None, None]:
    redis_cache = Redis(host=settings.redis_url, port=settings.redis_port, decode_responses=True)
    try:
        yield redis_cache
    finally:
        redis_cache.close()