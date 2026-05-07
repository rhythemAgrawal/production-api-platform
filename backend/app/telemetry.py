from opentelemetry import trace

from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter,
)

from opentelemetry.instrumentation.fastapi import (
    FastAPIInstrumentor,
)

from opentelemetry.instrumentation.httpx import (
    HTTPXClientInstrumentor,
)

from opentelemetry.sdk.resources import Resource

from opentelemetry.sdk.trace import TracerProvider

from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
)

from opentelemetry.semconv.resource import (
    ResourceAttributes,
)

from app.core.config import settings


def setup_telemetry(app):
    resource = Resource.create(
        {
            ResourceAttributes.SERVICE_NAME:
                settings.APP_NAME,

            ResourceAttributes.DEPLOYMENT_ENVIRONMENT:
                settings.ENVIRONMENT,
        }
    )

    tracer_provider = TracerProvider(
        resource=resource,
    )

    exporter = OTLPSpanExporter(
        endpoint=settings
        .OTEL_EXPORTER_OTLP_ENDPOINT,
        insecure=True,
    )

    span_processor = BatchSpanProcessor(
        exporter,
    )

    tracer_provider.add_span_processor(
        span_processor,
    )

    trace.set_tracer_provider(
        tracer_provider,
    )

    FastAPIInstrumentor.instrument_app(
        app,
    )

    HTTPXClientInstrumentor().instrument()
