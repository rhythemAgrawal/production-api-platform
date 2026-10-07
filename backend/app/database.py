from collections.abc import Generator
from redis import Redis
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# One client for the whole process. It keeps its own connection pool and
# does not connect until the first command.
redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
