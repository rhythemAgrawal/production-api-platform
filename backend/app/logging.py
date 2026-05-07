import logging
import sys
import structlog
from opentelemetry.trace import get_current_span


def add_trace_context(_, __, event_dict):
    span = get_current_span()

    ctx = span.get_span_context()

    if ctx.is_valid:
        event_dict["trace_id"] = format(
            ctx.trace_id,
            "032x",
        )

        event_dict["span_id"] = format(
            ctx.span_id,
            "016x",
        )

    return event_dict

def setup_logging():
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )

    structlog.configure(
        processors=[
            add_trace_context,
            structlog.contextvars.merge_contextvars,  # 🔥 important
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),  # JSON logs
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
