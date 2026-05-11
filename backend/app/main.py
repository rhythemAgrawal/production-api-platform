from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app.api import router
from backend.app.database import Base, engine
from backend.app.logging import setup_logging
from backend.app.middlewares import register_middlewares
from backend.app.observability import setup_observability


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(bind=engine)
    yield

setup_logging()

app = FastAPI(title="FastAPI PostgreSQL Demo", lifespan=lifespan)
setup_observability(app)
register_middlewares(app)
app.include_router(router)
