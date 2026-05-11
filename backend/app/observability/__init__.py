from fastapi import FastAPI

from backend.app.observability.tracing import setup_tracing
from backend.app.observability.metrics import setup_metrics


def setup_observability(app: FastAPI) -> None:
    # Order matters: metrics provider must exist before FastAPIInstrumentor
    # runs, otherwise it skips emitting HTTP metrics.
    setup_metrics()
    setup_tracing(app)
