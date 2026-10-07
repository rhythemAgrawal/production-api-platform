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

app = FastAPI(title="Production API Platform", lifespan=lifespan)
register_middlewares(app)
# After the other middlewares, so tracing wraps them: request logs then carry
# trace IDs and rate-limited requests are traced and counted too.
setup_observability(app)
app.include_router(router)
